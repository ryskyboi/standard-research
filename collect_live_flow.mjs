// Focused public read-only collection. No wallet/config/signing imports.
import fs from 'node:fs';
import {parseAbi,encodeFunctionData,decodeFunctionResult,decodeEventLog,keccak256,toHex} from 'viem';
const base=new URL('./notebook-evidence/',import.meta.url);
const read=n=>JSON.parse(fs.readFileSync(new URL(n,base),'utf8'));
const c=read('home.json').contracts, endpoint='https://rpc.mainnet.chain.robinhood.com';
const dir=new URL('./live-observations/'+new Date().toISOString().replaceAll(':','-')+'/',import.meta.url);
fs.mkdirSync(dir,{recursive:true});let serial=0;
const save=(n,v)=>fs.writeFileSync(new URL(n,dir),JSON.stringify(v,(_,x)=>typeof x==='bigint'?x.toString():x,2));
async function rpc(method,params){
 for(let attempt=0;attempt<3;attempt++){
  if(serial)await new Promise(r=>setTimeout(r,350+attempt*800));
  const request={jsonrpc:'2.0',id:++serial,method,params};
  try{
   const response=await fetch(endpoint,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.timeout(20000)}).then(r=>r.json());
   save(`rpc-${String(serial).padStart(4,'0')}.json`,{request,response});
   if(response.error){if(response.error.code===429&&attempt<2)continue;throw Error(JSON.stringify(response.error));}
   return response.result;
  }catch(e){save(`error-${serial}.json`,{request,error:String(e)});if(attempt===2)throw e;}
 }
}
if(Number(BigInt(await rpc('eth_chainId',[])))!==4663)throw Error('Wrong chain');
if(c.standard.toLowerCase()!=='0x88ad8ddf1e3898412146a534538d418c6f8a9062')throw Error('Wrong token');
const header=await rpc('eth_getBlockByNumber',['latest',false]);
const endB=Number(BigInt(header.number)),endT=Number(BigInt(header.timestamp)),tag=header.number;
let span=30000,startHeader;
for(let i=0;i<3;i++) {startHeader=await rpc('eth_getBlockByNumber',[toHex(endB-span),false]);if(Number(BigInt(startHeader.timestamp))<=endT-2700)break;span*=2;}
if(Number(BigInt(startHeader.timestamp))>endT-2400)throw Error('Window not covered');
const firstB=Number(BigInt(startHeader.number));
save('target.json',{chainId:4663,token:c.standard,question:'Current fees and prior twenty-minute decline',mode:'focused',endpoint,capturedAt:new Date().toISOString(),finality:'Latest L2 observation; not asserted L1-finalized',header,startHeader});
console.log('Pinned',endB,new Date(endT*1000).toISOString(),'directory',dir.pathname);
const abis=Object.fromEntries(['bank','hook','license','token'].map(n=>[n,read(n+'-abi.json')]));
const mc=parseAbi(['function aggregate3((address target,bool allowFailure,bytes callData)[] calls) payable returns ((bool success,bytes returnData)[] returnData)']);
const stateAbi=parseAbi(['function getSlot0(bytes32) view returns (uint160,int24,uint24,uint24)','function getLiquidity(bytes32) view returns (uint128)']);
const poolId='0xc73f3cd3fb68288e63f008e08ef69caa0437224e420963c6aeb4526178e87ad9',manager='0x8366a39CC670B4001A1121B8F6A443A643e40951',view='0xf3334192d15450cdd385c8b70e03f9a6bd9e673b';
async function calls(items,at=tag){
 const raw=await rpc('eth_call',[{to:c.multicall3,data:encodeFunctionData({abi:mc,functionName:'aggregate3',args:[items.map(x=>({target:x.address,allowFailure:true,callData:encodeFunctionData(x)}))]})},at]);
 return decodeFunctionResult({abi:mc,functionName:'aggregate3',data:raw}).map((x,i)=>x.success?{label:items[i].label,value:decodeFunctionResult({...items[i],data:x.returnData})}:{label:items[i].label,error:x.returnData});
}
const items=[];
for(const [kind,address,names] of [['token',c.standard,['name','symbol','decimals','totalSupply']],['hook',c.taxHook,['buyTaxBps','sellTaxBps','TAX_CAP_BPS','taxOverridden','taxDecayStart','taxDecayDuration','owner']],['bank',c.centralBank,['totalPendingLive','totalBranches','baseIssuancePerDay','multiplierWad','genesisTime','feeWindowDays','RESOLUTION_FEE_MIN_WAD','RESOLUTION_FEE_MAX_WAD','owner']],['license',c.licenseAuction,['remainingToday','dayFloorPrice','lastSalePrice']]])for(const functionName of names)items.push({label:kind+'.'+functionName,address,abi:abis[kind],functionName});
for(const b of [true,false])items.push({label:b?'currentBuyBps':'currentSellBps',address:c.taxHook,abi:abis.hook,functionName:'currentTaxBps',args:[b]});
for(const g of [0n,1000n,100000n,1000000n])items.push({label:'resolution.'+g,address:c.centralBank,abi:abis.bank,functionName:'previewResolutionFeeWad',args:[g*10n**18n]});
for(const functionName of ['getSlot0','getLiquidity'])items.push({label:functionName,address:view,abi:stateAbi,functionName,args:[poolId]});
const state=await calls(items);save('state.json',state);
const value=Object.fromEntries(state.map(x=>[x.label,x.value]));
if(Number(value['token.decimals'])!==18)throw Error('Unexpected decimals');
const day=Math.floor((endT-Number(value['bank.genesisTime']))/86400),days=Number(value['bank.feeWindowDays']);
const w=await calls(Array.from({length:Math.min(days,day+1)},(_,i)=>({label:'withdrawn.'+(day-i),address:c.centralBank,abi:abis.bank,functionName:'withdrawnOnDay',args:[BigInt(day-i)]})));save('withdrawal-window.json',w);
const poolAbi=parseAbi(['event Swap(bytes32 indexed id,address indexed sender,int128 amount0,int128 amount1,uint160 sqrtPriceX96,uint128 liquidity,int24 tick,uint24 fee)','event ModifyLiquidity(bytes32 indexed id,address indexed sender,int24 tickLower,int24 tickUpper,int256 liquidityDelta,bytes32 salt)']);
const topic=s=>keccak256(toHex(s));
const poolTopics=[topic('Swap(bytes32,address,int128,int128,uint160,uint128,int24,uint24)'),topic('ModifyLiquidity(bytes32,address,int24,int24,int256,bytes32)')];
const bankNames=['Withdrawn','BranchesOpened','Deposited','Revoked','EpochSettled'];
const hookNames=['TaxesUpdated','TaxCollected'];
const sig=x=>topic(x.name+'('+x.inputs.map(v=>v.type).join(',')+')');
const economicAbi=[...abis.bank.filter(x=>x.type==='event'&&bankNames.includes(x.name)),...abis.hook.filter(x=>x.type==='event'&&hookNames.includes(x.name))];
const poolLogs=[],economicLogs=[];
for(let b=firstB;b<=endB;b+=10000){
 const range={fromBlock:toHex(b),toBlock:toHex(Math.min(b+9999,endB))};
 for(const [target,filter,abi] of [[poolLogs,{address:manager,topics:[poolTopics,poolId]},poolAbi],[economicLogs,{address:[c.centralBank,c.taxHook],topics:[economicAbi.map(sig)]},economicAbi]]){
  const logs=await rpc('eth_getLogs',[{...filter,...range}]);
  for(const x of logs){if(x.removed)throw Error('Removed log');const decoded=decodeEventLog({abi,data:x.data,topics:x.topics});target.push({...x,event:decoded.eventName,decoded:decoded.args});}
 }
 console.log('Read through block',Math.min(b+9999,endB));
}
const order=(a,b)=>Number(BigInt(a.blockNumber)-BigInt(b.blockNumber))||Number(BigInt(a.logIndex)-BigInt(b.logIndex));poolLogs.sort(order);economicLogs.sort(order);
// Some providers populate blockTimestamp with 0x0; never interpret that as a real time.
if([...poolLogs,...economicLogs].some(x=>!x.blockTimestamp||BigInt(x.blockTimestamp)<=0n)){
 save('pool-events.json',poolLogs);save('economic-events.json',economicLogs);
 save('summary.json',{chainId:4663,token:c.standard,poolId,block:endB,blockHash:header.hash,invalid:'RPC supplied missing/zero log timestamps. Run analyze_live_flow.mjs against this directory to build verified block-header windows.'});
 console.log('Raw observations saved. Timestamp validation requires analyze_live_flow.mjs:',dir.pathname);
 process.exit(0);
}
const headers=new Map([[endB,header],[firstB,startHeader]]);
for(const x of [...poolLogs,...economicLogs])if(!x.blockTimestamp){const b=Number(BigInt(x.blockNumber));if(!headers.has(b))headers.set(b,await rpc('eth_getBlockByNumber',[x.blockNumber,false]));x.blockTimestamp=headers.get(b).timestamp;}
save('pool-events.json',poolLogs);save('economic-events.json',economicLogs);
const ts=x=>Number(BigInt(x.blockTimestamp));const swaps=poolLogs.filter(x=>x.event==='Swap');
const num=x=>Number(x)/1e18;const price=x=>(2**96/Number(x.decoded.sqrtPriceX96))**2;
const summaries=[];
for(const [label,lo,hi] of [['previous_20m',endT-2400,endT-1200],['last_20m',endT-1200,endT],['last_5m',endT-300,endT]]){
 const a=swaps.filter(x=>ts(x)>lo&&ts(x)<=hi),before=swaps.filter(x=>ts(x)<=lo).at(-1),last=swaps.filter(x=>ts(x)<=hi).at(-1);
 const events=economicLogs.filter(x=>ts(x)>lo&&ts(x)<=hi);const exits=events.filter(x=>x.event==='Withdrawn');
 const buy=a.filter(x=>BigInt(x.decoded.amount0)<0n),sell=a.filter(x=>BigInt(x.decoded.amount0)>0n);
 summaries.push({label,startUTC:new Date(lo*1000).toISOString(),endUTC:new Date(hi*1000).toISOString(),buyCount:buy.length,sellCount:sell.length,swapCount:a.length,
  startPriceETH:before?price(before):null,endPriceETH:last?price(last):null,priceChangePct:before&&last?100*(price(last)/price(before)-1):null,
  buysETH:buy.reduce((v,x)=>v-num(x.decoded.amount0),0),sellsETH:sell.reduce((v,x)=>v+num(x.decoded.amount0),0),tokensSold:sell.reduce((v,x)=>v-num(x.decoded.amount1),0),
  withdrawals:exits.length,branchesRetired:exits.reduce((v,x)=>v+Number(x.decoded.branchesDestroyed),0),withdrawalGross:exits.reduce((v,x)=>v+num(x.decoded.gross),0),withdrawalNet:exits.reduce((v,x)=>v+num(x.decoded.net),0),
  licensesOpened:events.filter(x=>x.event==='BranchesOpened').reduce((v,x)=>v+Number(x.decoded.count),0),
  taxChanges:events.filter(x=>x.event==='TaxesUpdated'),liquidityChanges:poolLogs.filter(x=>x.event==='ModifyLiquidity'&&ts(x)>lo&&ts(x)<=hi)});
}
const lastSales=swaps.filter(x=>ts(x)>endT-1200&&BigInt(x.decoded.amount0)>0n);
const top=[...lastSales].sort((a,b)=>num(b.decoded.amount0)-num(a.decoded.amount0)).slice(0,6);
const receipts=[];
for(const x of top){
 const receipt=await rpc('eth_getTransactionReceipt',[x.transactionHash]);if(receipt.blockHash!==x.blockHash||receipt.status!=='0x1')throw Error('Receipt mismatch');receipts.push(receipt);
}
save('largest-sale-receipts.json',receipts);
const finalHeader=await rpc('eth_getBlockByNumber',[tag,false]);if(finalHeader.hash!==header.hash)throw Error('Reorg');
const summary={chainId:4663,token:c.standard,poolId,block:endB,blockHash:header.hash,blockUTC:new Date(endT*1000).toISOString(),completedUTC:new Date().toISOString(),state,withdrawalWindow:w,windows:summaries,
 largestSales:top.map((x,i)=>({transaction:x.transactionHash,from:receipts[i].from,utc:new Date(ts(x)*1000).toISOString(),eth:num(x.decoded.amount0),tokens:-num(x.decoded.amount1),afterPriceETH:price(x)})),
 note:'Canonical STANDARD/ETH pool only. ETH swap amounts are pool event deltas, not USD or wallet totals. Block timestamps filter exact windows; starting price is the last pool swap at or before the boundary. Latest L2 pin, rechecked; no L1 finality claim.'};
save('summary.json',summary);console.log(JSON.stringify({directory:dir.pathname,windows:summaries,fees:{buy:value.currentBuyBps,sell:value.currentSellBps,override:value['hook.taxOverridden'],resolution1000:value['resolution.1000']},largestSales:summary.largestSales},(_,x)=>typeof x==='bigint'?x.toString():x,2));
