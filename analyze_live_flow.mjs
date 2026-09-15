// Repair unreliable log timestamps using bounded block-header observations.
import fs from 'node:fs';
import {toHex} from 'viem';
const dir=new URL(process.argv[2],import.meta.url);
const read=n=>JSON.parse(fs.readFileSync(new URL(n,dir),'utf8'));
const save=(n,v)=>fs.writeFileSync(new URL(n,dir),JSON.stringify(v,null,2));
const target=read('target.json'),endpoint=target.endpoint,header=target.header;
let serial=Math.max(...fs.readdirSync(dir).filter(x=>/^rpc-\d+\.json$/.test(x)).map(x=>Number(x.slice(4,-5))));
const cache=new Map();
for(const n of fs.readdirSync(dir).filter(x=>/^rpc-\d+\.json$/.test(x))){const x=read(n);if(x.response.result!==undefined)cache.set(JSON.stringify([x.request.method,x.request.params]),x.response.result);}
async function rpc(method,params){
 const key=JSON.stringify([method,params]);if(cache.has(key)&&method!=='eth_chainId')return cache.get(key);
 for(let a=0;a<3;a++){
  await new Promise(r=>setTimeout(r,350+a*800));
  const request={jsonrpc:'2.0',id:++serial,method,params};
  const response=await fetch(endpoint,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.timeout(20000)}).then(r=>r.json());
  save(`rpc-${String(request.id).padStart(4,'0')}.json`,{request,response});
  if(response.error){if(a<2)continue;throw Error(JSON.stringify(response.error));}cache.set(key,response.result);return response.result;
 }
}
if(Number(BigInt(await rpc('eth_chainId',[])))!==4663)throw Error('Wrong chain');
const n=x=>Number(BigInt(x));const endB=n(header.number),endT=n(header.timestamp),first=target.startHeader;
const rate=(endB-n(first.number))/(endT-n(first.timestamp));
async function boundary(seconds){
 const wanted=endT-seconds;let b=Math.round(endB-seconds*rate),h;
 for(let i=0;i<8;i++){
  h=await rpc('eth_getBlockByNumber',[toHex(b),false]);const delta=n(h.timestamp)-wanted;
  if(Math.abs(delta)<=1)return h;
  b=Math.max(n(first.number),Math.min(endB,b-Math.round(delta*rate)));
 }
 throw Error('Could not find a close time boundary');
}
const [b40,b20,b5]=await Promise.all([boundary(2400),boundary(1200),boundary(300)]);
save('window-headers.json',{b40,b20,b5,end:header,method:'Nearest interpolated block, verified by actual header; boundary timestamp within one second of requested window.'});
const pool=read('pool-events.json'),economic=read('economic-events.json'),state=read('state.json');
const swaps=pool.filter(x=>x.event==='Swap');const amount=x=>Number(x)/1e18;
const price=x=>(2**96/Number(x.decoded.sqrtPriceX96))**2;
const summaries=[];
for(const [label,start,end] of [['previous_20m',b40,b20],['last_20m',b20,header],['last_5m',b5,header]]){
 const lo=n(start.number),hi=n(end.number);const within=x=>n(x.blockNumber)>lo&&n(x.blockNumber)<=hi;
 const selected=swaps.filter(within),before=swaps.filter(x=>n(x.blockNumber)<=lo).at(-1),last=swaps.filter(x=>n(x.blockNumber)<=hi).at(-1);
 if(!before||!last)throw Error('Missing boundary price');
 const buys=selected.filter(x=>BigInt(x.decoded.amount0)<0n),sales=selected.filter(x=>BigInt(x.decoded.amount0)>0n),ev=economic.filter(within),ex=ev.filter(x=>x.event==='Withdrawn');
 const buyETH=buys.reduce((v,x)=>v-amount(x.decoded.amount0),0),sellETH=sales.reduce((v,x)=>v+amount(x.decoded.amount0),0);
 summaries.push({label,startBlock:lo,endBlock:hi,startUTC:new Date(n(start.timestamp)*1000).toISOString(),endUTC:new Date(n(end.timestamp)*1000).toISOString(),durationSeconds:n(end.timestamp)-n(start.timestamp),
  buyCount:buys.length,sellCount:sales.length,swapCount:selected.length,startPriceETH:price(before),endPriceETH:price(last),priceChangePct:100*(price(last)/price(before)-1),
  buysETH:buyETH,sellsETH:sellETH,netSwapETH:buyETH-sellETH,tokensSold:sales.reduce((v,x)=>v-amount(x.decoded.amount1),0),
  withdrawals:ex.length,branchesRetired:ex.reduce((v,x)=>v+Number(x.decoded.branchesDestroyed),0),withdrawalGross:ex.reduce((v,x)=>v+amount(x.decoded.gross),0),withdrawalNet:ex.reduce((v,x)=>v+amount(x.decoded.net),0),
  licensesOpened:ev.filter(x=>x.event==='BranchesOpened').reduce((v,x)=>v+Number(x.decoded.count),0),deposits:ev.filter(x=>x.event==='Deposited').reduce((v,x)=>v+amount(x.decoded.amount),0),
  taxChanges:ev.filter(x=>x.event==='TaxesUpdated'),liquidityChanges:pool.filter(x=>x.event==='ModifyLiquidity'&&within(x))});
}
const recent=swaps.filter(x=>n(x.blockNumber)>n(b20.number)&&BigInt(x.decoded.amount0)>0n);
const top=[...recent].sort((a,b)=>amount(b.decoded.amount0)-amount(a.decoded.amount0)).slice(0,6);
const receipts=[],largest=[];
for(const x of top){
 const [receipt,b]=await Promise.all([rpc('eth_getTransactionReceipt',[x.transactionHash]),rpc('eth_getBlockByNumber',[x.blockNumber,false])]);
 if(receipt.blockHash!==x.blockHash||receipt.status!=='0x1'||b.hash!==x.blockHash)throw Error('Receipt/header mismatch');receipts.push(receipt);
 largest.push({transaction:x.transactionHash,from:receipt.from,utc:new Date(n(b.timestamp)*1000).toISOString(),eth:amount(x.decoded.amount0),tokens:-amount(x.decoded.amount1),afterPriceETH:price(x)});
}
save('largest-sale-receipts.json',receipts);
// Force a fresh pin check instead of taking it from the query cache.
cache.delete(JSON.stringify(['eth_getBlockByNumber',[header.number,false]]));
const final=await rpc('eth_getBlockByNumber',[header.number,false]);if(final.hash!==header.hash)throw Error('Reorg');
const summary={chainId:4663,token:target.token,poolId:read('summary.json').poolId,block:endB,blockHash:header.hash,blockUTC:new Date(endT*1000).toISOString(),completedUTC:new Date().toISOString(),state,withdrawalWindow:read('withdrawal-window.json'),windows:summaries,largestSales:largest,
 note:'Canonical STANDARD/ETH pool. RPC log blockTimestamp fields were zero and are NOT used. Window boundaries use actual verified block headers, within one second of target time; trades filtered by block number. Pool swap deltas, not USD or wallet totals. Latest L2 pin rechecked; no L1 finality claim.'};
save('summary.json',summary);console.log(JSON.stringify({windows:summaries,largestSales:largest},null,2));
