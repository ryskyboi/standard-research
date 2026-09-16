// Read-only pinned execution checks and event discovery. No signing or sending.
import fs from 'node:fs';import zlib from 'node:zlib';
import {encodeFunctionData,decodeEventLog,decodeErrorResult,parseAbi,toHex} from 'viem';
const root=new URL('./',import.meta.url),dir=new URL('reentry-evidence/',root);
const read=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const target=read('reentry-evidence/target.json'),tag=target.header.number;
const state=Object.fromEntries(read('reentry-evidence/state.json').map(x=>[x.label,x.value]));
const c=read('notebook-evidence/home.json').contracts;
const abi=read('notebook-evidence/vault-abi.json'),splitter=read('reentry-abi/splitter.json');
let id=0;const raw=[];
async function rpc(method,params){await new Promise(r=>setTimeout(r,1500));const request={jsonrpc:'2.0',id:++id,method,params};const response=await fetch('https://rpc.mainnet.chain.robinhood.com',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.timeout(45000)}).then(r=>r.json());raw.push({request,response});fs.writeFileSync(new URL('vault-raw.json.gz',dir),zlib.gzipSync(JSON.stringify(raw)));return response;}
const chain=await rpc('eth_chainId',[]);if(BigInt(chain.result)!==4663n)throw Error('Wrong chain');
const checks=[];
for(const [label,from] of [['synthetic_public_caller','0x0000000000000000000000000000000000001234'],['owner_counterfactual',state['vault.owner']]]){
 const result=await rpc('eth_call',[{to:c.contractionVault,from,data:encodeFunctionData({abi,functionName:'buybackTick'})},tag]);
 let decoded=null;try{decoded=decodeErrorResult({abi,data:result.error?.data});}catch{}
 checks.push({label,from,result,decoded});
}
fs.writeFileSync(new URL('buyback-execution.json',dir),JSON.stringify({block:tag,checks},(_,x)=>typeof x==='bigint'?x.toString():x,2));
const all=[];
// Contract-address filters over the complete chain history, in bounded chunks.
for(let start=0;start<=Number(BigInt(tag));start+=10000000){
 const result=await rpc('eth_getLogs',[{address:[c.contractionVault,c.feeSplitter],fromBlock:toHex(start),toBlock:toHex(Math.min(start+9999999,Number(BigInt(tag))))}]);
 if(result.error)throw Error(JSON.stringify(result.error));
 for(const x of result.result){const d=decodeEventLog({abi:x.address.toLowerCase()===c.contractionVault.toLowerCase()?abi:splitter,data:x.data,topics:x.topics});all.push({...x,event:d.eventName,decoded:d.args});}
}
fs.writeFileSync(new URL('vault-events.json',dir),JSON.stringify(all,(_,x)=>typeof x==='bigint'?x.toString():x,2));
const swapAbi=parseAbi(['event Swap(address indexed sender,address indexed recipient,int256 amount0,int256 amount1,uint160 sqrtPriceX96,uint128 liquidity,int24 tick)']);
const result=await rpc('eth_getLogs',[{address:['0xbbd8f14be91b0eab9dcc6538b8360de243c8a4ca','0x17df14744076421e165d04372f196885c6292417'],fromBlock:toHex(target.priorHolderBlock+1),toBlock:tag}]);
if(result.error)throw Error(JSON.stringify(result.error));
const secondary=[];for(const x of result.result){try{const d=decodeEventLog({abi:swapAbi,data:x.data,topics:x.topics});secondary.push({...x,event:d.eventName,decoded:d.args});}catch{}}
fs.writeFileSync(new URL('secondary-swaps.json.gz',dir),zlib.gzipSync(JSON.stringify({logs:secondary},(_,x)=>typeof x==='bigint'?x.toString():x)));
const header=await rpc('eth_getBlockByNumber',[tag,false]);if(header.result.hash!==target.header.hash)throw Error('Reorg');
console.log(JSON.stringify({checks,events:all,secondary_swaps:secondary.length},(_,x)=>typeof x==='bigint'?x.toString():x,2));
