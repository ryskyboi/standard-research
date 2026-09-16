// Reconcile hook ETH tax events through the same frozen snapshot.
import fs from 'node:fs';import zlib from 'node:zlib';import {decodeEventLog,toHex} from 'viem';
const root=new URL('./',import.meta.url),dir=new URL('reentry-evidence/',root);
const read=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const target=read('reentry-evidence/target.json'),abi=read('notebook-evidence/hook-abi.json');
const hook=read('notebook-evidence/home.json').contracts.taxHook;const end=Number(BigInt(target.header.number));
const rawPath=new URL('fee-raw.json.gz',dir);const raw=fs.existsSync(rawPath)?JSON.parse(zlib.gunzipSync(fs.readFileSync(rawPath))):[];let id=raw.length;const logs=[];
const cache=new Map(raw.filter(x=>x.response.result).map(x=>[JSON.stringify(x.request.params),x.response]));const retries=new Map();
const ranges=[];for(let start=63251626;start<=end;start+=50000)ranges.push([start,Math.min(end,start+49999)]);
while(ranges.length){
 const [start,stop]=ranges.shift();
 await new Promise(r=>setTimeout(r,1500));
 const request={jsonrpc:'2.0',id:++id,method:'eth_getLogs',params:[{address:hook,fromBlock:toHex(start),toBlock:toHex(stop)}]};
 const response=cache.get(JSON.stringify(request.params))||await fetch('https://rpc.mainnet.chain.robinhood.com',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.timeout(45000)}).then(r=>r.json());
 raw.push({request,response});fs.writeFileSync(new URL('fee-raw.json.gz',dir),zlib.gzipSync(JSON.stringify(raw)));
 if(response.error){if(response.error.code===429){const k=start+":"+stop,n=(retries.get(k)||0)+1;retries.set(k,n);if(n<=5){await new Promise(r=>setTimeout(r,5000*n));ranges.unshift([start,stop]);continue;}}if(response.error.message?.includes("exceeds limit")&&stop>start){const mid=Math.floor((start+stop)/2);ranges.unshift([start,mid],[mid+1,stop]);continue;}throw Error(JSON.stringify(response.error));}
 for(const x of response.result){const d=decodeEventLog({abi,data:x.data,topics:x.topics});logs.push({...x,event:d.eventName,decoded:d.args});}
}
fs.writeFileSync(new URL('fee-events.json.gz',dir),zlib.gzipSync(JSON.stringify(logs,(_,x)=>typeof x==='bigint'?x.toString():x)));
console.log('Saved hook events',logs.length);
