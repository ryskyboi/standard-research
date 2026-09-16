// Public, read-only finite polling. Each sample is pinned and independently saved.
import fs from 'node:fs';import zlib from 'node:zlib';import {spawnSync} from 'node:child_process';
import {parseAbi,encodeFunctionData,decodeFunctionResult,decodeEventLog,keccak256,toHex} from 'viem';
const root=new URL('./',import.meta.url).pathname;
const read=p=>JSON.parse(fs.readFileSync(root+p,'utf8'));
const args=process.argv.slice(2);const option=(name,fallback)=>{const i=args.indexOf(name);return i<0?fallback:Number(args[i+1]);};
const samples=option('--samples',1),interval=option('--interval',300);
if(!Number.isInteger(samples)||samples<1||samples>1000||!Number.isFinite(interval)||interval<30)throw Error('Use --samples 1..1000 and --interval >=30 seconds');
const base=read('reentry-evidence/target.json'),c=read('notebook-evidence/home.json').contracts;
const home=root+'seller-monitor/';fs.mkdirSync(home,{recursive:true});
const abis=Object.fromEntries(['token','bank','hook','vault'].map(n=>[n,read('notebook-evidence/'+n+'-abi.json')]));
const transfer=parseAbi(['event Transfer(address indexed from,address indexed to,uint256 value)']);
const pools=parseAbi(['event Swap(bytes32 indexed id,address indexed sender,int128 amount0,int128 amount1,uint160 sqrtPriceX96,uint128 liquidity,int24 tick,uint24 fee)','event ModifyLiquidity(bytes32 indexed id,address indexed sender,int24 tickLower,int24 tickUpper,int256 liquidityDelta,bytes32 salt)']);
const secondary=parseAbi(['event Swap(address indexed sender,address indexed recipient,int256 amount0,int256 amount1,uint160 sqrtPriceX96,uint128 liquidity,int24 tick)']);
const mc=parseAbi(['function aggregate3((address target,bool allowFailure,bytes callData)[] calls) payable returns((bool success,bytes returnData)[])','function getEthBalance(address) view returns(uint256)']);
const registry=parseAbi(['function executionPermissionless() view returns(bool)']);
const view=parseAbi(['function getSlot0(bytes32) view returns(uint160,int24,uint24,uint24)']);
const pid='0xc73f3cd3fb68288e63f008e08ef69caa0437224e420963c6aeb4526178e87ad9';
const sig=x=>keccak256(toHex(x.name+'('+x.inputs.map(y=>y.type).join(',')+')'));
const stringify=x=>JSON.stringify(x,(_,v)=>typeof v==='bigint'?v.toString():v,2);
for(let iteration=0;iteration<samples;iteration++){
 const started=Date.now(),raw=[];let id=0;
 async function rpc(method,params){for(let a=0;a<5;a++){
  await new Promise(r=>setTimeout(r,1300+a*3000));const request={jsonrpc:'2.0',id:++id,method,params};
  const response=await fetch('https://rpc.mainnet.chain.robinhood.com',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.timeout(45000)}).then(r=>r.json());raw.push({request,response});
  if(response.error?.code===429)continue;if(response.error)throw Error(JSON.stringify(response.error));return response.result;
 }throw Error('RPC retries exhausted');}
 if(BigInt(await rpc('eth_chainId',[]))!==4663n)throw Error('Wrong chain');
 const header=await rpc('eth_getBlockByNumber',['latest',false]),tag=header.number,end=Number(BigInt(tag));
 const priorDirs=fs.readdirSync(home).filter(n=>fs.existsSync(home+n+'/target.json')).sort();
 const previous=priorDirs.length?JSON.parse(fs.readFileSync(home+priorDirs.at(-1)+'/target.json')):base;
 if(previous.status&&previous.status!=='complete')throw Error('Previous snapshot incomplete');
 const begin=Number(BigInt(previous.header.number))+1;
 const previousCheck=await rpc('eth_getBlockByNumber',[previous.header.number,false]);if(previousCheck.hash!==previous.header.hash)throw Error('Prior pin reorg; rebuild monitoring chain');
 const folder=home+new Date(Number(BigInt(header.timestamp))*1000).toISOString().replaceAll(':','-')+'/';fs.mkdirSync(folder,{recursive:true});
 const save=(name,value)=>fs.writeFileSync(folder+name,name.endsWith('.gz')?zlib.gzipSync(stringify(value)):stringify(value));
 save('target.json',{chainId:4663,token:c.standard,header,previousBlock:begin-1,status:'collecting'});
 const items=[];
 for(const [kind,address,names] of [['token',c.standard,['totalSupply','decimals']],['bank',c.centralBank,['totalBranches','totalPendingLive']],['hook',c.taxHook,['buyTaxBps','sellTaxBps','epochNetFlow']],['vault',c.contractionVault,['lastTickAt','paused','poolEthDepth','tickVaultPctBps','effectiveTickPoolPctBps','tickCooldown']]])for(const functionName of names)items.push({label:kind+'.'+functionName,address,abi:abis[kind],functionName});
 items.push({label:'vaultETH',address:c.multicall3,abi:mc,functionName:'getEthBalance',args:[c.contractionVault]},{label:'permissionless',address:'0x855C294dD019E9e0d84C058cFF7404f5F2dDCa4b',abi:registry,functionName:'executionPermissionless'},{label:'slot0',address:'0xf3334192d15450cdd385c8b70e03f9a6bd9e673b',abi:view,functionName:'getSlot0',args:[pid]});
 const call=await rpc('eth_call',[{to:c.multicall3,data:encodeFunctionData({abi:mc,functionName:'aggregate3',args:[items.map(x=>({target:x.address,allowFailure:false,callData:encodeFunctionData(x)}))]})},tag]);
 const state=decodeFunctionResult({abi:mc,functionName:'aggregate3',data:call}).map((x,i)=>({label:items[i].label,value:decodeFunctionResult({...items[i],data:x.returnData})}));save('state.json',state);
 if(state.find(x=>x.label==='token.decimals').value!==18)throw Error('Decimals mismatch');
 const transfers=[],events=[],other=[];
 for(let b=begin;b<=end;b+=10000)for(const [filter,abi,dest] of [[{address:c.standard,topics:[transfer.map(sig)]},transfer,transfers],[{address:'0x8366a39CC670B4001A1121B8F6A443A643e40951',topics:[pools.map(sig),pid]},pools,events]]){
  for(const x of await rpc('eth_getLogs',[{...filter,fromBlock:toHex(b),toBlock:toHex(Math.min(end,b+9999))}])){if(x.removed)throw Error('Removed log');const d=decodeEventLog({abi,data:x.data,topics:x.topics});dest.push({...x,event:d.eventName,decoded:d.args});}
 }
 const bankEvents=abis.bank.filter(x=>x.type==='event'&&['Withdrawn','Revoked','Deposited','BranchesOpened'].includes(x.name));
 for(let b=begin;b<=end;b+=50000)for(const [filter,abi,dest] of [[{address:c.centralBank,topics:[bankEvents.map(sig)]},bankEvents,events],[{address:['0xbbd8f14be91b0eab9dcc6538b8360de243c8a4ca','0x17df14744076421e165d04372f196885c6292417'],topics:[secondary.map(sig)]},secondary,other],[{address:c.contractionVault},abis.vault,events]]){
  for(const x of await rpc('eth_getLogs',[{...filter,fromBlock:toHex(b),toBlock:toHex(Math.min(end,b+49999))}])){const d=decodeEventLog({abi,data:x.data,topics:x.topics});dest.push({...x,event:d.eventName,decoded:d.args});}
 }
 const final=await rpc('eth_getBlockByNumber',[tag,false]);if(final.hash!==header.hash)throw Error('Pin reorg');
 save('transfers.json.gz',transfers);save('events.json.gz',events);save('secondary.json.gz',other);save('raw.json.gz',raw);
 save('target.json',{chainId:4663,token:c.standard,header,previousBlock:begin-1,status:'complete'});
 const analysis=spawnSync('python3',[root+'seller_monitor.py'],{cwd:root,stdio:'inherit'});if(analysis.status!==0)throw Error('Analysis failed');
 console.log('Poll complete:',folder);
 if(iteration+1<samples)await new Promise(r=>setTimeout(r,Math.max(0,interval*1000-(Date.now()-started))));
}
