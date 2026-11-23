import csv,re,random,json
from pathlib import Path
def parts(text):
    return [p.strip() for p in re.split(r'[\n.!?。]+|\s+(?:근데|그런데|하지만)\s+',text) if p.strip()]
def load():
    return list(csv.DictReader(open('steam_review_data/reviews_clean.csv',encoding='utf-8-sig')))
if __name__=='__main__':
    rng=random.Random(33)
    pool=[(r['review_id'],s) for r in load() for s in parts(r['review_text']) if 6<=len(s)<=56 and re.search('[가-힣]',s)]
    rng.shuffle(pool)
    seen=set(); selected=[]
    for pattern in ['그래픽|풍경|아트|모델링|배경|연출','스토리|서사|엔딩|세계관|캐릭터','운영|업뎃|업데이트|패치|과금|핵쟁|핵이|정지','프레임|최적화|사양|발적화|로딩|렉이','버그|오류|튕|팅기|멈추|접속|강종|먹통','전투|타격|조작|파밍|난이도|보스|농사','재밌|인생겜|돈값|비싸|노잼|재미없']:
        n=0
        for rid,s in pool:
            if rid not in seen and re.search(pattern,s):
                selected.append([rid,s]);seen.add(rid);n+=1
                if n==52:break
    Path('review_candidates.json').write_text(json.dumps(selected,ensure_ascii=False),encoding='utf8')
    for i,(_,s) in enumerate(selected):print(i,s)
