#!/usr/bin/env python3
"""Выгрузка данных для планирования контента: топ моделей WB за 30 дней + карточки + артикулы Ozon.

python3 export_data.py <папка>  → <папка>/top.json
Каждая модель: model, orders, nmIds (цвета по убыванию заказов), и по главному nmId:
title, vendorCode, subject, colors, sizes, characteristics, description, photos (big), video, ozonSku.
"""
import sys, os, json, time, datetime, urllib.request, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from publish import load_env
from ozon import Ozon


def wb(url, token, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": token, "Content-Type": "application/json"})
    for i in range(5):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(65); continue
            raise


def main(folder, top_n=40):
    env = load_env(os.path.join(folder, "api-keys.txt"))
    t = env["WB_API_TOKEN"]
    since = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    orders = wb(f"https://statistics-api.wildberries.ru/api/v1/supplier/orders?dateFrom={since}", t)
    by_nm, art = collections.Counter(), {}
    for o in orders:
        if o.get("isCancel"):
            continue
        by_nm[o["nmId"]] += 1
        art[o["nmId"]] = o["supplierArticle"].split("/")[0]
    models = collections.OrderedDict()
    for nm, k in by_nm.most_common():
        m = art[nm]
        models.setdefault(m, {"model": m, "orders": 0, "nmIds": []})
        models[m]["orders"] += k
        models[m]["nmIds"].append({"nmId": nm, "orders": k})
    top = sorted(models.values(), key=lambda x: -x["orders"])[:top_n]
    oz = Ozon(env["OZON_CLIENT_ID"], env["OZON_API_KEY"]) if env.get("OZON_API_KEY") else None
    for m in top:
        nm = m["nmIds"][0]["nmId"]
        body = {"settings": {"cursor": {"limit": 10}, "filter": {"textSearch": str(nm), "withPhoto": -1}}}
        cards = wb("https://content-api.wildberries.ru/content/v2/get/cards/list", t, body).get("cards", [])
        c = next((x for x in cards if x["nmID"] == nm), None)
        time.sleep(0.7)
        if not c:
            continue
        ch = {x["name"]: x["value"] for x in c.get("characteristics", [])}
        m.update(nmId=nm, title=c.get("title"), vendorCode=c.get("vendorCode"), subject=c.get("subjectName"),
                 sizes=[s.get("techSize") for s in c.get("sizes", [])], characteristics=ch,
                 description=(c.get("description") or "")[:1500],
                 photos=[p["big"] for p in c.get("photos", [])], video=c.get("video"))
        try:
            m["ozonSku"] = oz.sku_for(c["vendorCode"]) if oz else None
        except Exception:
            m["ozonSku"] = None
    out = {"generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "since": since, "models": top}
    json.dump(out, open(os.path.join(folder, "top.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("TOP_MODELS", len(top))


if __name__ == "__main__":
    main(sys.argv[1])
