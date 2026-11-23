import http from 'node:http';
import worker from './dist/server/index.js';
http.createServer(async(req,res)=>{
 try{const result=await worker.fetch(new Request(new URL(req.url,'http://localhost'),{method:req.method}));res.writeHead(result.status,Object.fromEntries(result.headers));res.end(Buffer.from(await result.arrayBuffer()))}
 catch{res.writeHead(500);res.end('Server error')}
}).listen(8765,'127.0.0.1',()=>console.log('http://127.0.0.1:8765'));
