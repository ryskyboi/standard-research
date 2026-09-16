// Read-only public historical observations ending at an existing frozen pin.
import fs from 'node:fs';
import zlib from 'node:zlib';
import {parseAbi,decodeEventLog,keccak256,toHex} from 'viem';
const root=new URL('./',import.meta.url);
const pin=new URL('./live-observations/2026-09-15T22-45-57.336Z/',root);
const dir=new URL('./empirical-evidence/',root);fs.mkdirSync(dir,{recursive:true});
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const target=read(new URL('target.json',pin)),summary=read(new URL('summary.json',pin));
const home=read(new URL('notebook-evidence/home.json',root));
const save=(name,v)=>fs.writeFileSync(new URL(name,dir),JSON.stringify(v,(_,x)=>typeof x==='bigint'?x.toString():x,2));
const cache=new Map();let serial=0;
for(const name of fs.readdirSync(dir).filter(n=>/^rpc-.*\.json\.gz$/.test(n))){
 const x=JSON.parse(zlib.gunzipSync(fs.readFileSync(new URL(name,dir))));serial=Math.max(serial,x.request.id);
 if(x.response.result!==undefined)cache.set(JSON.stringify([x.request.method,x.request.params]),x.response.result);
}
async function rpc(method,params,fresh=false){
 const key=JSON.stringify([method,params]);if(!fresh&&cache.has(key))return cache.get(key);
 for(let attempt=0;attempt<5;attempt++){
  await new Promise(r=>setTimeout(r,1500+(attempt?3000*2**(attempt-1):0)));
  const request={jsonrpc:'2.0',id:++serial,method,params};
  const response=await fetch(target.endpoint,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.timeout(30000)}).then(r=>r.json());
  fs.writeFileSync(new URL(`rpc-${String(serial).padStart(4,'0')}.json.gz`,dir),zlib.gzipSync(JSON.stringify({request,response})));
  if(response.error){if(attempt<4&&!String(response.error.message).includes('exceeds limit'))continue;throw Error(JSON.stringify(response.error));}
  cache.set(key,response.result);return response.result;
 }
}
if(BigInt(await rpc('eth_chainId',[],true))!==4663n)throw Error('Wrong chain');
const header=await rpc('eth_getBlockByNumber',[target.header.number,false],true);
if(header.hash!==target.header.hash)throw Error('Wrong pin');
const poolAbi=parseAbi(['event Swap(bytes32 indexed id,address indexed sender,int128 amount0,int128 amount1,uint160 sqrtPriceX96,uint128 liquidity,int24 tick,uint24 fee)','event ModifyLiquidity(bytes32 indexed id,address indexed sender,int24 tickLower,int24 tickUpper,int256 liquidityDelta,bytes32 salt)']);
const topic=s=>keccak256(toHex(s));
const bank=read(new URL('notebook-evidence/bank-abi.json',root));
const license=read(new URL('notebook-evidence/license-abi.json',root));
const economicAbi=[...bank.filter(x=>x.type==='event'&&['BranchesOpened','Deposited','Withdrawn','EpochSettled'].includes(x.name)),...license.filter(x=>x.type==='event'&&x.name==='LicensesPurchased')];
const sig=x=>topic(x.name+'('+x.inputs.map(v=>v.type).join(',')+')');
const first=63123899,end=summary.block,logs=[];
// Exact pool-ID filter avoids collecting unrelated PoolManager markets.
async function boundedLogs(filter,lo,hi){
 try{return await rpc('eth_getLogs',[{...filter,fromBlock:toHex(lo),toBlock:toHex(hi)}]);}
 catch(error){
  if(!String(error).includes('exceeds limit')||hi<=lo)throw error;
  const mid=Math.floor((lo+hi)/2);
  return [...await boundedLogs(filter,lo,mid),...await boundedLogs(filter,mid+1,hi)];
 }
}
function append(found){
 for(const x of found){
  if(x.removed)throw Error('Removed log');
  const decoded=decodeEventLog({abi:[...poolAbi,...economicAbi],data:x.data,topics:x.topics});
  logs.push({...x,event:decoded.eventName,decoded:decoded.args});
 }
}
for(let b=first;b<=end;b+=10000){
 append(await boundedLogs({address:'0x8366a39CC670B4001A1121B8F6A443A643e40951',topics:[poolAbi.map(sig),summary.poolId]},b,Math.min(b+9999,end)));
 if((b-first)%100000===0)console.log('History through',Math.min(b+9999,end),'events',logs.length);
}
for(let b=first;b<=end;b+=50000)append(await boundedLogs({address:[home.contracts.centralBank,home.contracts.licenseAuction],topics:[economicAbi.map(sig)]},b,Math.min(b+49999,end)));
logs.sort((a,b)=>Number(BigInt(a.blockNumber)-BigInt(b.blockNumber))||Number(BigInt(a.logIndex)-BigInt(b.logIndex)));
const safeString=JSON.stringify({fromBlock:first,toBlock:end,logs},(_,v)=>typeof v==='bigint'?v.toString():v);
fs.writeFileSync(new URL('events.json.gz',dir),zlib.gzipSync(safeString));
const endT=Number(BigInt(header.timestamp));
const startHeader=await rpc('eth_getBlockByNumber',[toHex(first),false]);
const rate=(end-first)/(endT-Number(BigInt(startHeader.timestamp)));
async function boundary(wanted){
 let b=Math.round(end-(endT-wanted)*rate);
 for(let i=0;i<10;i++){
  const h=await rpc('eth_getBlockByNumber',[toHex(b),false]);const delta=Number(BigInt(h.timestamp))-wanted;
  if(Math.abs(delta)<=1)return h;
  b=Math.max(first,Math.min(end,b-Math.round(delta*rate)));
 }
 throw Error('Boundary failed');
}
// Twenty full hours; all observations after the launch tax has reached its floor.
const boundaries=[];
for(let i=80;i>=0;i--){boundaries.push(i===0?header:await boundary(endT-i*900));if(i%10===0)console.log('Verified 15-minute boundary',i);}
save('boundaries.json',boundaries);
const floorStart=Number(home.snapshot.tax.taxDecayStart)+Number(home.snapshot.tax.taxDecayDuration);
const floorHeader=await boundary(floorStart);
const postTax=logs.filter(x=>x.event==='Swap'&&Number(BigInt(x.blockNumber))>=Number(BigInt(floorHeader.number)));
const peak=postTax.reduce((a,b)=>BigInt(a.decoded.sqrtPriceX96)<BigInt(b.decoded.sqrtPriceX96)?a:b);
const peakHeader=await rpc('eth_getBlockByNumber',[peak.blockNumber,false]);
const last=await rpc('eth_getBlockByNumber',[header.number,false],true);if(last.hash!==header.hash)throw Error('Reorg');
save('target.json',{chainId:4663,token:summary.token,poolId:summary.poolId,header,startHeader,floorHeader,postLaunchPeak:{event:peak,header:peakHeader},logs:logs.length,queryFromBlock:first,modelBins:80,modelIntervalSeconds:900,method:'Exact verified boundary headers; zero RPC log timestamps ignored. Raw queries saved as gzip. Post-launch peak excludes the initial tax-decay hour. Latest L2 pin, not asserted L1-finalized.'});
console.log('History complete',logs.length,'events;',boundaries.length,'boundaries; peak',new Date(Number(BigInt(peakHeader.timestamp))*1000).toISOString());
