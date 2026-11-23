import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
process.chdir(fileURLToPath(new URL('.', import.meta.url)));
const previous=fs.readFileSync('../스팀 리뷰 분석.html','utf8');
const start=previous.indexOf('const D=')+8;
const demo=JSON.parse(previous.slice(start,previous.indexOf(';const el=',start)));
const model=JSON.parse(fs.readFileSync('../review_classifier.json','utf8'));
const html=fs.readFileSync('index.html','utf8');
fs.mkdirSync('dist/server',{recursive:true});
fs.writeFileSync('dist/server/index.js',[
 'const html='+JSON.stringify(html)+';',
 'const demo='+JSON.stringify(demo)+';',
 'const model='+JSON.stringify(model)+';',
 fs.readFileSync('worker.mjs','utf8')
].join('\n'));
