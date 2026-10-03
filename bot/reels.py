#!/usr/bin/env python3
"""Reels для @ivbaby_official из видео карточки WB.

render(video_url, title, footer, out) — скачивает HLS-видео WB, приводит к 1080x1920 (9:16),
  накладывает заголовок (первые 4 с), затем плашку с артикулами (вверху, вне зоны подписи Instagram), H.264 + AAC.
publish(path, caption, env) — загружает файл в Instagram (resumable upload, без внешнего хостинга)
  и публикует Reels. Возвращает (media_id, permalink).
"""
import os, json, time, subprocess, urllib.request, urllib.parse, textwrap
from PIL import Image, ImageDraw, ImageFont

API = "https://graph.instagram.com/v21.0"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
NAVY = (31, 56, 100)


def _plate(lines, size, out, alpha=215):
    """PNG с полупрозрачной плашкой и текстом по центру."""
    W = 1080
    font = ImageFont.truetype(FONT, size)
    pad, gap = 34, int(size * 0.28)
    hs = [font.getbbox(l)[3] - font.getbbox(l)[1] for l in lines]
    H = sum(hs) + gap * (len(lines) - 1) + pad * 2
    img = Image.new("RGBA", (W, H + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    widths = [d.textlength(l, font=font) for l in lines]
    bw = int(max(widths)) + pad * 2
    x0 = (W - bw) // 2
    d.rounded_rectangle([x0, 10, x0 + bw, 10 + H], radius=28, fill=NAVY + (alpha,))
    y = 10 + pad
    for l, h, w in zip(lines, hs, widths):
        d.text(((W - w) / 2, y - font.getbbox(l)[1]), l, font=font, fill=(255, 255, 255, 255))
        y += h + gap
    img.save(out)
    return out


def render(video_url, title, footer, out, workdir=None):
    workdir = workdir or os.path.dirname(os.path.abspath(out))
    src = os.path.join(workdir, "_src.mp4")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", video_url, "-c", "copy", src], check=True)
    top = _plate(textwrap.wrap(title, 22)[:3], 64, os.path.join(workdir, "_top.png"))
    bot = _plate([footer], 40, os.path.join(workdir, "_bot.png"), alpha=190)
    has_audio = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                                "stream=index", "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip()
    vf = ("[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30[v];"
          "[v][1:v]overlay=0:150:enable='lt(t,4)'[v1];[v1][2:v]overlay=0:170:enable='gte(t,4)'[v2]")
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", src, "-i", top, "-i", bot]
    if not has_audio:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    cmd += ["-filter_complex", vf, "-map", "[v2]", "-map", "0:a" if has_audio else "3:a",
            "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "20",
            "-maxrate", "8M", "-bufsize", "16M", "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
            "-af", "loudnorm=I=-16:TP=-1.5", "-shortest", "-movflags", "+faststart", "-t", "89", out]
    subprocess.run(cmd, check=True)
    for f in (src, top, bot):
        os.remove(f)
    return out


def _call(method, url, params=None, headers=None, data=None):
    if method == "GET" and params:
        url += "?" + urllib.parse.urlencode(params)
    elif params:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{e.code}: {e.read().decode()[:500]}")


def upload(path, caption, env, cover_offset_ms=1500):
    """Создаёт контейнер Reels и загружает видео. Возвращает id контейнера (готов к публикации)."""
    tok, uid = env["IG_ACCESS_TOKEN"], env["IG_USER_ID"]
    c = _call("POST", f"{API}/{uid}/media", {"media_type": "REELS", "upload_type": "resumable",
                                             "caption": caption, "share_to_feed": "true",
                                             "thumb_offset": str(cover_offset_ms), "access_token": tok})
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        body = f.read()
    _call("POST", c["uri"], headers={"Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(size)}, data=body)
    for _ in range(60):
        st = _call("GET", f"{API}/{c['id']}", {"fields": "status_code,status", "access_token": tok})
        if st.get("status_code") == "FINISHED":
            return c["id"]
        if st.get("status_code") == "ERROR":
            raise RuntimeError(f"reel container error: {st}")
        time.sleep(5)
    raise RuntimeError("reel container timeout")


def publish(path, caption, env):
    tok, uid = env["IG_ACCESS_TOKEN"], env["IG_USER_ID"]
    cid = upload(path, caption, env)
    pub = _call("POST", f"{API}/{uid}/media_publish", {"creation_id": cid, "access_token": tok})
    info = _call("GET", f"{API}/{pub['id']}", {"fields": "permalink", "access_token": tok})
    return pub["id"], info.get("permalink")


MEDIA_REPO = "AnatolyM37/ivbaby-media"


def public_url(filename):
    """Публичная ссылка на ролик из репозитория ivbaby-media (через CDN jsDelivr, отдаёт video/mp4)."""
    return f"https://cdn.jsdelivr.net/gh/{MEDIA_REPO}@main/reels/{filename}"


def publish_url(video_url, caption, env, thumb_ms=1500):
    """Публикует Reels по публичной ссылке на mp4. Возвращает (media_id, permalink)."""
    tok, uid = env["IG_ACCESS_TOKEN"], env["IG_USER_ID"]
    c = _call("POST", f"{API}/{uid}/media", {"media_type": "REELS", "video_url": video_url, "caption": caption,
                                             "share_to_feed": "true", "thumb_offset": str(thumb_ms), "access_token": tok})
    for _ in range(90):
        st = _call("GET", f"{API}/{c['id']}", {"fields": "status_code,status", "access_token": tok})
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise RuntimeError(f"reel container error: {st}")
        time.sleep(5)
    else:
        raise RuntimeError("reel container timeout")
    pub = _call("POST", f"{API}/{uid}/media_publish", {"creation_id": c["id"], "access_token": tok})
    info = _call("GET", f"{API}/{pub['id']}", {"fields": "permalink", "access_token": tok})
    return pub["id"], info.get("permalink")
