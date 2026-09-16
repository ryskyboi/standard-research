// Focused public-chain address attribution. No signing or transaction submission.
import fs from 'node:fs';
import {parseAbi,encodeFunctionData,decodeFunctionResult,decodeEventLog,keccak256,toHex} from 'viem';
const root=new URL('./',import.meta.url),out=new URL('buyer-investigation/',root);const read=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const targets=read('buyer-investigation/targets.json'),c=read('notebook-evidence/home.json').contracts,prior=read('decision-evidence/2026-09-16T0908/tape.json');
const raw=fs.existsSync(new URL('raw.json',out))?JSON.parse(fs.readFileSync(new URL('raw.json',out),'utf8')):[];let id=Math.max(0,...raw.map(x=>x.request.id));const cache=new Map(raw.filter(x=>x.response.result!==undefined).map(x=>[JSON.stringify([x.request.method,x.request.params]),x.response.result]));const save=(n,v)=>fs.writeFileSync(new URL(n,out),JSON.stringify(v,(_,v)=>typeof v==='bigint'?v.toString():v,2));
async function rpc(method,params){
 const key=JSON.stringify([method,params]);if(cache.has(key))return cache.get(key);
 for(let attempt=0;attempt<3;attempt++){
  await new Promise(r=>setTimeout(r,attempt?4000:1500));const request={jsonrpc:'2.0',id:++id,method,params};let response;
  try{const res=await fetch('https://rpc.mainnet.chain.robinhood.com',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.timeout(30000)});const body=await res.text();try{response=JSON.parse(body);}catch{response={error:{message:'Non-JSON HTTP '+res.status}};}}
  catch(e){response={error:{message:String(e)}};}
  raw.push({request,response});save('raw.json',raw);
  if(!response.error){cache.set(key,response.result);return response.result;}
  if(attempt===2)throw Error(JSON.stringify(response.error));
 }
}
if(BigInt(await rpc('eth_chainId',[]))!==4663n)throw Error('Wrong chain');
const header=await rpc('eth_getBlockByNumber',['latest',false]),tag=header.number;
const mc=parseAbi(['function aggregate3((address target,bool allowFailure,bytes callData)[] calls) payable returns((bool success,bytes returnData)[])','function getEthBalance(address) view returns(uint256)']);
const erc=parseAbi(['function balanceOf(address) view returns(uint256)','function decimals() view returns(uint8)','function symbol() view returns(string)','function owner() view returns(address)','function pendingOwner() view returns(address)','function ownerOf(uint256) view returns(address)']);
const bank=read('notebook-evidence/bank-abi.json');const assets={STANDARD:c.standard,WETH:'0x0bd7d308f8e1639fab988df18a8011f41eacad73',USDG:'0x5fc5360d0400a0fd4f2af552add042d716f1d168'};
const calls=[];for(const [name,address] of Object.entries(assets))for(const functionName of ['symbol','decimals'])calls.push({label:name+'.'+functionName,address,abi:erc,functionName});
for(const address of targets.addresses){
 calls.push({label:address+'.ETH',address:c.multicall3,abi:mc,functionName:'getEthBalance',args:[address]});
 for(const [name,token] of Object.entries(assets))calls.push({label:address+'.'+name,address:token,abi:erc,functionName:'balanceOf',args:[address]});
 calls.push({label:address+'.charters',address:c.charterNFT,abi:erc,functionName:'balanceOf',args:[address]});
}
for(const [name,address] of Object.entries(c))for(const functionName of ['owner','pendingOwner'])calls.push({label:'protocol.'+name+'.'+functionName,address,abi:erc,functionName});
calls.push({label:'charter738.owner',address:c.charterNFT,abi:erc,functionName:'ownerOf',args:[738n]});
for(const functionName of ['branchCountOf','pendingOf'])calls.push({label:'charter738.'+functionName,address:c.centralBank,abi:bank,functionName,args:[738n]});
const result=await rpc('eth_call',[{to:c.multicall3,data:encodeFunctionData({abi:mc,functionName:'aggregate3',args:[calls.map(x=>({target:x.address,allowFailure:true,callData:encodeFunctionData(x)}))]})},tag]);
const state=decodeFunctionResult({abi:mc,functionName:'aggregate3',data:result}).map((x,i)=>({label:calls[i].label,success:x.success,...(x.success?{value:decodeFunctionResult({...calls[i],data:x.returnData})}:{returnData:x.returnData})}));
const codes=await Promise.all(targets.addresses.map(async a=>({address:a,code:await rpc('eth_getCode',[a,tag]),nonce:await rpc('eth_getTransactionCount',[a,tag])})));
save('snapshot.json',{chainId:4663,token:c.standard,header,assets,state,codes});console.log('Snapshot',new Date(Number(BigInt(header.timestamp))*1000).toISOString(),JSON.stringify(state.slice(6,21),(_,v)=>typeof v==='bigint'?v.toString():v));
const transactions=[];for(let i=0;i<targets.transactions.length;i+=1)transactions.push(...await Promise.all(targets.transactions.slice(i,i+1).map(async tx=>({transaction:await rpc('eth_getTransactionByHash',[tx]),receipt:await rpc('eth_getTransactionReceipt',[tx])}))));save('transactions.json',transactions);
const transfer=parseAbi(['event Transfer(address indexed from,address indexed to,uint256 value)']);const logs=[];
for(let b=Number(BigInt(prior.header.number))+1;b<=Number(BigInt(tag));b+=20000){for(const x of await rpc('eth_getLogs',[{address:c.standard,fromBlock:toHex(b),toBlock:toHex(Math.min(b+19999,Number(BigInt(tag))))}])){try{x.decoded=decodeEventLog({abi:transfer,data:x.data,topics:x.topics}).args;logs.push(x);}catch{}}}
save('delta-transfers.json',logs);
// Only a narrow call trace is requested for the ambiguous large recipient.
const tx=targets.transactions.at(-1);try{save('trace.json',{tx,result:await rpc('debug_traceTransaction',[tx,{tracer:'callTracer',tracerConfig:{onlyTopCall:false}}])});}catch(e){save('trace.json',{tx,error:String(e)});}
if((await rpc('eth_getBlockByNumber',[tag,false])).hash!==header.hash)throw Error('Changed pin');
console.log('Completed focused buyer collection');
