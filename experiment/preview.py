"""Run with python experiment/preview.py and visit the printed loopback URL."""
import json
import re
import sys
import time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
from threading import Lock
from itertools import islice
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
    return dict(games=[name]*len(reviews),reviews=reviews,labels=labels,evidence=evidence)

def fetch_game(raw):
    match=re.fullmatch(r'(?:https?://store\.steampowered\.com/app/)?(\d{1,10})(?:[/?#].*)?',raw)
    if not match or not 0<int(match[1])<2**32:raise ValueError('Steam 상점 주소나 게임 번호를 확인해 주세요.')
    game=int(match[1]);seen=set();reviews=[];cursor='*';visited=set()
    while cursor and cursor not in visited and len(reviews)<300 and len(visited)<4:
        visited.add(cursor)
        page=fetch_page(dict(appid=game,languages=['koreana'],filter=1,purchase_type=1,review_type=0,num_per_page=min(100,300-len(reviews)),cursor=cursor),attempts=2)
        for r in page['reviews']:
            if r['recommendationid'] not in seen and r.get('language')=='koreana' and r.get('review','').strip():
                seen.add(r['recommendationid']);reviews.append(r['review'])
        cursor=page.get('cursor') if page['reviews'] else None
        if cursor and len(reviews)<300:time.sleep(1.5)
    if not reviews:raise ValueError('분석할 한국어 리뷰가 없습니다.')
    return classify('Steam 게임 '+str(game),reviews)

html=(ROOT/'web/index.html').read_text(encoding='utf-8-sig').replace('스팀 리뷰 분석','한국어 BERT 리뷰 분석')
panel="""<section><h2>리뷰 한 문장 체험</h2><form id="single"><input id="sentence" required maxlength="1000" value="캐릭터 이동이 너무 답답함" aria-label="분석할 리뷰"><button>문장 분석</button></form><p id="prediction" role="status"></p></section>"""
js="""document.getElementById('single').onsubmit=async e=>{e.preventDefault();const result=document.getElementById('prediction'),button=e.target.querySelector('button');button.disabled=true;result.textContent='분석 중…';try{const r=await fetch('/sentence',{method:'POST',body:document.getElementById('sentence').value});const d=await r.json();if(!r.ok)throw Error(d.error);result.textContent=d.tags.join(' / ')||'미분류'}catch(err){result.textContent=err.message}finally{button.disabled=false}};"""
html=html.replace('</header>','</header>'+panel).replace('</script>',js+'</script>')
with (ROOT/'steam_review_data/reviews_clean.csv').open(encoding='utf-8-sig',newline='') as f:
    demo=classify('엘든 링 · 체험 표본',list(islice((r['review_text'] for r in csv.DictReader(f) if r['game_name']=='ELDEN RING' and r['has_hangul']=='True'),30)))
class Handler(BaseHTTPRequestHandler):
    def reply(self,data,status=200,mime='application/json'):
        body=(data if mime=='text/html' else json.dumps(data,ensure_ascii=False)).encode()
        self.send_response(status);self.send_header('Content-Type',mime+'; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_GET(self):
        url=urlsplit(self.path)
        if url.path=='/':return self.reply(html,mime='text/html')
        if url.path=='/demo':return self.reply(demo)
        if url.path!='/analyze':return self.reply({},404)
        try:data=fetch_game(parse_qs(url.query).get('game',[''])[0].strip())
        except ValueError as error:return self.reply({'error':str(error)},400)
        except (OSError,URLError):return self.reply({'error':'Steam 연결이 지연됩니다. 다시 시도해 주세요.'},502)
        self.reply(data)
    def do_POST(self):
        if self.path!='/sentence':return self.reply({},404)
        n=int(self.headers.get('Content-Length',0))
        if not 0<n<=6000:return self.reply({'error':'1~1000자 문장을 입력해 주세요.'},400)
        text=self.rfile.read(n).decode().strip()
        if not 0<len(text)<=1000:return self.reply({'error':'1~1000자 문장을 입력해 주세요.'},400)
        with gate:tags=predict([text])[0]
        self.reply({'tags':tags})
if __name__=='__main__':
    server=ThreadingHTTPServer(('127.0.0.1',8766),Handler)
    print('http://127.0.0.1:8766',flush=True)
    server.serve_forever()
