// Public, read-only state for a specified existing observation. No wallet imports.
import fs from 'node:fs';
import {parseAbi, encodeFunctionData, decodeFunctionResult} from 'viem';
const root = new URL('./', import.meta.url);
const dir = new URL(process.argv[2] || './live-observations/2026-09-15T22-34-29.773Z/', root);
const read = p => JSON.parse(fs.readFileSync(p, 'utf8'));
const target = read(new URL('target.json', dir));
const summary = read(new URL('summary.json', dir));
const home = read(new URL('notebook-evidence/home.json', root));
const oldPositions = read(new URL('notebook-evidence/liquidity-positions.json', root));
const c = home.contracts, tag = target.header.number;
const save = (n,v) => fs.writeFileSync(new URL(n,dir),JSON.stringify(v,(_,x)=>typeof x==='bigint'?x.toString():x,2)+'\n');
let id=0;
async function rpc(method,params) {
  await new Promise(r=>setTimeout(r,400));
  const request={jsonrpc:'2.0',id:++id,method,params};
  const response=await fetch(target.endpoint,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.timeout(30000)}).then(r=>r.json());
  save(`recovery-rpc-${String(id).padStart(3,'0')}.json`,{request,response});
  if(response.error)throw Error(JSON.stringify(response.error));
  return response.result;
}
const mc=parseAbi(['function aggregate3((address target,bool allowFailure,bytes callData)[] calls) payable returns ((bool success,bytes returnData)[] returnData)']);
const view='0xf3334192d15450cdd385c8b70e03f9a6bd9e673b';
const abi=parseAbi(['function getTickBitmap(bytes32,int16) view returns(uint256)', 'function getPositionInfo(bytes32,address,int24,int24,bytes32) view returns(uint128,uint256,uint256)']);
// Net liquidity is signed. Keep the actual ABI separate from unsigned position fields.
const tickAbi=parseAbi(['function getTickLiquidity(bytes32,int24) view returns(uint128 liquidityGross,int128 liquidityNet)']);
async function calls(items) {
  const result=[];
  for(let i=0;i<items.length;i+=100){
    const group=items.slice(i,i+100);
    const raw=await rpc('eth_call',[{to:c.multicall3,data:encodeFunctionData({abi:mc,functionName:'aggregate3',args:[group.map(x=>({target:x.address,allowFailure:false,callData:encodeFunctionData(x)}))]})},tag]);
    const decoded=decodeFunctionResult({abi:mc,functionName:'aggregate3',data:raw});
    result.push(...decoded.map((x,j)=>decodeFunctionResult({...group[j],data:x.returnData})));
  }
  return result;
}
if(BigInt(await rpc('eth_chainId',[]))!==4663n)throw Error('Wrong chain');
if(summary.token.toLowerCase()!=='0x88ad8ddf1e3898412146a534538d418c6f8a9062')throw Error('Wrong token');
if((await rpc('eth_getBlockByNumber',[tag,false])).hash!==target.header.hash)throw Error('Wrong pin');
const words=[];for(let w=Math.floor(Math.floor(-887272/200)/256);w<=Math.floor(Math.floor(887272/200)/256);w++)words.push(w);
const bitmaps=await calls(words.map(w=>({address:view,abi,functionName:'getTickBitmap',args:[summary.poolId,w]})));
const ticks=[];for(let i=0;i<words.length;i++)for(let b=0;b<256;b++)if(bitmaps[i]&(1n<<BigInt(b)))ticks.push((words[i]*256+b)*200);
const values=await calls(ticks.map(t=>({address:view,abi:tickAbi,functionName:'getTickLiquidity',args:[summary.poolId,t]})));
const rows=ticks.map((tick,i)=>({tick,liquidityGross:values[i][0],liquidityNet:values[i][1]}));
const state=Object.fromEntries((summary.state || read(new URL('state.json',dir))).map(x=>[x.label,x.value]));
const active=rows.filter(x=>x.tick<=state.getSlot0[1]).reduce((a,x)=>a+x.liquidityNet,0n);
if(active!==BigInt(state.getLiquidity)||rows.reduce((a,x)=>a+x.liquidityNet,0n)!==0n)throw Error('Tick reconciliation failed');
save('recovery-liquidity.json',{block:summary.block,blockHash:summary.blockHash,poolId:summary.poolId,spacing:200,words,bitmaps,activeLiquidity:active,sqrtPriceX96:state.getSlot0[0],ticks:rows});
const positions=oldPositions.positions.filter(x=>x.assumedPermanent);
const infos=await calls(positions.map(p=>({address:view,abi,functionName:'getPositionInfo',args:[summary.poolId,p.owner,p.tickLower,p.tickUpper,p.salt]})));
const verified=positions.map((p,i)=>({owner:p.owner,tickLower:p.tickLower,tickUpper:p.tickUpper,salt:p.salt,liquidity:infos[i][0],priorLiquidity:p.liquidity,unchanged:infos[i][0]===BigInt(p.liquidity)}));
save('recovery-protocol-positions.json',{block:summary.block,positions:verified,scope:'Recheck known protocol positions; not a discovery of new positions. Custody remains assumed safe.'});
const items=[];
for(const [address,names] of [[c.licenseAuction,['auctionAnchor','licensesPerDay','MAX_PER_CHARTER_PER_DAY','startMultiplier','floorPaybackDays','lastSaleDay','currentDay','dayStartPrice','remainingToday']],[c.charterAuction,['chartersPerDay','remainingToday']]])for(const name of names)items.push({label:(address===c.licenseAuction?'license.':'charter.')+name,address,abi:parseAbi([`function ${name}() view returns(uint256)`]),functionName:name});
const outputs=await calls(items);
save('recovery-auctions.json',{block:summary.block,state:items.map((x,i)=>({label:x.label,value:outputs[i]}))});
const supportItems=[];
for(const [kind,address,names] of [['vault',c.contractionVault,['lastTickAt','paused','poolEthDepth','tickCooldown','tickVaultPctBps','effectiveTickPoolPctBps']],['bank',c.centralBank,['epochStart','epochEnd','epochNumber','epochsSettled','previousEpochFlow']],['hook',c.taxHook,['epochBoundary','epochNetFlow','settledNetFlow']]])for(const functionName of names)supportItems.push({label:kind+'.'+functionName,address,abi:read(new URL('notebook-evidence/'+kind+'-abi.json',root)),functionName});
const supportValues=await calls(supportItems),balancesWei={};
for(const name of ['contractionVault','expansionVault','feeSplitter'])balancesWei[name]=BigInt(await rpc('eth_getBalance',[c[name],tag]));
save('support-state.json',{block:summary.block,blockHash:summary.blockHash,state:supportItems.map((x,i)=>({label:x.label,value:supportValues[i]})),balancesWei});
if((await rpc('eth_getBlockByNumber',[tag,false])).hash!==target.header.hash)throw Error('Reorg');
console.log('Pinned recovery state complete:',rows.length,'ticks;',verified.length,'known protocol positions; unchanged:',verified.every(x=>x.unchanged));
