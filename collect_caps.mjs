// Read-only checks of the branch constraints at the existing research pin.
import fs from 'node:fs';
import {encodeFunctionData,decodeFunctionResult,parseAbi,toHex} from 'viem';
const base=new URL('./notebook-evidence/',import.meta.url);
const read=n=>JSON.parse(fs.readFileSync(new URL(n,base),'utf8'));
const home=read('home.json');let block=toHex(BigInt(home.snapshot.blockNumber));
const live=process.argv.includes('--latest');
const items=[
 ['bank','centralBank','MAX_BRANCHES'],['bank','centralBank','FOUNDING_CHARTER_CAP'],
 ['license','licenseAuction','MAX_PER_CHARTER_PER_DAY'],['license','licenseAuction','dayCap'],
 ['license','licenseAuction','floorPaybackDays'],['license','licenseAuction','dayFloorPrice'],
 ['license','licenseAuction','soldToday'],['license','licenseAuction','remainingToday'],
 ['charter','charterAuction','chartersPerDay']
];
const abi=parseAbi(['function aggregate3((address target,bool allowFailure,bytes callData)[] calls) payable returns((bool success,bytes returnData)[] returnData)']);
const inputs=items.map(([kind,address,name])=>({abi:kind==='charter'?parseAbi(['function chartersPerDay() view returns(uint256)']):read(`${kind}-abi.json`),functionName:name,target:home.contracts[address]}));
const calls=inputs.map(x=>({target:x.target,allowFailure:false,callData:encodeFunctionData(x)}));
const raw=[];let id=0;
async function rpc(method,params){
 const request={jsonrpc:'2.0',id:++id,method,params};
 const response=await fetch('https://rpc.mainnet.chain.robinhood.com',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.timeout(30000)}).then(r=>r.json());
 raw.push({request,response});fs.writeFileSync(new URL('./branch-cap-read-attempt.json',import.meta.url),JSON.stringify(raw,null,2));if(response.error)throw Error(JSON.stringify(response.error));return response.result;
}
if(BigInt(await rpc('eth_chainId',[]))!==4663n)throw Error('Wrong chain');
const before=await rpc('eth_getBlockByNumber',[live?'latest':block,false]);
block=before.number;
if(!live && before.hash!==home.blockHash)throw Error('Wrong snapshot');
const encoded=await rpc('eth_call',[{to:home.contracts.multicall3,data:encodeFunctionData({abi,functionName:'aggregate3',args:[calls]})},block]);
const values=decodeFunctionResult({abi,functionName:'aggregate3',data:encoded});
const decoded=Object.fromEntries(values.map((v,i)=>[`${items[i][0]}.${items[i][2]}`,decodeFunctionResult({...inputs[i],data:v.returnData})]));
const after=await rpc('eth_getBlockByNumber',[block,false]);if(after.hash!==before.hash)throw Error('Pin changed');
const output={chainId:4663,block:BigInt(block),blockTimestamp:BigInt(before.timestamp),blockHash:before.hash,originalResearchBlock:home.snapshot.blockNumber,values:decoded,raw};
fs.writeFileSync(new URL('./branch-cap-evidence.json',import.meta.url),JSON.stringify(output,(_,v)=>typeof v==='bigint'?v.toString():v,2)+'\n');
console.log(JSON.stringify(decoded,(_,v)=>typeof v==='bigint'?v.toString():v));
