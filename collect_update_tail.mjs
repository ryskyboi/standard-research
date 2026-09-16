// Final read-only price/flow check. Does not refresh wallet inventories or rerun scenarios.
import fs from 'node:fs';
import {parseAbi,encodeFunctionData,decodeFunctionResult,decodeEventLog,keccak256,toHex} from 'viem';
const root=new URL('./',import.meta.url),packet=new URL(process.argv[2].replace(/\/$/,'')+'/',root);
const read=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const c=read('notebook-evidence/home.json').contracts,prior=JSON.parse(fs.readFileSync(new URL('evidence/target.json',packet)));
const raw=[];let id=0;
async function rpc(method,params){const request={jsonrpc:'2.0',id:++id,method,params};const response=await fetch('https://rpc.mainnet.chain.robinhood.com',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.timeout(45000)}).then(r=>r.json());raw.push({request,response});if(response.error)throw Error(JSON.stringify(response.error));return response.result;}
if(BigInt(await rpc('eth_chainId',[]))!==4663n)throw Error('Wrong chain');
const header=await rpc('eth_getBlockByNumber',['latest',false]),tag=header.number;
const mc=parseAbi(['function aggregate3((address target,bool allowFailure,bytes callData)[] calls) payable returns((bool success,bytes returnData)[])','function getEthBalance(address) view returns(uint256)']);
const view=parseAbi(['function getSlot0(bytes32) view returns(uint160,int24,uint24,uint24)']);
const pid='0xc73f3cd3fb68288e63f008e08ef69caa0437224e420963c6aeb4526178e87ad9';
const vault=read('notebook-evidence/vault-abi.json');
const items=[{label:'slot0',address:'0xf3334192d15450cdd385c8b70e03f9a6bd9e673b',abi:view,functionName:'getSlot0',args:[pid]},{label:'lastTickAt',address:c.contractionVault,abi:vault,functionName:'lastTickAt'},{label:'vaultETH',address:c.multicall3,abi:mc,functionName:'getEthBalance',args:[c.contractionVault]}];
const result=await rpc('eth_call',[{to:c.multicall3,data:encodeFunctionData({abi:mc,functionName:'aggregate3',args:[items.map(x=>({target:x.address,allowFailure:false,callData:encodeFunctionData(x)}))]})},tag]);
const state=decodeFunctionResult({abi:mc,functionName:'aggregate3',data:result}).map((x,i)=>({label:items[i].label,value:decodeFunctionResult({...items[i],data:x.returnData})}));
const swap=parseAbi(['event Swap(bytes32 indexed id,address indexed sender,int128 amount0,int128 amount1,uint160 sqrtPriceX96,uint128 liquidity,int24 tick,uint24 fee)']);
const topic=keccak256(toHex('Swap(bytes32,address,int128,int128,uint160,uint128,int24,uint24)'));const events=[];
for(let b=Number(BigInt(prior.header.number))+1;b<=Number(BigInt(tag));b+=10000){
 for(const x of await rpc('eth_getLogs',[{address:'0x8366a39CC670B4001A1121B8F6A443A643e40951',topics:[topic,pid],fromBlock:toHex(b),toBlock:toHex(Math.min(b+9999,Number(BigInt(tag))))}])){const d=decodeEventLog({abi:swap,data:x.data,topics:x.topics});events.push({...x,decoded:d.args});}
}
if((await rpc('eth_getBlockByNumber',[prior.header.number,false])).hash!==prior.header.hash||(await rpc('eth_getBlockByNumber',[tag,false])).hash!==header.hash)throw Error('Pin changed');
const vals=Object.fromEntries(state.map(x=>[x.label,x.value]));
const summary={chainId:4663,token:c.standard,header,from_header:prior.header,scope:'Price, canonical flows and buyback vault only; wallet inventories and scenarios retain the full earlier pin.',price_ETH:2**192/Number(vals.slot0[0])**2,buy_ETH:events.filter(x=>x.decoded.amount0<0n).reduce((a,x)=>a-Number(x.decoded.amount0)/1e18,0),sell_ETH:events.filter(x=>x.decoded.amount0>0n).reduce((a,x)=>a+Number(x.decoded.amount0)/1e18,0),lastTickAt:vals.lastTickAt,vault_ETH:Number(vals.vaultETH)/1e18,state,events,raw};
fs.writeFileSync(new URL('tail-check.json',packet),JSON.stringify(summary,(_,x)=>typeof x==='bigint'?x.toString():x,2));
console.log(JSON.stringify({utc:new Date(Number(BigInt(header.timestamp))*1000).toISOString(),price_ETH:summary.price_ETH,buy_ETH:summary.buy_ETH,sell_ETH:summary.sell_ETH,lastTickAt:String(summary.lastTickAt)}));
