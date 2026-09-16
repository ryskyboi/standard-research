// Public Transfer replay for strategy attribution; never uses a signer.
import fs from 'node:fs';
import zlib from 'node:zlib';
import {parseAbi,decodeEventLog,keccak256,toHex,encodeFunctionData,decodeFunctionResult} from 'viem';
const root=new URL('./',import.meta.url),dir=new URL('./strategy-evidence/',root);
fs.mkdirSync(dir,{recursive:true});
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const summary=read(new URL('live-observations/2026-09-15T22-45-57.336Z/summary.json',root));
const target=read(new URL('live-observations/2026-09-15T22-45-57.336Z/target.json',root));
const abi=parseAbi(['event Transfer(address indexed from,address indexed to,uint256 value)','function balanceOf(address) view returns(uint256)']);
const cache=new Map();let serial=0;
for(const n of fs.readdirSync(dir).filter(n=>/^rpc-.*json.gz$/.test(n))){const x=JSON.parse(zlib.gunzipSync(fs.readFileSync(new URL(n,dir))));serial=Math.max(serial,x.request.id);if(x.response.result!==undefined)cache.set(JSON.stringify([x.request.method,x.request.params]),x.response.result);}
async function rpc(method,params,fresh=false){
 const key=JSON.stringify([method,params]);if(cache.has(key)&&!fresh)return cache.get(key);
 for(let a=0;a<4;a++){
  await new Promise(r=>setTimeout(r,1500+(a?3000*2**(a-1):0)));
  const request={jsonrpc:'2.0',id:++serial,method,params};
  const response=await fetch(target.endpoint,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.timeout(30000)}).then(r=>r.json());
  fs.writeFileSync(new URL(`rpc-${String(serial).padStart(4,'0')}.json.gz`,dir),zlib.gzipSync(JSON.stringify({request,response})));
  if(response.error){if(a<3&&response.error.code===429)continue;throw Error(JSON.stringify(response.error));}
  cache.set(key,response.result);return response.result;
 }
}
if(BigInt(await rpc('eth_chainId',[],true))!==4663n)throw Error('Wrong chain');
const header=await rpc('eth_getBlockByNumber',[target.header.number,false],true);
if(header.hash!==summary.blockHash)throw Error('Wrong pin');
const signature=keccak256(toHex('Transfer(address,address,uint256)'));
async function logs(lo,hi){
 try{return await rpc('eth_getLogs',[{address:summary.token,topics:[signature],fromBlock:toHex(lo),toBlock:toHex(hi)}]);}
 catch(e){if(!String(e).includes('exceeds limit')||lo===hi)throw e;const mid=Math.floor((lo+hi)/2);return [...await logs(lo,mid),...await logs(mid+1,hi)];}
}
const events=[...await logs(0,63123898)];
for(let b=63123899;b<=summary.block;b+=50000){events.push(...await logs(b,Math.min(b+49999,summary.block)));console.log('Transfers through',Math.min(b+49999,summary.block),events.length);}
events.sort((a,b)=>Number(BigInt(a.blockNumber)-BigInt(b.blockNumber))||Number(BigInt(a.logIndex)-BigInt(b.logIndex)));
const balances=new Map(),zero='0x0000000000000000000000000000000000000000';let minted=0n,burned=0n;
for(const x of events){
 if(x.removed)throw Error('Removed log');
 x.decoded=decodeEventLog({abi,data:x.data,topics:x.topics}).args;
 const {from,to,value}=x.decoded;
 if(from.toLowerCase()===zero)minted+=value;else balances.set(from.toLowerCase(),(balances.get(from.toLowerCase())||0n)-value);
 if(to.toLowerCase()===zero)burned+=value;else balances.set(to.toLowerCase(),(balances.get(to.toLowerCase())||0n)+value);
}
const supply=BigInt(summary.state.find(x=>x.label==='token.totalSupply').value);
if(minted-burned!==supply||[...balances.values()].some(x=>x<0n))throw Error('Transfer replay failed');
const save=(n,v)=>fs.writeFileSync(new URL(n,dir),JSON.stringify(v,(_,x)=>typeof x==='bigint'?x.toString():x,2));
fs.writeFileSync(new URL('transfers.json.gz',dir),zlib.gzipSync(JSON.stringify(events,(_,x)=>typeof x==='bigint'?x.toString():x)));
const ranked=[...balances].sort((a,b)=>a[1]>b[1]?-1:a[1]<b[1]?1:0).filter(x=>x[1]>0n);
save('holder-replay.json',{block:summary.block,blockHash:summary.blockHash,totalSupply:supply,minted,burned,holderCount:ranked.length,holders:ranked.map(([address,balance])=>({address,balance})),coverage:'All Transfer logs from block zero to pin. Integer mint/burn/supply reconciliation; addresses are not identified people.'});
const checks=[];
// This endpoint may prune historical storage. A failed material balance check
// remains explicit; matching aggregate supply is not silently upgraded to proof.
for(const [address,balance] of ranked.slice(0,3)){
 try{const raw=await rpc('eth_call',[{to:summary.token,data:encodeFunctionData({abi,functionName:'balanceOf',args:[address]})},target.header.number]);
  const observed=decodeFunctionResult({abi,functionName:'balanceOf',data:raw});checks.push({address,replayed:balance,observed,match:observed===balance});
 }catch(error){checks.push({address,replayed:balance,unverified:String(error)});}
}
const last=await rpc('eth_getBlockByNumber',[target.header.number,false],true);if(last.hash!==summary.blockHash)throw Error('Reorg');
save('target.json',{chainId:4663,token:summary.token,header,transferCount:events.length,checks,finality:'Rechecked L2 pin; no L1-finality claim'});
console.log('Complete:',ranked.length,'holders;',events.length,'transfers; supply reconciled.');
