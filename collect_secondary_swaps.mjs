import fs from 'node:fs';import zlib from 'node:zlib';import {parseAbi,decodeEventLog} from 'viem';
const root=new URL('./strategy-current/',import.meta.url),target=JSON.parse(fs.readFileSync(new URL('target.json',root)));
const abi=parseAbi(['event Swap(address indexed sender,address indexed recipient,int256 amount0,int256 amount1,uint160 sqrtPriceX96,uint128 liquidity,int24 tick)']);let serial=0;const raw=[],logs=[];
async function range(a,b){
 await new Promise(r=>setTimeout(r,1600));
 const request={jsonrpc:'2.0',id:++serial,method:'eth_getLogs',params:[{address:['0xbbd8f14be91b0eab9dcc6538b8360de243c8a4ca','0x17df14744076421e165d04372f196885c6292417'],fromBlock:'0x'+a.toString(16),toBlock:'0x'+b.toString(16),topics:['0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67']}]};
 const response=await fetch('https://rpc.mainnet.chain.robinhood.com',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.timeout(45000)}).then(r=>r.json());raw.push({request,response});
 if(response.error){if((response.error.message.includes('exceeds limit')||response.error.message.includes('timed out'))){const m=Math.floor((a+b)/2);await range(a,m);await range(m+1,b);return;}throw Error(JSON.stringify(response.error));}
 logs.push(...response.result.map(x=>({...x,decoded:decodeEventLog({abi,data:x.data,topics:x.topics}).args})));
}
const end=Number(BigInt(target.header.number));for(let a=63123899;a<=end;a+=50000){await range(a,Math.min(a+49999,end));console.log('Secondary progress',a,logs.length);}
fs.writeFileSync(new URL('secondary-swaps.json.gz',root),zlib.gzipSync(JSON.stringify({raw,logs},(_,x)=>typeof x==='bigint'?x.toString():x)));console.log('Secondary Swap logs',logs.length,'requests',serial);
