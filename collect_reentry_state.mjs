// Refresh positions, available native ETH, Charters and liquidity at ONE pin.
import fs from 'node:fs';import zlib from 'node:zlib';
import {parseAbi,encodeFunctionData,decodeFunctionResult,decodeEventLog,keccak256,toHex} from 'viem';
const root=new URL('./',import.meta.url),dir=new URL('./reentry-evidence/',root);fs.mkdirSync(dir,{recursive:true});
const read=p=>JSON.parse(fs.readFileSync(p,'utf8')),base=new URL('notebook-evidence/',root),home=read(new URL('home.json',base)),c=home.contracts;
const prior=read(new URL('strategy-current/target.json',root));
const old={block:Number(BigInt(prior.header.number)),holders:read(new URL('strategy-current/wallet-balances.json',root)).filter(x=>x.label.endsWith('.token')&&BigInt(x.value)>0n).map(x=>({address:x.label.slice(0,-6),balance:x.value}))};
const save=(n,v)=>fs.writeFileSync(new URL(n,dir),JSON.stringify(v,(_,x)=>typeof x==='bigint'?x.toString():x,2));
let serial=0;
async function rpc(method,params){
 for(let a=0;a<4;a++){
  await new Promise(r=>setTimeout(r,1500+(a?3000*2**(a-1):0)));
  const request={jsonrpc:'2.0',id:++serial,method,params};
  const response=await fetch('https://rpc.mainnet.chain.robinhood.com',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.timeout(30000)}).then(r=>r.json());
  fs.writeFileSync(new URL(`rpc-${String(serial).padStart(4,'0')}.json.gz`,dir),zlib.gzipSync(JSON.stringify({request,response})));
  if(response.error){if(a<3&&response.error.code===429)continue;throw Error(JSON.stringify(response.error));}return response.result;
 }
}
if(BigInt(await rpc('eth_chainId',[]))!==4663n)throw Error('Wrong chain');
const header=await rpc('eth_getBlockByNumber',['latest',false]),tag=header.number,end=Number(BigInt(tag));
save('target.json',{chainId:4663,token:c.standard,header,priorHolderBlock:old.block,status:'collecting'});
console.log('Fresh pin',end,new Date(Number(BigInt(header.timestamp))*1000).toISOString());
const mc=parseAbi(['function aggregate3((address target,bool allowFailure,bytes callData)[] calls) payable returns((bool success,bytes returnData)[] returnData)','function getEthBalance(address) view returns(uint256)']);
async function calls(items){const results=[];for(let i=0;i<items.length;i+=500){
 const group=items.slice(i,i+500),raw=await rpc('eth_call',[{to:c.multicall3,data:encodeFunctionData({abi:mc,functionName:'aggregate3',args:[group.map(x=>({target:x.address,allowFailure:true,callData:encodeFunctionData(x)}))]})},tag]);
 const out=decodeFunctionResult({abi:mc,functionName:'aggregate3',data:raw});
 results.push(...out.map((x,j)=>({label:group[j].label,...(x.success?{value:decodeFunctionResult({...group[j],data:x.returnData})}:{error:x.returnData})})));
 }return results;}
