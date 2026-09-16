import fs from 'node:fs';import zlib from 'node:zlib';
import {parseAbi,encodeFunctionData,decodeFunctionResult,decodeEventLog,toHex,keccak256} from 'viem';
const root=new URL('./',import.meta.url).pathname;const read=p=>JSON.parse(fs.readFileSync(root+p,'utf8'));
const snap=read('buyback-updates/2026-09-16T02-22-37.000Z.json'),old=read('reentry-evidence/target.json'),tag=snap.header.number,end=Number(BigInt(tag));
const folder=root+'buyback-seller-evidence/';fs.mkdirSync(folder,{recursive:true});let id=0;const raw=[];
async function rpc(method,params){for(let i=0;i<5;i++){await new Promise(r=>setTimeout(r,1300+i*3000));const request={jsonrpc:'2.0',id:++id,method,params};const response=await fetch('https://rpc.mainnet.chain.robinhood.com',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.timeout(45000)}).then(r=>r.json());raw.push({request,response});fs.writeFileSync(folder+'raw.json.gz',zlib.gzipSync(JSON.stringify(raw)));if(response.error?.code===429)continue;if(response.error)throw Error(JSON.stringify(response.error));return response.result;}throw Error('Throttled');}
if(BigInt(await rpc('eth_chainId',[]))!==4663n)throw Error('Wrong chain');
const token='0x88ad8DdF1E3898412146a534538d418c6F8A9062',manager='0x8366a39CC670B4001A1121B8F6A443A643e40951',pool='0xc73f3cd3fb68288e63f008e08ef69caa0437224e420963c6aeb4526178e87ad9';
const ta=parseAbi(['event Transfer(address indexed from,address indexed to,uint256 value)']);
const pa=parseAbi(['event Swap(bytes32 indexed id,address indexed sender,int128 amount0,int128 amount1,uint160 sqrtPriceX96,uint128 liquidity,int24 tick,uint24 fee)','event ModifyLiquidity(bytes32 indexed id,address indexed sender,int24 tickLower,int24 tickUpper,int256 liquidityDelta,bytes32 salt)']);
const sig=x=>keccak256(toHex(x.name+'('+x.inputs.map(i=>i.type).join(',')+')'));const transfers=[],events=[];
for(let b=Number(BigInt(old.header.number))+1;b<=end;b+=10000)for(const [filter,abi,arr] of [[{address:token,topics:[ta.map(sig)]},ta,transfers],[{address:manager,topics:[pa.map(sig),pool]},pa,events]]){
 for(const x of await rpc('eth_getLogs',[{...filter,fromBlock:toHex(b),toBlock:toHex(Math.min(end,b+9999))}])){const d=decodeEventLog({abi,data:x.data,topics:x.topics});arr.push({...x,event:d.eventName,decoded:d.args});}
}
const mc=parseAbi(['function aggregate3((address target,bool allowFailure,bytes callData)[] calls) payable returns((bool success,bytes returnData)[])']);
const va=parseAbi(['function getSlot0(bytes32) view returns(uint160,int24,uint24,uint24)','function getLiquidity(bytes32) view returns(uint128)','function getTickBitmap(bytes32,int16) view returns(uint256)','function getTickLiquidity(bytes32,int24) view returns(uint128,int128)']);
async function calls(items){const r=await rpc('eth_call',[{to:'0xcA11bde05977b3631167028862bE2a173976CA11',data:encodeFunctionData({abi:mc,functionName:'aggregate3',args:[items.map(x=>({target:'0xf3334192d15450cdd385c8b70e03f9a6bd9e673b',allowFailure:false,callData:encodeFunctionData({abi:va,...x})}))]})},tag]);return decodeFunctionResult({abi:mc,functionName:'aggregate3',data:r}).map((x,i)=>decodeFunctionResult({abi:va,...items[i],data:x.returnData}));}
const words=Array.from({length:36},(_,i)=>i-18);const result=await calls([{functionName:'getSlot0',args:[pool]},{functionName:'getLiquidity',args:[pool]},...words.map(w=>({functionName:'getTickBitmap',args:[pool,w]}))]);
const ticks=[];for(let i=0;i<words.length;i++)for(let b=0;b<256;b++)if(result[i+2]&(1n<<BigInt(b)))ticks.push((words[i]*256+b)*200);
const tl=await calls(ticks.map(t=>({functionName:'getTickLiquidity',args:[pool,t]})));
const rows=ticks.map((tick,i)=>({tick,liquidityGross:tl[i][0],liquidityNet:tl[i][1]}));
if(rows.reduce((s,x)=>s+x.liquidityNet,0n)!==0n||rows.filter(x=>x.tick<=result[0][1]).reduce((s,x)=>s+x.liquidityNet,0n)!==result[1])throw Error('Tick mismatch');
const final=await rpc('eth_getBlockByNumber',[tag,false]);if(final.hash!==snap.header.hash)throw Error('Reorg');
const stringify=x=>JSON.stringify(x,(_,v)=>typeof v==='bigint'?v.toString():v,2);
for(const [name,data] of [['target.json',snap],['liquidity.json',{block:end,blockHash:final.hash,poolId:pool,sqrtPriceX96:result[0][0],ticks:rows}],['transfers.json.gz',transfers],['events.json.gz',events]]){const dataStr=stringify(data);fs.writeFileSync(folder+name,name.endsWith('.gz')?zlib.gzipSync(dataStr):dataStr);}
console.log('Done',transfers.length,'transfers',events.length,'pool events',rows.length,'ticks at',end);
