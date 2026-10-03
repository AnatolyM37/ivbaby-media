"""Подбор артикула (SKU) Ozon для товара WB по коду модели и цвету."""
import json, urllib.request

def norm(s): return s.lower().replace('ё','е').replace(' ','').replace(',','')

class Ozon:
    def __init__(self, cid, key):
        self.H={"Client-Id":cid,"Api-Key":key,"Content-Type":"application/json"}; self.items=None
    def call(self,path,body):
        r=urllib.request.urlopen(urllib.request.Request("https://api-seller.ozon.ru"+path,data=json.dumps(body).encode(),headers=self.H),timeout=60)
        return json.loads(r.read())
    def load(self):
        items,last=[], ""
        while True:
            r=self.call("/v3/product/list",{"filter":{"visibility":"ALL"},"last_id":last,"limit":1000})['result']
            items+=r['items']; last=r['last_id']
            if not last or len(r['items'])<1000: break
        self.items=items
    def sku_for(self, wb_vendor_code):
        """wb_vendor_code вида '30255-40034/сиреневый' → SKU Ozon (str) или None."""
        if self.items is None: self.load()
        model=wb_vendor_code.split('/')[0].split('-')[0]
        color=norm(wb_vendor_code.split('/',1)[1]) if '/' in wb_vendor_code else ''
        cand=[p for p in self.items if p['offer_id'].split(' ')[0]==model and not p.get('archived')]
        same=[p for p in cand if norm(' '.join(p['offer_id'].split(' ')[2:]))==color] or cand
        if not same: return None
        # предпочитаем средний размер
        def size(p):
            try: return int(p['offer_id'].split(' ')[1])
            except: return 0
        same.sort(key=lambda p: abs(size(p)-128))
        info=self.call("/v3/product/info/list",{"product_id":[p['product_id'] for p in same[:10]]})['items']
        for it in sorted(info,key=lambda i:abs(size(i)-128)):
            if it.get('sku'): return str(it['sku'])
        return None
