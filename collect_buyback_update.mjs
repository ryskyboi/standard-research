import fs from 'node:fs';
import {parseAbi,encodeFunctionData,decodeFunctionResult,decodeErrorResult,decodeEventLog,toHex} from 'viem';
const root=new URL('./',import.meta.url).pathname;
const read=p=>JSON.parse(fs.readFileSync(root+p,'utf8'));
const c=read('notebook-evidence/home.json').contracts,old=read('reentry-evidence/target.json');
const abis=Object.fromEntries(['token','bank','vault','hook'].map(n=>[n,read('notebook-evidence/'+n+'-abi.json')]));
const mc=parseAbi(['function aggregate3((address target,bool allowFailure,bytes callData)[] calls) payable returns((bool success,bytes returnData)[])','function getEthBalance(address) view returns(uint256)']);
const reg=parseAbi(['function executionPermissionless() view returns(bool)']);
const raw=[];let id=0;
async function rpc(method,params){for(let i=0;i<5;i++){await new Promise(r=>setTimeout(r,1200+i*3000));const request={jsonrpc:'2.0',id:++id,method,params};const response=await fetch('https://rpc.mainnet.chain.robinhood.com',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.timeout(30000)}).then(r=>r.json());raw.push({request,response});if(response.error?.code===429)continue;return response;}throw Error('RPC throttled');}
if(BigInt((await rpc('eth_chainId',[])).result)!==4663n)throw Error('Wrong chain');
const header=(await rpc('eth_getBlockByNumber',['latest',false])).result,tag=header.number;const items=[];
for(const [kind,address,names] of [['token',c.standard,['totalSupply','decimals']],['bank',c.centralBank,['totalPendingLive','totalBranches','epochEnd']],['hook',c.taxHook,['epochNetFlow','twapTick','currentTick']],['vault',c.contractionVault,['owner','registry','paused','lastTickAt','tickCooldown','tickVaultPctBps','effectiveTickPoolPctBps','poolEthDepth','effectiveTwapDeviationTicks']]])for(const functionName of names)items.push({label:kind+'.'+functionName,address,abi:abis[kind],functionName});
const pol='0x242f3e67bef43470c2434d95e7d618e19f87c8f8',pool='0x8366a39cc670b4001a1121b8f6a443a643e40951';
const custody=[...new Set([...Object.values(c),pol,pool,'0xbbd8f14be91b0eab9dcc6538b8360de243c8a4ca','0x17df14744076421e165d04372f196885c6292417','0x65ee0e9d98ed1564655ac51d78ffd6ef61f66404'].map(x=>x.toLowerCase()))];
for(const address of custody)items.push({label:'custody.'+address,address:c.standard,abi:abis.token,functionName:'balanceOf',args:[address]});
for(const [n,address] of Object.entries({vault:c.contractionVault,hook:c.taxHook,splitter:c.feeSplitter,expansion:c.expansionVault,POL:pol}))items.push({label:'ETH.'+n,address:c.multicall3,abi:mc,functionName:'getEthBalance',args:[address]});
items.push({label:'executionPermissionless',address:'0x855C294dD019E9e0d84C058cFF7404f5F2dDCa4b',abi:reg,functionName:'executionPermissionless'});
const r=await rpc('eth_call',[{to:c.multicall3,data:encodeFunctionData({abi:mc,functionName:'aggregate3',args:[items.map(x=>({target:x.address,allowFailure:true,callData:encodeFunctionData(x)}))]})},tag]);
if(r.error)throw Error(JSON.stringify(r.error));
const state=decodeFunctionResult({abi:mc,functionName:'aggregate3',data:r.result}).map((x,i)=>({label:items[i].label,...(x.success?{value:decodeFunctionResult({...items[i],data:x.returnData})}:{error:x.returnData})}));
if(state.some(x=>x.error))throw Error('State call failed');
const s=Object.fromEntries(state.map(x=>[x.label,x.value]));
const checks=[];for(const [label,from] of [['public','0x0000000000000000000000000000000000001234'],['owner_counterfactual',s['vault.owner']]]){const result=await rpc('eth_call',[{to:c.contractionVault,from,data:encodeFunctionData({abi:abis.vault,functionName:'buybackTick'})},tag]);let decoded;try{decoded=decodeErrorResult({abi:abis.vault,data:result.error?.data}).errorName;}catch{}checks.push({label,from,result,decoded});}
const events=[];for(let b=Number(BigInt(old.header.number))+1;b<=Number(BigInt(tag));b+=100000){const r=await rpc('eth_getLogs',[{address:c.contractionVault,fromBlock:toHex(b),toBlock:toHex(Math.min(Number(BigInt(tag)),b+99999))}]);if(r.error)throw Error(JSON.stringify(r.error));for(const x of r.result){const d=decodeEventLog({abi:abis.vault,data:x.data,topics:x.topics});events.push({...x,event:d.eventName,decoded:d.args});}}
const held=state.filter(x=>x.label.startsWith('custody.')).reduce((a,x)=>a+x.value,0n);
const summary={timestampUTC:new Date(Number(BigInt(header.timestamp))*1000).toISOString(),block:Number(BigInt(tag)),supply:Number(s['token.totalSupply'])/1e18,knownCustodyTokens:Number(held)/1e18,outsideKnownCustody:Number(s['token.totalSupply']-held)/1e18,bankPending:Number(s['bank.totalPendingLive'])/1e18,poolManagerTokens:Number(s['custody.'+pool])/1e18,firstTickETH:Math.min(Number(s['ETH.vault'])*Number(s['vault.tickVaultPctBps'])/10000,Number(s['vault.poolEthDepth'])*Number(s['vault.effectiveTickPoolPctBps'])/10000)/1e18};
const output={header,state,checks,events,summary,raw};const stringify=x=>JSON.stringify(x,(_,v)=>typeof v==='bigint'?v.toString():v,2);
const dir=root+'buyback-updates/';fs.mkdirSync(dir,{recursive:true});const file=dir+summary.timestampUTC.replaceAll(':','-')+'.json';fs.writeFileSync(file,stringify(output));console.log(stringify({file,state:state.filter(x=>!x.label.startsWith('custody.')),checks,events,summary}));
