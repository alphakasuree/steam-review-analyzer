"""Run from repository root. Evaluation sets are used only after model selection."""
import csv, json, sys, copy, random, re
import argparse
from pathlib import Path
WEB = Path(__file__).resolve().parent
ROOT = WEB.parent
DATA = WEB / 'data'
sys.path[:0] = [str(ROOT/'.bert_lib'), str(ROOT/'.review_lib')]
import numpy as np
import torch
from torch import nn
from transformers import AutoTokenizer, BertModel
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import f1_score
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.multiclass import OneVsRestClassifier
from sklearn.linear_model import LogisticRegression

def read(path):
    with open(path, encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))
random.seed(42); np.random.seed(42); torch.manual_seed(42); torch.set_num_threads(4)
parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,default=WEB)
output=parser.parse_args().output
output.mkdir(parents=True,exist_ok=True)
rows=read(DATA/'review_labels.csv')
groups=np.array([r['review_id'] for r in rows])
labels=json.loads((WEB/'review_classifier.json').read_text(encoding='utf8'))['labels']
def split(ix,size,seed):
    a,b=next(GroupShuffleSplit(test_size=size,random_state=seed).split(ix,groups=groups[ix]))
    return ix[a],ix[b]
dev,test_ids=split(np.arange(len(rows)),.2,42)
_,val_ids=split(dev,.2,17)
training=read(DATA/'train_5000.csv')
validation=[rows[i] for i in val_ids]
testing=[rows[i] for i in test_ids]
audit=read(DATA/'audit.csv')
external=read(DATA/'unseen_games_audit.csv')+read(DATA/'volume_random_audit.csv')
heldout=validation+testing+audit+external
assert len(training)==5000
assert not {r['review_id'] for r in training}.intersection(r['review_id'] for r in heldout)
assert not {r['app_id'] for r in training}.intersection(r['app_id'] for r in external)
def normalized(text):return re.sub(r'[\W_]+','',text.casefold())
assert not {normalized(r['opinion']) for r in training[1256:]}.intersection(normalized(r['opinion']) for r in heldout)
allrows=training+validation+testing+audit
train,val,test,fresh=np.split(np.arange(len(allrows)),np.cumsum([len(training),len(validation),len(testing)]))
texts=np.array([r['opinion'] for r in allrows])
targets=[r['labels'].split('|') if r['labels'] else [] for r in allrows]
assert all(set(tags)<=set(labels) for tags in targets)
y=MultiLabelBinarizer(classes=labels).fit_transform(targets)
def macro(ix,p,t):return float(f1_score(y[ix],p>=t,average='macro',zero_division=0))
def metrics(ix,p,t):
    pred=p>=t
    return dict(n=len(ix),macro=macro(ix,p,t),micro=float(f1_score(y[ix],pred,average='micro',zero_division=0)),by_label={k:dict(n=int(n),f1=float(v)) for k,n,v in zip(labels,y[ix].sum(0),f1_score(y[ix],pred,average=None,zero_division=0))})
vec=TfidfVectorizer(analyzer='char',ngram_range=(2,4),sublinear_tf=True)
base=OneVsRestClassifier(LogisticRegression(class_weight='balanced',C=6,max_iter=500)).fit(vec.fit_transform(texts[train]),y[train])
basep=base.predict_proba(vec.transform(texts))
thresholds=[.35,.4,.45,.5,.55,.6]
bt=max(thresholds,key=lambda t:macro(val,basep[val],t))
device='cpu'
token=AutoTokenizer.from_pretrained('.bert_model',local_files_only=True)
bert=BertModel.from_pretrained('.bert_model',local_files_only=True,attn_implementation='eager').eval()
# Cache only frozen layers; optimize the actual final transformer block and classification head.
block=bert.encoder.layer[-1]
bert.encoder.layer=nn.ModuleList(list(bert.encoder.layer)[:-1])
batch=token(texts.tolist(),padding='max_length',truncation=True,max_length=64,return_tensors='pt')
mask=batch['attention_mask']
lengths=mask.sum(1).numpy()
hidden=torch.empty(len(texts),mask.size(1),bert.config.hidden_size)
with torch.no_grad():
    ordered=np.argsort(lengths)
    for start in range(0,len(ordered),24):
        indexes=ordered[start:start+24]
        width=int(lengths[indexes].max())
        hidden[indexes,:width]=bert(**{k:v[indexes,:width] for k,v in batch.items()}).last_hidden_state
    # Zero padding keeps masked pooling safe even when a batch mixes lengths.
    hidden.masked_fill_(~mask.bool().unsqueeze(-1),0)
del bert
head=nn.Sequential(nn.LayerNorm(768),nn.Dropout(.15),nn.Linear(768,len(labels)))
def logits(ix):
    width=int(lengths[ix].max())
    m=mask[ix,:width]; add=(1-m[:,None,None,:].float())*-10000
    values=block(hidden[ix,:width],attention_mask=add)[0]
    return head((values*m.unsqueeze(-1)).sum(1)/m.sum(1,keepdim=True))
target=torch.tensor(y,dtype=torch.float32)
counts=y[train].sum(0); weight=np.sqrt((len(train)-counts)/np.maximum(counts,1))
loss_fn=nn.BCEWithLogitsLoss(pos_weight=torch.tensor(weight,dtype=torch.float32))
optimizer=torch.optim.AdamW([{'params':block.parameters(),'lr':3e-5},{'params':head.parameters(),'lr':8e-4}])
def predict(ix):
    block.eval();head.eval()
    with torch.no_grad():
        p=torch.cat([logits(chunk).sigmoid() for chunk in np.array_split(ix,max(1,(len(ix)+23)//24))]).numpy()
    p[:,counts==0]=0
    return p
best=-1
for epoch in range(1,17):
    block.train();head.train()
    order=np.random.permutation(train)
    for start in range(0,len(order),24):
        ix=order[start:start+24]
        optimizer.zero_grad();loss_fn(logits(ix),target[ix]).backward()
        nn.utils.clip_grad_norm_(list(block.parameters())+list(head.parameters()),1)
        optimizer.step()
    pv=predict(val)
    threshold=max(thresholds,key=lambda t:macro(val,pv,t));score=macro(val,pv,threshold)
    print(epoch,round(score,4),flush=True)
    if score>best:
        best=score; chosen=epoch; cutoff=threshold
        state=(copy.deepcopy(block.state_dict()),copy.deepcopy(head.state_dict()))
block.load_state_dict(state[0]);head.load_state_dict(state[1])

torch.save(dict(block=state[0],head=state[1],labels=labels,threshold=cutoff,trained_labels=counts.tolist()),output/'bert-last-layer.pt')
results={'model':'klue/bert-base','revision':(ROOT/'.bert_model/revision.txt').read_text(encoding='utf-8-sig').strip(),'selected_epoch':chosen,'bert_threshold':cutoff,'baseline_threshold':bt,'splits':{}}
for name,ix in [('validation',val),('original_test',test),('fresh_audit',fresh)]:
    results['splits'][name]={'tfidf':metrics(ix,basep[ix],bt),'bert':metrics(ix,predict(ix),cutoff)}
results['training_examples']=len(train)
results['training_label_counts']=dict(zip(labels,counts.tolist()))
(output/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
print([(k,round(v['tfidf']['macro'],3),round(v['bert']['macro'],3)) for k,v in results['splits'].items()],flush=True)

