// Read-only extension of the saved canonical trade tape, with token transfers for actor attribution.
import fs from 'node:fs';
import {parseAbi,encodeFunctionData,decodeFunctionResult,decodeEventLog,keccak256,toHex} from 'viem';
const root=new URL('./',import.meta.url),packet=new URL('decision-evidence/2026-09-16T0908/',root);fs.mkdirSync(packet,{recursive:true});
const read=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const c=read('notebook-evidence/home.json').contracts,prior=read('tape-evidence/tape.json');
const raw=[];let id=0;
async function rpc(method,params){const request={jsonrpc:'2.0',id:++id,method,params};const response=await fetch('https://rpc.mainnet.chain.robinhood.com',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.timeout(45000)}).then(r=>r.json());raw.push({request,response});if(response.error)throw Error(JSON.stringify(response.error));return response.result;}
if(BigInt(await rpc('eth_chainId',[]))!==4663n)throw Error('Wrong chain');
const header=await rpc('eth_getBlockByNumber',['latest',false]),tag=header.number;
const mc=parseAbi(['function aggregate3((address target,bool allowFailure,bytes callData)[] calls) payable returns((bool success,bytes returnData)[])','function getEthBalance(address) view returns(uint256)']);
const view=parseAbi(['function getSlot0(bytes32) view returns(uint160,int24,uint24,uint24)']);
const pid='0xc73f3cd3fb68288e63f008e08ef69caa0437224e420963c6aeb4526178e87ad9';
const vault=read('notebook-evidence/vault-abi.json');
const items=[{label:'slot0',address:'0xf3334192d15450cdd385c8b70e03f9a6bd9e673b',abi:view,functionName:'getSlot0',args:[pid]},{label:'lastTickAt',address:c.contractionVault,abi:vault,functionName:'lastTickAt'},{label:'vaultETH',address:c.multicall3,abi:mc,functionName:'getEthBalance',args:[c.contractionVault]}];

const tokenABI=read('notebook-evidence/token-abi.json'),hookABI=read('notebook-evidence/hook-abi.json'),licenseABI=read('notebook-evidence/license-abi.json');
for(const address of ["0x8224c04a8f66557df682fd0581eb3724bd2bee07", "0x5638484ba2d2f1d1d35020572b0aa439a9869192", "0xa65ce1d604fa901c13aa29f2126a57d9032e412b", "0xd026f7a62fad79952d2f136ebd598a71b0053da1", "0x8c509e461bcebe90711e3eb99a6ef1f1ddde3351", "0x31caa6199d3fb1e193e968789aea8b7df4ba50af", "0xf75f2f708e489299c992349a73baec209b400aa0", "0x681d22c5e615c7a876026ceba3dc36c6dde5b97d", "0xb9e98a981adc50aacc93625990b86a6524c3d3e7", "0xe8e4eb3fe4a93b45ddc4589abdd8f8e006d0533d", "0xc2c66aec8165f0e94b692b088c5459e8ece2d493", "0xd9eb90019424e30d05b7e2a3144092225faa7b0c", "0x5140087842da3cbc55ff69ba74b4239af219c4b6", "0x2ed95f0e63ec4b4a7d33438f04b5bb25ad945915", "0x8cba145d686845b50475ab396bc0cd182a6c7e63", "0x2408ce75d217e3a70d6ca370c78c1b34d706f5a0", "0x4e0e372160ad718658ddeceda18fa5a26ecbce70", "0x85c521838790918214ee343bbbd2701107906ba2"])items.push({label:'wallet.'+address,address:c.standard,abi:tokenABI,functionName:'balanceOf',args:[address]});
for(const functionName of ['buyTaxBps','sellTaxBps','taxOverridden','taxDecayStart','taxDecayDuration'])items.push({label:functionName,address:c.taxHook,abi:hookABI,functionName});
for(const functionName of ['remainingToday','soldToday'])items.push({label:functionName,address:c.licenseAuction,abi:licenseABI,functionName});
for(const functionName of ['poolEthDepth'])items.push({label:functionName,address:c.contractionVault,abi:vault,functionName});

