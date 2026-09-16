// Selected public transactions and headers; no private RPC credential is stored.
import fs from 'node:fs';import zlib from 'node:zlib';
const root=new URL('./strategy-current/',import.meta.url),requests=JSON.parse(fs.readFileSync(new URL('detail-requests.json',root)));
const file=new URL('details.json',root),done=fs.existsSync(file)?JSON.parse(fs.readFileSync(file)):[];
for(let i=done.length;i<requests.length;i++){
 const request={jsonrpc:'2.0',id:i+1,...requests[i]};
 let response;
 for(let n=0;n<5;n++){
  await new Promise(r=>setTimeout(r,1500*(n+1)));
  response=await fetch('https://rpc.mainnet.chain.robinhood.com',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.timeout(30000)}).then(x=>x.json());
  if(!response.error)break;if(n===4)throw Error(JSON.stringify(response.error));
 }
 done.push({request,response});fs.writeFileSync(file,JSON.stringify(done));
 if((i+1)%20===0)console.log('Detail requests',i+1,'/',requests.length);
}
console.log('Details complete',done.length);
