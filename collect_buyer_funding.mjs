import fs from 'node:fs';import {keccak256,toHex,decodeEventLog,parseAbi} from 'viem';
const root=new URL('buyer-investigation/',import.meta.url),read=n=>JSON.parse(fs.readFileSync(new URL(n,root),'utf8')),snapshot=read('snapshot.json'),targets=read('targets.json');const raw=[];let id=0;
async function rpc(method,params){await new Promise(r=>setTimeout(r,1600));const request={jsonrpc:'2.0',id:++id,method,params};let response;try{const r=await fetch('https://rpc.mainnet.chain.robinhood.com',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.timeout(30000)});response=await r.json();}catch(e){response={error:{message:String(e)}};}raw.push({request,response});fs.writeFileSync(new URL('funding-raw.json',root),JSON.stringify(raw,null,2));return response;}
const pin=Number(BigInt(snapshot.header.number));
await rpc('trace_filter',[{fromBlock:toHex(pin-150000),toBlock:snapshot.header.number,toAddress:targets.addresses,after:0,count:100}]);
const sig=keccak256(toHex('Transfer(address,address,uint256)'));const router='0x5399d94d2cab7c252a6034042e1917a0e5e17a18';
const rows=[];for(let b=pin-150000;b<=pin;b+=50000){const x=await rpc('eth_getLogs',[{address:snapshot.assets.USDG,topics:[sig,null,'0x'+router.slice(2).padStart(64,'0')],fromBlock:toHex(b),toBlock:toHex(Math.min(pin,b+49999))}]);if(x.result)rows.push(...x.result);}
const abi=parseAbi(['event Transfer(address indexed from,address indexed to,uint256 value)']);for(const x of rows)x.decoded=decodeEventLog({abi,data:x.data,topics:x.topics}).args;
fs.writeFileSync(new URL('router-usdg-incoming.json',root),JSON.stringify(rows,(_,v)=>typeof v==='bigint'?v.toString():v,2));console.log('Router USDG funding logs',rows.length,'Trace filter',raw[0].response.error||'supported');
