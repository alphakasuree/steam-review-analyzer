"""Load the experiment checkpoint and classify one or more Korean review excerpts."""
import argparse
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'.bert_lib'),str(ROOT/'.review_lib')]
import torch
from torch import nn
from transformers import AutoTokenizer, BertModel

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('text',nargs='+',help='One opinion per quoted argument')
    args=parser.parse_args()
    model_dir=ROOT/'.bert_model'
    state=torch.load(ROOT/'experiment'/'bert-last-layer.pt',map_location='cpu',weights_only=True)
    tokenizer=AutoTokenizer.from_pretrained(model_dir,local_files_only=True)
    model=BertModel.from_pretrained(model_dir,local_files_only=True,attn_implementation='eager')
    model.encoder.layer[-1].load_state_dict(state['block'])
    head=nn.Sequential(nn.LayerNorm(768),nn.Dropout(.15),nn.Linear(768,len(state['labels'])))
    head.load_state_dict(state['head'])
    head.eval();model.eval();torch.set_num_threads(4)
    with torch.inference_mode():
        b=tokenizer(args.text,truncation=True,max_length=64,padding=True,return_tensors='pt')
        h=model(**b).last_hidden_state
        mask=b['attention_mask'].unsqueeze(-1)
        scores=head((h*mask).sum(1)/mask.sum(1)).sigmoid()
    for text,values in zip(args.text,scores):
        labels=[label for label,s,n in zip(state['labels'],values,state['trained_labels']) if n and s>=state['threshold']]
        print(text,'→',', '.join(labels) or '미분류')

if __name__=='__main__':main()
