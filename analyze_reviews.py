from pathlib import Path
import sys,csv,json,re
sys.path.insert(0,str(Path(__file__).resolve().parent/'.review_lib'))
import numpy as np
from sklearn.preprocessing import MultiLabelBinarizer,normalize
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import f1_score
from tokenizers import Tokenizer
import onnxruntime as ort
from review_data import load,parts
cats=['그래픽','스토리','운영','게임플레이','최적화','버그·안정성','기타']
classes=[c+'·'+p for c in cats for p in ['긍정','부정']]
def embed(texts):
    vectors=[]
    for i in range(0,len(texts),32):
        batch=tok.encode_batch(list(texts[i:i+32]))
        ids=np.array([x.ids for x in batch],dtype=np.int64)
        mask=np.array([x.attention_mask for x in batch],dtype=np.int64)
        inputs={'input_ids':ids,'attention_mask':mask,'token_type_ids':np.zeros_like(ids)}
        hidden=session.run(None,{k:inputs[k] for k in input_names})[0]
        vectors.extend((hidden*mask[:,:,None]).sum(1)/mask.sum(1)[:,None])
    return normalize(np.asarray(vectors))
def fit(x,y):
    return OneVsRestClassifier(LogisticRegression(class_weight='balanced',C=6,max_iter=500)).fit(x,y)
labels=list(csv.DictReader(open('review_labels.csv',encoding='utf-8-sig')))
texts=np.array([r['opinion'] for r in labels])
y=MultiLabelBinarizer(classes=classes).fit_transform([r['labels'].split('|') if r['labels'] else [] for r in labels])
groups=[r['review_id'] for r in labels]
def split(ix,size,seed):
    a,b=next(GroupShuffleSplit(test_size=size,random_state=seed).split(ix,groups=np.array(groups)[ix]))
    return ix[a],ix[b]
dev,test=split(np.arange(len(y)),0.2,42)
train,val=split(dev,0.2,17)
tok=Tokenizer.from_file('review_model/tokenizer.json')
tok.enable_truncation(max_length=128)
tok.enable_padding(pad_id=tok.token_to_id('<pad>') or 0,pad_token='<pad>')
options=ort.SessionOptions();options.intra_op_num_threads=4
session=ort.InferenceSession('review_model/model_quantized.onnx',sess_options=options,providers=['CPUExecutionProvider'])
input_names=[i.name for i in session.get_inputs()]
vec=TfidfVectorizer(analyzer='char',ngram_range=(2,4),sublinear_tf=True)
vec.fit(texts[train])
features={'TF-IDF':vec.transform(texts),'문장 임베딩':embed(texts)}
report={}; models={}
for name,x in features.items():
    model=fit(x[train],y[train]);vp=model.predict_proba(x[val])
    def score(t):
        return f1_score(y[val],vp>=t,average='macro',zero_division=0)
    threshold=max([0.35,0.4,0.45,0.5,0.55,0.6],key=score)
    pred=model.predict_proba(x[test])>=threshold
    report[name]={'validation_f1':score(threshold),'test_macro_f1':f1_score(y[test],pred,average='macro',zero_division=0),'threshold':threshold,'labels':{k:{'test_n':int(n),'f1':float(f)} for k,n,f in zip(classes,y[test].sum(0),f1_score(y[test],pred,average=None,zero_division=0))}}
    models[name]=model
winner=max(report,key=lambda k:report[k]['validation_f1'])
Path('review_metrics.json').write_text(json.dumps(dict(models=report,selected=winner,train=len(train),validation=len(val),test=len(test),label_source='AI',evaluation_unit='opinion',seed=42),ensure_ascii=False,indent=2),encoding='utf8')
print(winner,report[winner]['test_macro_f1'],flush=True)
records=load()
# 긴 리뷰도 문장 단위로 예측하고, 같은 리뷰의 같은 키워드는 한 건으로 집계한다.
opinions=[(i,s) for i,r in enumerate(records) for s in parts(r['review_text']) if re.search('[가-힣]',s)]
terms={'그래픽':'그래픽 풍경 모델링 연출 디자인 도트 초상화 이펙트 비주얼 아트','스토리':'스토리 서사 세계관 엔딩 이야기 캐릭터 설정','운영':'업데이트 패치 문의 정지 핵 과금 운영 서버','게임플레이':'보스 전투 탐험 조작 난이도 농사 낚시 파밍 오픈월드 자유도 멀티 길찾기','최적화':'프레임 최적화 사양 로딩 렉 발적화','버그·안정성':'버그 오류 튕김 멈춤 프리징 접속 저장 강종','기타':'재미 가격 추천 힐링 음악 가성비'}
aliases={'튕김':'튕|팅기','멈춤':'멈추|멈춤','재미':'재미|재밌|재밋|노잼|존잼','업데이트':'업데이트|업뎃|업댓','길찾기':r'길\s*찾','난이도':'난이도|어렵|어려','가격':'가격|돈값|비싸','프레임':'프레임|fps','저장':'저장|세이브','사양':'사양|똥컴'}
evidence=[]
for start in range(0,len(opinions),256):
    chunk=opinions[start:start+256]; ss=[s for _,s in chunk]
    x=vec.transform(ss) if winner=='TF-IDF' else embed(ss)
    scores=models[winner].predict_proba(x)
    for (i,s),pr in zip(chunk,scores):
        for j in np.where(pr>=report[winner]['threshold'])[0]:
            cat=classes[j].rsplit('·',1)[0]
            keys=[k for k in terms[cat].split() if re.search(aliases.get(k,k),s,re.I)] or ['그 외 표현']
            evidence.append([i,s,int(j),keys])
payload=dict(games=[r['game_name'] for r in records],reviews=[r['review_text'] for r in records],labels=classes,evidence=evidence)
template=Path('review_dashboard.template').read_text(encoding='utf8-sig') if False else Path('review_dashboard.template').read_text(encoding='utf-8-sig')
Path('스팀 리뷰 분석.html').write_text(template.replace('/*DATA*/',json.dumps(payload,ensure_ascii=False).replace('<',r'\u003c')),encoding='utf8')
print(len(records),len(opinions),len(evidence),flush=True)
