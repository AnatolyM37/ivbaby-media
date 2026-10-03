#!/usr/bin/env python3
"""Публикация постов-каруселей в Instagram @ivbaby_official из plan.json.

Использование:
  python3 publish.py <папка_с_файлами> [--date YYYY-MM-DD] [--id POST_ID] [--dry]
Папка должна содержать api-keys.txt и plan.json. Скрипт:
  * берёт пост на указанную дату (по умолчанию — сегодня по Москве) со status != published,
  * собирает картинки 1080x1350 через wsrv.nl из фото карточки WB,
  * публикует карусель через Instagram API, записывает в plan.json статус и ссылку,
  * продлевает токен Instagram, если до истечения < 20 дней (пишет новый в api-keys.txt).
"""
import json, sys, time, os, datetime, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

API = "https://graph.instagram.com/v21.0"
MSK = datetime.timezone(datetime.timedelta(hours=3))


def load_env(path):
    env = {}
    for l in open(path, encoding="utf-8"):
        l = l.strip()
        if l and not l.startswith("#") and "=" in l:
            k, v = l.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def save_env_value(path, key, value):
    lines = open(path, encoding="utf-8").read().splitlines()
    out, done = [], False
    for l in lines:
        if l.strip().startswith(key + "="):
            out.append(f"{key}={value}"); done = True
        else:
            out.append(l)
    if not done:
        out.append(f"{key}={value}")
    open(path, "w", encoding="utf-8").write("\n".join(out) + "\n")


def call(method, url, params=None):
    data = None
    if method == "GET" and params:
        url += "?" + urllib.parse.urlencode(params)
    elif params:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{e.code}: {e.read().decode()[:500]}")


def image_url(src):
    q = urllib.parse.urlencode({"url": src.replace("https://", ""), "w": 1080, "h": 1350,
                                "fit": "contain", "cbg": "ffffff", "output": "jpg", "q": 90})
    return "https://wsrv.nl/?" + q


def wait_ready(cid, token, tries=30):
    for _ in range(tries):
        st = call("GET", f"{API}/{cid}", {"fields": "status_code,status", "access_token": token})
        if st.get("status_code") == "FINISHED":
            return
        if st.get("status_code") == "ERROR":
            raise RuntimeError(f"container {cid} error: {st}")
        time.sleep(3)
    raise RuntimeError(f"container {cid} timeout")


def publish(post, env):
    token, uid = env["IG_ACCESS_TOKEN"], env["IG_USER_ID"]
    if post.get("type") == "reel":
        import reels
        caption = post["caption"].strip() + "\n\n" + " ".join(post["hashtags"])
        return reels.publish_url(post["video_url"], caption, env, post.get("thumb_ms", 1500))
    children = []
    for src in post["photos"]:
        r = call("POST", f"{API}/{uid}/media", {"image_url": image_url(src), "is_carousel_item": "true",
                                                 "access_token": token})
        children.append(r["id"])
    for c in children:
        wait_ready(c, token)
    caption = post["caption"].strip() + "\n\n" + " ".join(post["hashtags"])
    car = call("POST", f"{API}/{uid}/media", {"media_type": "CAROUSEL", "children": ",".join(children),
                                               "caption": caption, "access_token": token})
    wait_ready(car["id"], token)
    pub = call("POST", f"{API}/{uid}/media_publish", {"creation_id": car["id"], "access_token": token})
    info = call("GET", f"{API}/{pub['id']}", {"fields": "permalink", "access_token": token})
    return pub["id"], info.get("permalink")


def maybe_refresh(env, keys_path):
    token = env["IG_ACCESS_TOKEN"]
    exp = env.get("IG_TOKEN_EXPIRES")
    now = time.time()
    if exp and float(exp) - now > 20 * 86400:
        return
    try:
        r = call("GET", "https://graph.instagram.com/refresh_access_token",
                 {"grant_type": "ig_refresh_token", "access_token": token})
        save_env_value(keys_path, "IG_ACCESS_TOKEN", r["access_token"])
        save_env_value(keys_path, "IG_TOKEN_EXPIRES", str(int(now + r.get("expires_in", 5184000))))
        print("TOKEN_REFRESHED")
    except Exception as e:
        print("TOKEN_REFRESH_FAILED", e)


def main():
    folder = sys.argv[1]
    args = sys.argv[2:]
    date = datetime.datetime.now(MSK).strftime("%Y-%m-%d")
    pid, dry = None, "--dry" in args
    if "--date" in args:
        date = args[args.index("--date") + 1]
    if "--id" in args:
        pid = args[args.index("--id") + 1]
    keys_path = os.path.join(folder, "api-keys.txt")
    plan_path = os.path.join(folder, "plan.json")
    env = load_env(keys_path)
    plan = json.load(open(plan_path, encoding="utf-8"))
    todo = [p for p in plan["posts"] if p.get("status") != "published" and
            ((pid and p["id"] == pid) or (not pid and p["date"] == date))]
    if not todo:
        print("NO_POST_FOR", date)
    for p in todo:
        if dry:
            print("DRY", p["id"], p.get("video_url") if p.get("type") == "reel" else [image_url(s) for s in p["photos"]])
            continue
        try:
            mid, link = publish(p, env)
            p.update(status="published", media_id=mid, permalink=link,
                     published_at=datetime.datetime.now(MSK).isoformat(timespec="minutes"))
            print("PUBLISHED", p["id"], link)
            if env.get("TG_BOT_TOKEN") and env.get("TG_CHANNEL") and not p.get("tg_message_id"):
                try:
                    import tg
                    p["tg_message_id"] = tg.publish_post(p, env)
                    print("TELEGRAM_OK", p["id"])
                except Exception as te:
                    p["tg_error"] = str(te)[:300]
                    print("TELEGRAM_ERROR", p["id"], te)
        except Exception as e:
            p.update(status="error", error=str(e)[:300])
            print("ERROR", p["id"], e)
        json.dump(plan, open(plan_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if not dry:
        maybe_refresh(env, keys_path)
    if any(p.get("status") == "error" for p in todo):
        sys.exit(1)


if __name__ == "__main__":
    main()
