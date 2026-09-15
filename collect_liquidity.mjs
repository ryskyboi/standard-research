// Read-only reconstruction of the complete current tick map and position principal.
import fs from 'node:fs';
import {parseAbi,encodeFunctionData,decodeFunctionResult,decodeEventLog,keccak256,toHex} from 'viem';
const dir=new URL('./notebook-evidence/',import.meta.url);
const read=n=>JSON.parse(fs.readFileSync(new URL(n,dir),'utf8'));
const save=(n,x)=>fs.writeFileSync(new URL(n,dir),JSON.stringify(x,(_,v)=>typeof v==='bigint'?v.toString():v,2));
const state=read('state.json'),home=read('home.json'),block=toHex(BigInt(state.block));
const vals=Object.fromEntries(state.values.map(x=>[x.label,x.value]));
const abi=parseAbi(['function getTickBitmap(bytes32 poolId,int16 word) view returns(uint256)',
 'function getTickLiquidity(bytes32 poolId,int24 tick) view returns(uint128 liquidityGross,int128 liquidityNet)',
 'function getPositionInfo(bytes32 poolId,address owner,int24 tickLower,int24 tickUpper,bytes32 salt) view returns(uint128 liquidity,uint256 feeGrowthInside0LastX128,uint256 feeGrowthInside1LastX128)']);
const mc=parseAbi(['function aggregate3((address target,bool allowFailure,bytes callData)[] calls) payable returns((bool success,bytes returnData)[] returnData)']);
const event=parseAbi(['event ModifyLiquidity(bytes32 indexed id,address indexed sender,int24 tickLower,int24 tickUpper,int256 liquidityDelta,bytes32 salt)']);
const cache=new Map();let id=0;
for(const n of fs.readdirSync(dir).filter(x=>/^liquidity-rpc-\d+\.json$/.test(x))){const x=read(n);id=Math.max(id,x.request.id);if(x.response.result!==undefined)cache.set(JSON.stringify([x.request.method,x.request.params]),x.response.result);}
async function rpc(method,params){
 const key=JSON.stringify([method,params]);if(method!=='eth_getBlockByNumber'&&cache.has(key))return cache.get(key);
 for(let attempt=0;attempt<3;attempt++){
  await new Promise(r=>setTimeout(r,700+attempt*1000));
  const request={jsonrpc:'2.0',id:++id,method,params};
  const response=await fetch('https://rpc.mainnet.chain.robinhood.com',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.timeout(30000)}).then(r=>r.json());
  save(`liquidity-rpc-${String(id).padStart(4,'0')}.json`,{request,response});
  if(response.error){if(response.error.code===429&&attempt<2)continue;throw Error(JSON.stringify(response.error));}
  return response.result;
 }
}
async function batch(functionName,argsList){
 const result=[];
 for(let i=0;i<argsList.length;i+=100){
  const args=argsList.slice(i,i+100),data=encodeFunctionData({abi:mc,functionName:'aggregate3',args:[args.map(a=>({target:state.stateView,allowFailure:false,callData:encodeFunctionData({abi,functionName,args:a})}))]});
  const raw=await rpc('eth_call',[{to:home.contracts.multicall3,data},block]);
  const out=decodeFunctionResult({abi:mc,functionName:'aggregate3',data:raw});
  result.push(...out.map(x=>decodeFunctionResult({abi,functionName,data:x.returnData})));
 }
 return result;
}
if(BigInt(await rpc('eth_chainId',[]))!==4663n)throw Error('Wrong chain');
let header=await rpc('eth_getBlockByNumber',[block,false]);if(header.hash!==home.blockHash)throw Error('Wrong pin');
const spacing=state.poolKey[3],words=[];
for(let w=Math.floor(Math.floor(-887272/spacing)/256);w<=Math.floor(Math.floor(887272/spacing)/256);w++)words.push(w);
const bitmaps=await batch('getTickBitmap',words.map(w=>[state.poolId,w]));
const ticks=[];
for(let j=0;j<words.length;j++)for(let b=0;b<256;b++)if(bitmaps[j]&(1n<<BigInt(b)))ticks.push((words[j]*256+b)*spacing);
const liquidity=await batch('getTickLiquidity',ticks.map(t=>[state.poolId,t]));
const rows=ticks.map((tick,i)=>({tick,liquidityGross:liquidity[i][0],liquidityNet:liquidity[i][1]}));
const active=rows.filter(x=>x.tick<=vals.getSlot0[1]).reduce((s,x)=>s+x.liquidityNet,0n);
if(active!==BigInt(vals.getLiquidity)||rows.reduce((s,x)=>s+x.liquidityNet,0n)!==0n)throw Error('Tick liquidity does not reconcile');
save('liquidity-ticks.json',{block:state.block,blockHash:home.blockHash,poolId:state.poolId,spacing,words,bitmaps,activeLiquidity:active,sqrtPriceX96:vals.getSlot0[0],ticks:rows});
console.log('All bitmap words scanned; initialized ticks',rows.length);
const topic=keccak256(toHex('ModifyLiquidity(bytes32,address,int24,int24,int256,bytes32)'));
const start=63123899,end=Number(state.block),logs=[];
for(let b=start;b<=end;b+=10000){
 const found=await rpc('eth_getLogs',[{address:state.poolManager,topics:[topic,state.poolId],fromBlock:toHex(BigInt(b)),toBlock:toHex(BigInt(Math.min(end,b+9999)))}]);
 logs.push(...found.map(x=>({...x,decoded:decodeEventLog({abi:event,data:x.data,topics:x.topics}).args})));
}
save('liquidity-history.json',{fromBlock:start,toBlock:end,logs});
const positions=new Map();
for(const x of logs){const a=x.decoded,key=[a.sender.toLowerCase(),a.tickLower,a.tickUpper,a.salt].join(':');
 const p=positions.get(key)??{owner:a.sender,tickLower:a.tickLower,tickUpper:a.tickUpper,salt:a.salt,replayedLiquidity:0n};p.replayedLiquidity+=a.liquidityDelta;positions.set(key,p);}
