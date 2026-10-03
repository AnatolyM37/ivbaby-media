#!/usr/bin/env python3
"""Дублирование постов Ivbaby в Telegram-канал.

publish_post(post, env) — карусель → альбом фото (sendMediaGroup), Reels → видео (sendVideo).
Подпись: текст поста без хэштегов Instagram (в Telegram они не работают как в IG), до 1024 знаков.
"""
import json, re, urllib.request

def _tg(token, method, payload):
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/{method}",
                                 data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"telegram {method}: {e.code} {e.read().decode()[:300]}")


def caption_for(post):
    """Текст поста (HTML) с кликабельными ссылками на WB и Ozon вместо строки с артикулами."""
    import html
    lines = post["caption"].strip().split("\n")
    # убрать финальную строку с артикулами / «ищите на Wildberries»
    while lines and (lines[-1].startswith("🛍") or not lines[-1].strip()):
        lines.pop()
    body = html.escape(re.sub(r"\n{3,}", "\n\n", "\n".join(lines)))
    nm, sku = post.get("nmId"), post.get("ozonSku")
    links = f'🛍 <a href="https://www.wildberries.ru/catalog/{nm}/detail.aspx">Купить на Wildberries</a> (арт. {nm})'
    if sku:
        links += f'\n🛍 <a href="https://www.ozon.ru/product/{sku}/">Купить на Ozon</a> (арт. {sku})'
    room = 1024 - len(links) - 4
    return body[:room] + "\n\n" + links


def publish_post(post, env):
    token, chat = env["TG_BOT_TOKEN"], env["TG_CHANNEL"]
    cap = caption_for(post)
    if post.get("type") == "reel":
        r = _tg(token, "sendVideo", {"chat_id": chat, "video": post["video_url"], "caption": cap,
                                     "parse_mode": "HTML", "supports_streaming": True})
        return r["result"]["message_id"]
    from publish import image_url
    media = [{"type": "photo", "media": image_url(u)} for u in post["photos"][:10]]
    media[0]["caption"] = cap
    media[0]["parse_mode"] = "HTML"
    r = _tg(token, "sendMediaGroup", {"chat_id": chat, "media": media})
    return r["result"][0]["message_id"]