for(const isBuy of [true,false])items.push({label:isBuy?'buyTaxNowBps':'sellTaxNowBps',address:c.taxHook,abi:hookABI,functionName:'currentTaxBps',args:[isBuy]});
const result=await rpc('eth_call',[{to:c.multicall3,data:encodeFunctionData({abi:mc,functionName:'aggregate3',args:[items.map(x=>({target:x.address,allowFailure:false,callData:encodeFunctionData(x)}))]})},tag]);
const state=decodeFunctionResult({abi:mc,functionName:'aggregate3',data:result}).map((x,i)=>({label:items[i].label,value:decodeFunctionResult({...items[i],data:x.returnData})}));
const swap=parseAbi(['event Swap(bytes32 indexed id,address indexed sender,int128 amount0,int128 amount1,uint160 sqrtPriceX96,uint128 liquidity,int24 tick,uint24 fee)','event ModifyLiquidity(bytes32 indexed id,address indexed sender,int24 tickLower,int24 tickUpper,int256 liquidityDelta,bytes32 salt)']);
const topic=keccak256(toHex('Swap(bytes32,address,int128,int128,uint160,uint128,int24,uint24)'));const lpTopic=keccak256(toHex('ModifyLiquidity(bytes32,address,int24,int24,int256,bytes32)'));const events=[];
for(let b=Number(BigInt(prior.header.number))+1;b<=Number(BigInt(tag));b+=10000){
 for(const x of await rpc('eth_getLogs',[{address:'0x8366a39CC670B4001A1121B8F6A443A643e40951',topics:[[topic,lpTopic],pid],fromBlock:toHex(b),toBlock:toHex(Math.min(b+9999,Number(BigInt(tag))))}])){const d=decodeEventLog({abi:swap,data:x.data,topics:x.topics});events.push({...x,event:d.eventName,decoded:d.args});}
}
const transferAbi=parseAbi(['event Transfer(address indexed from,address indexed to,uint256 value)']);const transfers=[];
for(let b=Number(BigInt(prior.header.number))+1;b<=Number(BigInt(tag));b+=10000)for(const x of await rpc('eth_getLogs',[{address:c.standard,fromBlock:toHex(b),toBlock:toHex(Math.min(b+9999,Number(BigInt(tag))))}])){try{const d=decodeEventLog({abi:transferAbi,data:x.data,topics:x.topics});transfers.push({...x,decoded:d.args});}catch{}}
const headers=[prior.header,header];for(let b=Number(BigInt(prior.header.number))+5000;b<Number(BigInt(tag));b+=5000)headers.push(await rpc('eth_getBlockByNumber',[toHex(b),false]));
if((await rpc('eth_getBlockByNumber',[prior.header.number,false])).hash!==prior.header.hash||(await rpc('eth_getBlockByNumber',[tag,false])).hash!==header.hash)throw Error('Pin changed');
const vals=Object.fromEntries(state.map(x=>[x.label,x.value]));
const summary={chainId:4663,token:c.standard,header,from_header:prior.header,scope:'Price, canonical flows and buyback vault only; wallet inventories and scenarios retain the full earlier pin.',price_ETH:2**192/Number(vals.slot0[0])**2,buy_ETH:events.filter(x=>x.decoded.amount0<0n).reduce((a,x)=>a-Number(x.decoded.amount0)/1e18,0),sell_ETH:events.filter(x=>x.decoded.amount0>0n).reduce((a,x)=>a+Number(x.decoded.amount0)/1e18,0),lastTickAt:vals.lastTickAt,vault_ETH:Number(vals.vaultETH)/1e18,state,events,transfers,headers,raw};
fs.writeFileSync(new URL('tape.json',packet),JSON.stringify(summary,(_,x)=>typeof x==='bigint'?x.toString():x,2));
console.log(JSON.stringify({utc:new Date(Number(BigInt(header.timestamp))*1000).toISOString(),price_ETH:summary.price_ETH,buy_ETH:summary.buy_ETH,sell_ETH:summary.sell_ETH,lastTickAt:String(summary.lastTickAt)}));
