// Public, read-only research collector. No project config, wallet, signing or send imports.
import fs from 'node:fs';
import { encodeFunctionData, decodeFunctionResult, parseAbi, encodeAbiParameters, keccak256, toHex, decodeEventLog } from 'viem';
const dir = new URL(process.argv[2] ?? './evidence/', import.meta.url);
const read = n => JSON.parse(fs.readFileSync(new URL(n, dir), 'utf8'));
const save = (n, v) => fs.writeFileSync(new URL(n, dir), JSON.stringify(v, (_, x) => typeof x === 'bigint' ? x.toString() : x, 2));
const home = read('home.json'), c = home.contracts, block = toHex(BigInt(home.snapshot.blockNumber));
if(home.chainId!==4663 || c.standard.toLowerCase()!=='0x88ad8ddf1e3898412146a534538d418c6f8a9062')throw Error('Wrong target snapshot');
const endpoint = 'https://rpc.mainnet.chain.robinhood.com';
let serial = Math.max(0,...fs.readdirSync(dir).filter(x=>/^rpc-\d+\.json$/.test(x)).map(x=>Number(x.slice(4,-5))));
const cache=new Map();
for(const name of fs.readdirSync(dir).filter(x=>/^rpc-\d+\.json$/.test(x))) {
 const {request,response}=read(name);if(response.result!==undefined)cache.set(JSON.stringify([request.method,request.params]),response.result);
}
async function rpc(method, params) {
  const cacheKey=JSON.stringify([method,params]);
  if(['eth_call','eth_getCode','eth_getLogs'].includes(method)&&cache.has(cacheKey))return cache.get(cacheKey);
  for(let attempt=0;attempt<3;attempt++) {
  await new Promise(r=>setTimeout(r,650+attempt*1000));
  const request = {jsonrpc:'2.0', id: ++serial, method, params};
  const response = await fetch(endpoint, {method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify(request), signal:AbortSignal.timeout(30000)}).then(r=>r.json());
  save(`rpc-${String(request.id).padStart(4,'0')}.json`, {request,response});
  if(response.error) {if(response.error.code===429&&attempt<2)continue;throw Error(JSON.stringify(response.error));}
  return response.result;
  }
}
const abi = Object.fromEntries(['bank','hook','vault','license','token'].map(n=>[n,read(`${n}-abi.json`)]));
const mc = parseAbi(['function aggregate3((address target,bool allowFailure,bytes callData)[] calls) payable returns ((bool success,bytes returnData)[] returnData)']);
async function calls(items, at = block) {
  const result = [];
  for(let i=0;i<items.length;i+=100) {
    const chunk=items.slice(i,i+100), data=encodeFunctionData({abi:mc,functionName:'aggregate3',args:[chunk.map(x=>({target:x.address,allowFailure:true,callData:encodeFunctionData(x)}))]});
    const raw=await rpc('eth_call',[{to:c.multicall3,data},at]);
    const out=decodeFunctionResult({abi:mc,functionName:'aggregate3',data:raw});
    result.push(...out.map((x,j)=>x.success ? {label:chunk[j].label,value:decodeFunctionResult({...chunk[j],data:x.returnData})} : {label:chunk[j].label,error:x.returnData}));
  }
  return result;
}
if (Number(BigInt(await rpc('eth_chainId',[])))!==4663) throw Error('Wrong chain');
const header=await rpc('eth_getBlockByNumber',[block,false]);
if(header.hash!==home.blockHash) throw Error('Snapshot hash mismatch');
save('pin.json',{endpoint,capturedAt:new Date().toISOString(),finality:'latest L2, not L1-finalized',header});
const key=(await calls([{address:c.taxHook,abi:abi.hook,functionName:'poolKey',label:'key'}]))[0].value;
const poolId=keccak256(encodeAbiParameters([{type:'address'},{type:'address'},{type:'uint24'},{type:'int24'},{type:'address'}],key));
const stateView='0xf3334192d15450cdd385c8b70e03f9a6bd9e673b', poolManager='0x8366a39CC670B4001A1121B8F6A443A643e40951';
const stateAbi=parseAbi(['function getSlot0(bytes32) view returns (uint160,int24,uint24,uint24)','function getLiquidity(bytes32) view returns (uint128)']);
const nftAbi=parseAbi(['function ownerOf(uint256) view returns (address)']);
const current=[];
for(const [kind,address,names] of [
 ['bank',c.centralBank,['baseIssuancePerDay','totalBranches','totalPendingLive','multiplierWad','epochEnd','epochDays','genesisTime','issuanceRate','owner']],
 ['vault',c.contractionVault,['poolEthDepth','tickVaultPctBps','effectiveTickPoolPctBps','tickCooldown','lastTickAt','owner']],
 ['license',c.licenseAuction,['remainingToday','lastSalePrice','dayFloorPrice','auctionAnchor','owner']],
 ['token',c.standard,['name','symbol','decimals','totalSupply']]]) {
 for(const functionName of names)current.push({label:`${kind}.${functionName}`,address,abi:abi[kind],functionName});
}
current.push(...['getSlot0','getLiquidity'].map(functionName=>({label:functionName,address:stateView,abi:stateAbi,functionName,args:[poolId]})));
for(const gross of [0n,1000n,100000n,1000000n]) current.push({label:`exitFee.${gross}`,address:c.centralBank,abi:abi.bank,functionName:'previewResolutionFeeWad',args:[gross*10n**18n]});
const state=await calls(current);save('state.json',{poolKey:key,poolId,poolManager,stateView,block:home.snapshot.blockNumber,values:state});
console.log('Verified snapshot and pool',poolId);
const charters=[];
for(let id=1;id<=Number(home.snapshot.charterNft.nextId);id++) {
 for(const functionName of ['branchCountOf','pendingOf'])charters.push({label:`${id}.${functionName}`,address:c.centralBank,abi:abi.bank,functionName,args:[BigInt(id)]});
 charters.push({label:`${id}.ownerOf`,address:c.charterNFT,abi:nftAbi,functionName:'ownerOf',args:[BigInt(id)]});
}
if(!fs.existsSync(new URL('charters.json',dir))) save('charters.json',await calls(charters));console.log('Read charter balances');
// An unauthorized read-only call tests one narrow ownership proposition; no state overrides.
const probeFrom='0x000000000000000000000000000000000000dEaD';
const probes=[];
for(const [kind,address,functionName,args] of [
 ['bank',c.centralBank,'withdraw',[1n,1n,10n**18n]],
 ['bank',c.centralBank,'deposit',[1n,0n]],
 ['license',c.licenseAuction,'buyLicenses',[1n,1n,1000000n*10n**18n]]]) {
 try{probes.push({functionName,result:await rpc('eth_call',[{from:probeFrom,to:address,data:encodeFunctionData({abi:abi[kind],functionName,args})},block])});}
 catch(e){probes.push({functionName,error:String(e)});}
}
save('ownership-probes.json',probes);
// Pool/flow observations at approximate half-hour intervals; timestamps come from actual headers.
const latest=Number(BigInt(block)), genesis=Number(home.snapshot.bank.genesisTime), endTime=Number(BigInt(header.timestamp));
const history=[];
const step=Math.round(1800/(endTime-genesis)*(latest-63252200));
for(let bn=latest;bn>=63252200;bn-=Math.max(1000,step)) {
 const tag=toHex(BigInt(bn)), b=await rpc('eth_getBlockByNumber',[tag,false]);
 let values;
 try { values=await calls([
  ...['getSlot0','getLiquidity'].map(functionName=>({label:functionName,address:stateView,abi:stateAbi,functionName,args:[poolId]})),
  {label:'flow',address:c.taxHook,abi:abi.hook,functionName:'epochNetFlow'},
  {label:'depth',address:c.contractionVault,abi:abi.vault,functionName:'poolEthDepth'},
 ],tag); } catch(e) { history.push({block:bn,hash:b.hash,timestamp:Number(BigInt(b.timestamp)),error:String(e)}); break; }
 history.push({block:bn,hash:b.hash,timestamp:Number(BigInt(b.timestamp)),values});
}
save('history.json',history);console.log('Read historical pool observations',history.length);
// Bounded two-hour canonical-pool swap discovery. Log timestamps supplied by RPC if available.
const eventAbi=parseAbi(['event Swap(bytes32 indexed id,address indexed sender,int128 amount0,int128 amount1,uint160 sqrtPriceX96,uint128 liquidity,int24 tick,uint24 fee)']);
const topic=keccak256(toHex('Swap(bytes32,address,int128,int128,uint160,uint128,int24,uint24)'));
const logs=[];const start=Math.max(63252200,latest-72000);
for(let b=start;b<=latest;b+=10000){
 const found=await rpc('eth_getLogs',[{address:poolManager,topics:[topic,poolId],fromBlock:toHex(BigInt(b)),toBlock:toHex(BigInt(Math.min(latest,b+9999)))}]);
 logs.push(...found.map(x=>({...x,decoded:decodeEventLog({abi:eventAbi,data:x.data,topics:x.topics}).args})));
}
save('recent-swaps.json',{startBlock:start,endBlock:latest,logs});
const timeHeaders=[];
for(let b=start;b<latest;b+=9000)timeHeaders.push(await rpc('eth_getBlockByNumber',[toHex(BigInt(b)),false]));
timeHeaders.push(header);save('swap-time-headers.json',timeHeaders);
for(const [name,address] of Object.entries(c)){
 const code=await rpc('eth_getCode',[address,block]);save(`runtime-${name}.json`,{address,block,code,keccak256:keccak256(code)});
}
const after=await rpc('eth_getBlockByNumber',[block,false]);if(after.hash!==header.hash)throw Error('Reorg');
save('collection-complete.json',{completedAt:new Date().toISOString(),block:home.snapshot.blockNumber,hash:header.hash,swapCount:logs.length});
console.log('Complete; swaps',logs.length);
