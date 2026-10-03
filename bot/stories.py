#!/usr/bin/env python3
"""Сторис для @ivbaby_official: картинка 1080x1920 из фото карточки WB + плашки с текстом.

make(photo_url, label, title, footer, out)  — собрать JPEG
publish(image_url, env)                      — опубликовать сторис по публичной ссылке
python3 stories.py <папка>                   — опубликовать сторис на сегодня из stories.json
"""
import io, os, sys, json, time, datetime, textwrap, urllib.request, urllib.parse
from PIL import Image, ImageDraw, ImageFont

API = "https://graph.instagram.com/v21.0"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
NAVY = (31, 56, 100)
BG = (244, 241, 236)
MEDIA_REPO = "AnatolyM37/ivbaby-media"
MSK = datetime.timezone(datetime.timedelta(hours=3))


def public_url(filename):
    return f"https://cdn.jsdelivr.net/gh/{MEDIA_REPO}@main/stories/{filename}"


def _center(d, y, text, font, fill, W=1080):
    w = d.textlength(text, font=font)
    d.text(((W - w) / 2, y), text, font=font, fill=fill)


def make(photo_url, label, title, footer, out):
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), BG)
    ph = Image.open(io.BytesIO(urllib.request.urlopen(photo_url, timeout=30).read())).convert("RGB")
    pw = 1000
    ph = ph.resize((pw, int(ph.height * pw / ph.width)), Image.LANCZOS)
    top = 430
    img.paste(ph, ((W - pw) // 2, top))
    d = ImageDraw.Draw(img)
    # ярлык
    fl = ImageFont.truetype(BOLD, 40)
    lw = d.textlength(label.upper(), font=fl) + 60
    d.rounded_rectangle([(W - lw) / 2, 150, (W + lw) / 2, 220], radius=35, fill=NAVY)
    _center(d, 162, label.upper(), fl, (255, 255, 255))
    # заголовок
    ft = ImageFont.truetype(BOLD, 62)
    y = 255
    for line in textwrap.wrap(title, 26)[:2]:
        _center(d, y, line, ft, NAVY)
        y += 78
    # артикулы
    ff = ImageFont.truetype(BOLD, 38)
    fw = d.textlength(footer, font=ff) + 70
    yb = min(top + ph.height + 30, 1690)
    d.rounded_rectangle([(W - fw) / 2, yb, (W + fw) / 2, yb + 78], radius=39, fill=(255, 255, 255), outline=NAVY, width=3)
    _center(d, yb + 17, footer, ff, NAVY)
    img.save(out, "JPEG", quality=92)
    return out


def _call(method, url, params):
    if method == "GET":
        url += "?" + urllib.parse.urlencode(params); data = None
    else:
        data = urllib.parse.urlencode(params).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method), timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{e.code}: {e.read().decode()[:400]}")


def publish(image_url, env):
    tok, uid = env["IG_ACCESS_TOKEN"], env["IG_USER_ID"]
    c = _call("POST", f"{API}/{uid}/media", {"media_type": "STORIES", "image_url": image_url, "access_token": tok})
    for _ in range(30):
        st = _call("GET", f"{API}/{c['id']}", {"fields": "status_code", "access_token": tok})
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise RuntimeError(f"story error {st}")
        time.sleep(3)
    pub = _call("POST", f"{API}/{uid}/media_publish", {"creation_id": c["id"], "access_token": tok})
    return pub["id"]


def main(folder):
    sys.path.insert(0, folder)
    from publish import load_env
    env = load_env(os.path.join(folder, "api-keys.txt"))
    path = os.path.join(folder, "stories.json")
    plan = json.load(open(path, encoding="utf-8"))
    today = datetime.datetime.now(MSK).strftime("%Y-%m-%d")
    todo = [s for s in plan["stories"] if s["date"] == today and s.get("status") != "published"]
    if not todo:
        print("NO_STORY_FOR", today)
    for s in todo:
        try:
            s["media_id"] = publish(s["image_url"], env); s["status"] = "published"
            print("PUBLISHED_STORY", s["id"])
        except Exception as e:
            s["status"] = "error"; s["error"] = str(e)[:300]; print("ERROR", s["id"], e)
    left = sum(1 for s in plan["stories"] if s["date"] > today and s.get("status") != "published")
    print("STORIES_LEFT", left)
    json.dump(plan, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if any(s.get("status") == "error" for s in todo):
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1])
