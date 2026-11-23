"""Run with python experiment/app.py and visit the printed loopback URL."""
import json
import re
import sys
import time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
from threading import Lock
from datetime import datetime, timezone
from tempfile import NamedTemporaryFile
from urllib.error import URLError
from predict import ROOT, load_predictor
sys.path.insert(0,str(ROOT))
from collect_steam_reviews import fetch_page
from review_data import parts
import csv

labels,predict=load_predictor()
gate=Lock()
rules=json.loads((ROOT/'review_classifier.json').read_text(encoding='utf8'))
def classify(name,reviews):
    excerpts=[(i,s) for i,r in enumerate(reviews) for s in parts(r) if re.search('[가-힣]',s)]
    evidence=[]
    for start in range(0,len(excerpts),16):
        batch=excerpts[start:start+16]
        with gate:
            predictions=predict([s for _,s in batch])
        for (i,s),tags in zip(batch,predictions):
            for tag in tags:
                keys=[k for k in rules['terms'][tag.rsplit('·',1)[0]].split() if re.search(rules['aliases'].get(k,k),s,re.I)]
                evidence.append([i,s,labels.index(tag),keys or ['그 외 표현']])
    return dict(games=[name]*len(reviews),reviews=reviews,labels=labels,evidence=evidence,analyzed=datetime.now(timezone.utc).isoformat())


CACHE=ROOT/'.bert_runs'/'library-v1'
CACHE.mkdir(parents=True,exist_ok=True)
def read_result(key):
    if not re.fullmatch(r'(?:sample-)?[1-9][0-9]{0,9}',key):raise ValueError('잘못된 게임 번호입니다.')
    return json.loads((CACHE/(key+'.json')).read_text(encoding='utf8'))

def save_result(key,result):
    result['key']=key
    with NamedTemporaryFile('w',encoding='utf8',dir=CACHE,delete=False) as f:
        json.dump(result,f,ensure_ascii=False,separators=(',',':'))
    Path(f.name).replace(CACHE/(key+'.json'))
    return result

def library():
    summaries=[]
    for path in CACHE.glob('*.json'):
        d=read_result(path.stem)
        summaries.append(dict(key=d['key'],name=d['games'][0],count=len(d['reviews']),analyzed=d['analyzed']))
    return sorted(summaries,key=lambda r:r['analyzed'],reverse=True)

def seed():
    with (ROOT/'steam_review_data/reviews_clean.csv').open(encoding='utf-8-sig',newline='') as f:
        groups={}
        for r in csv.DictReader(f):
            name,rows=groups.setdefault(r['app_id'],(r['game_name'],[]))
            if len(rows)<100 and r['has_hangul']=='True':rows.append(r['review_text'])
    for app,(name,rows) in groups.items():
        key='sample-'+app
        if not (CACHE/(key+'.json')).exists():save_result(key,classify(name+' · 저장 표본',rows))

def fetch_game(raw, limit=1000):
    if limit not in (300,1000,2000):raise ValueError('분석량은 300, 1000, 2000개 중 선택해 주세요.')
    url=urlsplit(raw)
    match=re.fullmatch(r'/app/([1-9][0-9]{0,9})(?:/[^?#]*)?',url.path)
    if re.fullmatch(r'[1-9][0-9]{0,9}',raw):key=raw
    elif url.scheme in ('http','https') and url.hostname=='store.steampowered.com' and match:key=match[1]
    else:raise ValueError('Steam 상점 주소나 게임 번호를 확인해 주세요.')
    if int(key)>=2**32:raise ValueError('게임 번호가 너무 큽니다.')
    name='Steam 게임 '+key
    slug=url.path.strip('/').split('/')
    if len(slug)>2 and slug[2]:name=slug[2].replace('_',' ')+' · '+key
    game=int(key);seen=set();reviews=[];cursor='*';visited=set()
    while cursor and cursor not in visited and len(reviews)<limit:
        visited.add(cursor)
        page=fetch_page(dict(appid=game,languages=['koreana'],filter=1,purchase_type=1,review_type=0,num_per_page=min(100,limit-len(reviews)),cursor=cursor),attempts=2)
        for r in page['reviews']:
            if r['recommendationid'] not in seen and r.get('language')=='koreana' and r.get('review','').strip():
                seen.add(r['recommendationid']);reviews.append(r['review'])
        cursor=page.get('cursor') if page['reviews'] else None
        if cursor and len(reviews)<limit:time.sleep(1.5)
    if not reviews:raise ValueError('분석할 한국어 리뷰가 없습니다.')
    return save_result(key,classify(name,reviews))

html=(ROOT/'experiment'/'dashboard.html').read_text(encoding='utf8')
class Handler(BaseHTTPRequestHandler):
    def reply(self,data,status=200,mime='application/json'):
        body=(data if mime=='text/html' else json.dumps(data,ensure_ascii=False)).encode()
        self.send_response(status);self.send_header('Content-Type',mime+'; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_GET(self):
        u=urlsplit(self.path);params=parse_qs(u.query)
        try:
            if u.path=='/':return self.reply(html,mime='text/html')
            if u.path=='/health':return self.reply({'service':'klue-review-v1'})
            if u.path=='/library':return self.reply(library())
            if u.path=='/result':return self.reply(read_result(params.get('key',[''])[0]))
            return self.reply({},404)
        except FileNotFoundError:return self.reply({'error':'저장된 분석이 없습니다.'},404)
        except ValueError as e:return self.reply({'error':str(e)},400)
    def do_POST(self):
        try:
            url=urlsplit(self.path)
            if url.path not in ('/analyze','/sentence'):return self.reply({},404)
            origin=self.headers.get('Origin')
            if origin and urlsplit(origin).netloc!=self.headers.get('Host'):return self.reply({},403)
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<=6000:raise ValueError('입력 길이를 확인해 주세요.')
            text=self.rfile.read(n).decode().strip()
            if url.path=='/analyze':
                limit=int(parse_qs(url.query).get('limit',['1000'])[0])
                return self.reply(fetch_game(text,limit))
            if not 0<len(text)<=1000:raise ValueError('1~1000자 문장을 입력해 주세요.')
            with gate:tags=predict([text])[0]
            self.reply({'tags':tags})
        except ValueError as e:self.reply({'error':str(e)},400)
        except (TimeoutError,URLError):self.reply({'error':'Steam에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.'},502)
        except Exception:
            import traceback
            traceback.print_exc()
            self.reply({'error':'분석 중 오류가 발생했습니다. 다시 시도해 주세요.'},500)

if __name__=='__main__':
    seed()
    server=ThreadingHTTPServer(('127.0.0.1',8767),Handler)
    print('http://127.0.0.1:8767',flush=True)
    server.serve_forever()


