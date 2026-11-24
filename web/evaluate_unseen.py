"""Score an independent checkpoint on the fixed, category-targeted new-game audit."""
import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from predict import WEB, load_predictor
from sklearn.metrics import f1_score
from sklearn.preprocessing import MultiLabelBinarizer


def evaluate(checkpoint, audit_path=None):
    labels, predict = load_predictor(checkpoint)
    rules = json.loads((WEB / 'review_classifier.json').read_text(encoding='utf8'))
    with (audit_path or WEB / 'data/unseen_games_audit.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    predictions = []
    for start in range(0, len(rows), 16):
        predictions.extend(predict([r['opinion'] for r in rows[start:start+16]]))
    encode = MultiLabelBinarizer(classes=labels).fit([])
    gold = encode.transform([r['labels'].split('|') if r['labels'] else [] for r in rows])
    pred = encode.transform(predictions)
    groups = defaultdict(lambda: defaultdict(list))
    for row, tags in zip(rows, predictions):
        for tag in tags:
            topic, polarity = tag.rsplit('·', 1)
            for word in rules['terms'][topic].split():
                if re.search(rules['aliases'].get(word, word), row['opinion'], re.I):
                    groups[row['app_id'], polarity][tag, word].append(row)
    evidence = []
    for (game, polarity), entries in sorted(groups.items()):
        ranked = sorted(entries.items(), key=lambda item: (-len(item[1]), item[0]))
        for (tag, word), hits in ranked[:3]:
            evidence.append(dict(game=game, polarity=polarity, label=tag, keyword=word,
                                 reviews=len(hits), correct=sum(tag in r['labels'].split('|') for r in hits),
                                 example=hits[0]['opinion']))
    return dict(n=len(rows), macro=f1_score(gold,pred,average='macro',zero_division=0),
                micro=f1_score(gold,pred,average='micro',zero_division=0),
                by_label=dict(zip(labels,f1_score(gold,pred,average=None,zero_division=0))),
                label_counts={label: dict(actual=int(g.sum()),predicted=int(p.sum()),
                                          correct=int((g & p).sum()))
                              for label,g,p in zip(labels,gold.T,pred.T)},
                keyword_evidence=evidence)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkpoint',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--audit',type=Path)
    args=parser.parse_args()
    args.output.write_text(json.dumps(evaluate(args.checkpoint,args.audit),ensure_ascii=False,indent=2),encoding='utf8')
