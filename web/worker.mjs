const index=new Map(model.vocab.map((v,i)=>[v,i]));
function infer(review,id){
 const result=[];
 for(const segment of review.split(/[\n.!?。]+|\s+(?:근데|그런데|하지만)\s+/u)){
  const s=segment.trim(); if(!/[가-힣]/.test(s))continue;
  const chars=Array.from(s.toLowerCase().replace(/\s\s+/gu,' ')), f=new Map();
  for(let n=2;n<=4;n++)for(let i=0;i+n<=chars.length;i++){
   const j=index.get(chars.slice(i,i+n).join(''));if(j!==undefined)f.set(j,(f.get(j)||0)+1);
  }
  let sum=0;for(const [j,v] of f){const w=(1+Math.log(v))*model.idf[j];f.set(j,w);sum+=w*w}
  const norm=Math.sqrt(sum)||1;
  model.labels.forEach((label,j)=>{
   let z=model.bias[j];if(model.weights[j].length)for(const [k,w] of f)z+=model.weights[j][k]*w/norm;
   if(z<Math.log(model.threshold/(1-model.threshold)))return;
   const keys=model.terms[label.slice(0,-3)].split(' ').filter(k=>new RegExp(model.aliases[k]||k,'i').test(s));
   result.push([id,s,j,keys.length?keys:['그 외 표현']]);
  });
 }
 return result;
}
function appId(raw){
 if(/^\d{1,10}$/.test(raw))return Number(raw);
 try{const url=new URL(raw);if(['http:','https:'].includes(url.protocol)&&url.hostname==='store.steampowered.com')return Number(url.pathname.match(/^\/app\/(\d{1,10})(?:\/|$)/)?.[1])}catch{}
 return 0;
}
export default {async fetch(request){
 const url=new URL(request.url);
 if(request.method!=='GET')return new Response(null,{status:405});
 if(url.pathname==='/')return new Response(html,{headers:{'Content-Type':'text/html;charset=utf-8'}});
 if(url.pathname==='/demo')return Response.json(demo);
 if(url.pathname!=='/analyze')return new Response(null,{status:404});
 const id=appId((url.searchParams.get('game')||'').trim());
 if(!id||id>4294967295)return Response.json({error:'Steam 게임 상점 주소 또는 게임 번호를 확인해 주세요.'},{status:400});
 const reviews=[],evidence=[],seen=new Set(),visited=new Set();let cursor='*';
 try{for(let page=0;page<4&&reviews.length<300&&cursor&&!visited.has(cursor);page++){
  visited.add(cursor);
  const p={appid:id,languages:['koreana'],filter:1,purchase_type:1,review_type:0,num_per_page:Math.min(100,300-reviews.length),cursor};
  const res=await fetch('https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/?input_json='+encodeURIComponent(JSON.stringify(p)),{signal:AbortSignal.timeout(20000)});
  if(!res.ok)throw Error(res.status===429?'Steam 요청이 많습니다. 잠시 뒤 다시 시도해 주세요.':'Steam 리뷰를 가져오지 못했습니다.');
  const body=(await res.json()).response;if(!body)throw Error('Steam 응답을 읽을 수 없습니다.');
  if(!body.reviews?.length)break;
  for(const r of body.reviews){if(seen.has(r.recommendationid)||r.language!=='koreana'||!r.review?.trim())continue;seen.add(r.recommendationid);evidence.push(...infer(r.review,reviews.length));reviews.push(r.review)}
  cursor=body.cursor;
 }
 if(!reviews.length)return Response.json({error:'이 게임의 한국어 리뷰를 찾지 못했습니다.'},{status:404});
 return Response.json({games:reviews.map(()=>'Steam 게임 '+id),reviews,evidence,labels:model.labels});
 }catch(error){return Response.json({error:error.name==='TimeoutError'?'Steam 응답 시간이 초과됐습니다. 다시 시도해 주세요.':error.message},{status:502})}
}};