const abis=Object.fromEntries(['bank','hook','license','token','vault'].map(n=>[n,read(new URL(n+'-abi.json',base))]));
const items=[];
abis.splitter=read(new URL('reentry-abi/splitter.json',root));abis.charter=read(new URL('reentry-abi/charter.json',root));
for(const [kind,address] of [['token',c.standard],['bank',c.centralBank],['hook',c.taxHook],['license',c.licenseAuction],['vault',c.contractionVault],['splitter',c.feeSplitter],['charterNFT',c.charterNFT]]){
 const abi=kind==='charterNFT'?abis.charter:abis[kind];
 for(const f of abi.filter(x=>x.type==='function'&&x.stateMutability==='view'&&x.inputs.length===0))items.push({label:kind+'.'+f.name,address,abi,functionName:f.name});
}
const assets={wrapped:'0x5fc5360d0400a0fd4f2af552add042d716f1d168',routed:'0x0bd7d308f8e1639fab988df18a8011f41eacad73'};
const erc=parseAbi(['function name() view returns(string)','function symbol() view returns(string)','function decimals() view returns(uint8)','function balanceOf(address) view returns(uint256)']);
for(const [label,address] of Object.entries(assets))for(const functionName of ['name','symbol','decimals'])items.push({label:'asset.'+label+'.'+functionName,address,abi:erc,functionName});
const poolId='0xc73f3cd3fb68288e63f008e08ef69caa0437224e420963c6aeb4526178e87ad9',view='0xf3334192d15450cdd385c8b70e03f9a6bd9e673b';
const va=parseAbi(['function getSlot0(bytes32) view returns(uint160,int24,uint24,uint24)','function getLiquidity(bytes32) view returns(uint128)','function getTickBitmap(bytes32,int16) view returns(uint256)','function getTickLiquidity(bytes32,int24) view returns(uint128,int128)']);
for(const functionName of ['getSlot0','getLiquidity'])items.push({label:functionName,address:view,abi:va,functionName,args:[poolId]});
c.polManager='0x242F3e67BEf43470C2434d95E7D618E19f87c8f8';
for(const n of ['contractionVault','expansionVault','feeSplitter','taxHook','polManager','centralBank','genesisMinter','charterAuction'])items.push({label:'balance.'+n,address:c.multicall3,abi:mc,functionName:'getEthBalance',args:[c[n]]});
items.push({label:'charter.chartersPerDay',address:c.charterAuction,abi:parseAbi(['function chartersPerDay() view returns(uint256)']),functionName:'chartersPerDay'});
const state=await calls(items);save('state.json',state);const vals=Object.fromEntries(state.map(x=>[x.label,x.value]));
const registry=vals['vault.registry'];
const registryAbi=parseAbi(['function executionPermissionless() view returns(bool)','function owner() view returns(address)','function contractionVault() view returns(address)','function expansionVault() view returns(address)','function polManager() view returns(address)']);
save('registry.json',await calls(['executionPermissionless','owner','contractionVault','expansionVault','polManager'].map(functionName=>({label:functionName,address:registry,abi:registryAbi,functionName}))));
if(vals['token.symbol']!=='STANDARD'||Number(vals['token.decimals'])!==18)throw Error('Wrong metadata');
const days=Math.floor((Number(BigInt(header.timestamp))-Number(vals['bank.genesisTime']))/86400);
save('withdrawals.json',await calls(Array.from({length:Math.min(days+1,7)},(_,i)=>({label:'withdrawn.'+(days-i),address:c.centralBank,abi:abis.bank,functionName:'withdrawnOnDay',args:[BigInt(days-i)]}))));
const words=Array.from({length:36},(_,i)=>i-18);
const bits=await calls(words.map(w=>({label:String(w),address:view,abi:va,functionName:'getTickBitmap',args:[poolId,w]})));
const ticks=[];for(let i=0;i<words.length;i++)for(let b=0;b<256;b++)if(BigInt(bits[i].value)&(1n<<BigInt(b)))ticks.push((words[i]*256+b)*200);
const liqs=await calls(ticks.map(t=>({label:String(t),address:view,abi:va,functionName:'getTickLiquidity',args:[poolId,t]})));
const rows=ticks.map((tick,i)=>({tick,liquidityGross:liqs[i].value[0],liquidityNet:liqs[i].value[1]}));
if(rows.reduce((s,x)=>s+x.liquidityNet,0n)!==0n||rows.filter(x=>x.tick<=vals.getSlot0[1]).reduce((s,x)=>s+x.liquidityNet,0n)!==vals.getLiquidity)throw Error('Liquidity mismatch');
save('liquidity.json',{block:end,blockHash:header.hash,poolId,sqrtPriceX96:vals.getSlot0[0],ticks:rows});
const transferAbi=parseAbi(['event Transfer(address indexed from,address indexed to,uint256 value)']);
const poolAbi=parseAbi(['event Swap(bytes32 indexed id,address indexed sender,int128 amount0,int128 amount1,uint160 sqrtPriceX96,uint128 liquidity,int24 tick,uint24 fee)','event ModifyLiquidity(bytes32 indexed id,address indexed sender,int24 tickLower,int24 tickUpper,int256 liquidityDelta,bytes32 salt)']);
const econAbi=[...abis.bank.filter(x=>x.type==='event'&&['Deposited','BranchesOpened','Withdrawn','EpochSettled'].includes(x.name)),...abis.license.filter(x=>x.type==='event'&&x.name==='LicensesPurchased')];
const sig=x=>keccak256(toHex(x.name+'('+x.inputs.map(y=>y.type).join(',')+')'));
const transfers=[],events=[];
for(let b=old.block+1;b<=end;b+=10000){
 const range={fromBlock:toHex(b),toBlock:toHex(Math.min(end,b+9999))};
 for(const [filter,abi,out] of [[{address:c.standard,topics:[transferAbi.map(sig)]},transferAbi,transfers],[{address:'0x8366a39CC670B4001A1121B8F6A443A643e40951',topics:[poolAbi.map(sig),poolId]},poolAbi,events]]){
  for(const x of await rpc('eth_getLogs',[{...filter,...range}])){if(x.removed)throw Error('Removed log');const d=decodeEventLog({abi,data:x.data,topics:x.topics});out.push({...x,event:d.eventName,decoded:d.args});}
 }
}
for(let b=old.block+1;b<=end;b+=50000)for(const x of await rpc('eth_getLogs',[{address:[c.centralBank,c.licenseAuction],topics:[econAbi.map(sig)],fromBlock:toHex(b),toBlock:toHex(Math.min(end,b+49999))}])){const d=decodeEventLog({abi:econAbi,data:x.data,topics:x.topics});events.push({...x,event:d.eventName,decoded:d.args});}
const zip=(n,v)=>fs.writeFileSync(new URL(n,dir),zlib.gzipSync(JSON.stringify(v,(_,x)=>typeof x==='bigint'?x.toString():x)));
zip('delta-transfers.json.gz',transfers);zip('delta-events.json.gz',events);
const balances=new Map(old.holders.map(x=>[x.address.toLowerCase(),BigInt(x.balance)])),zero='0x0000000000000000000000000000000000000000';
for(const x of transfers){const d=x.decoded,a=d.from.toLowerCase(),b=d.to.toLowerCase();if(a!==zero)balances.set(a,(balances.get(a)||0n)-d.value);if(b!==zero)balances.set(b,(balances.get(b)||0n)+d.value);}
if([...balances.values()].some(x=>x<0n)||[...balances.values()].reduce((a,b)=>a+b,0n)!==vals['token.totalSupply'])throw Error('Current replay mismatch');
const charterAbi=parseAbi(['function ownerOf(uint256) view returns(address)']);
const charterItems=[];for(let id=1;id<=Number(vals['charterNFT.nextId']);id++){for(const functionName of ['branchCountOf','pendingOf'])charterItems.push({label:id+'.'+functionName,address:c.centralBank,abi:abis.bank,functionName,args:[BigInt(id)]});charterItems.push({label:id+'.ownerOf',address:c.charterNFT,abi:charterAbi,functionName:'ownerOf',args:[BigInt(id)]});}
const charters=await calls(charterItems);save('charters.json',charters);
const addresses=new Set([...balances].filter(([a,b])=>b>0n).map(([a])=>a));
for(const x of charters)if(x.label.endsWith('.ownerOf')&&x.value)addresses.add(x.value.toLowerCase());
// Include recent net sellers even when their remaining token balance is zero.
for(const x of transfers){addresses.add(x.decoded.from.toLowerCase());addresses.add(x.decoded.to.toLowerCase());}addresses.delete(zero);
for(const address of read(new URL('reentry-abi/recent-addresses.json',root)))addresses.add(address);
const wallets=[...addresses];console.log('Reading ETH and token balances for',wallets.length,'addresses');
const walletItems=wallets.flatMap(address=>[{label:address+'.eth',address:c.multicall3,abi:mc,functionName:'getEthBalance',args:[address]},{label:address+'.token',address:c.standard,abi:abis.token,functionName:'balanceOf',args:[address]},...Object.entries(assets).map(([label,asset])=>({label:address+'.'+label,address:asset,abi:erc,functionName:'balanceOf',args:[address]}))]);
const observed=await calls(walletItems);save('wallet-balances.json',observed);
if(observed.some(x=>x.error))throw Error('Wallet balance read failed');
for(const x of observed.filter(x=>x.label.endsWith('.token'))){const address=x.label.slice(0,-6);if(x.value!==(balances.get(address)||0n))throw Error('Individual token replay mismatch '+address);}
// Interval headers for event timing; event timestamps are interpolated between these.
const headerBlocks=new Set();
for(let b=old.block;b<end;b+=10000)headerBlocks.add(toHex(b));headerBlocks.add(tag);
const headers=[];for(const b of headerBlocks)headers.push(await rpc('eth_getBlockByNumber',[b,false]));save('headers.json',headers);
const final=await rpc('eth_getBlockByNumber',[tag,false]);if(final.hash!==header.hash)throw Error('Reorg');
save('target.json',{chainId:4663,token:c.standard,header,priorHolderBlock:old.block,status:'complete',walletCount:wallets.length,allWalletTokenBalancesReconciled:true,scope:'Native ETH plus two identified routed ERC20 balances measured. They are held assets, not committed buying budgets; external inflows and other assets unmeasured. Known protocol custody excluded downstream.'});
console.log('Complete fresh actor snapshot:',end,wallets.length,'addresses; every token balance reconciled.');