const positive=[...positions.values()].filter(x=>x.replayedLiquidity>0n);
const info=await batch('getPositionInfo',positive.map(p=>[state.poolId,p.owner,p.tickLower,p.tickUpper,p.salt]));
const pol='0x242f3e67bef43470c2434d95e7d618e19f87c8f8',sqrt=Number(vals.getSlot0[0])/2**96;
for(let i=0;i<positive.length;i++){
 const p=positive[i];if(p.replayedLiquidity!==info[i][0])throw Error('Position replay mismatch');
 const lower=1.0001**(p.tickLower/2),upper=1.0001**(p.tickUpper/2),clamped=Math.max(lower,Math.min(upper,sqrt));
 p.liquidity=info[i][0];p.assumedPermanent=p.owner.toLowerCase()===pol;
 p.ethPrincipal=Number(p.liquidity)/1e18*(1/clamped-1/upper);
 p.tokenPrincipal=Number(p.liquidity)/1e18*(clamped-lower);
}
header=await rpc('eth_getBlockByNumber',[block,false]);if(header.hash!==home.blockHash)throw Error('Reorg');
save('liquidity-positions.json',{block:state.block,blockHash:home.blockHash,poolId:state.poolId,positions:positive,
 totalEthPrincipal:positive.reduce((s,x)=>s+x.ethPrincipal,0),totalTokenPrincipal:positive.reduce((s,x)=>s+x.tokenPrincipal,0),
 assumedPermanentEthPrincipal:positive.filter(x=>x.assumedPermanent).reduce((s,x)=>s+x.ethPrincipal,0),
 assumption:'Protocol PolManager principal is treated as permanently locked and safe at user request; custody safety is not re-audited here.'});
console.log('Position replay verified',positive.length,'positions;',positive.reduce((s,x)=>s+x.ethPrincipal,0),'ETH principal');
