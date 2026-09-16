import fs from 'node:fs';
const file=new URL('./strategy-current/routes.json',import.meta.url);let i=0,rows=[];
async function rpc(method,params){await new Promise(r=>setTimeout(r,1600));const request={jsonrpc:'2.0',id:++i,method,params};const response=await fetch('https://rpc.mainnet.chain.robinhood.com',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.timeout(30000)}).then(x=>x.json());rows.push({request,response});fs.writeFileSync(file,JSON.stringify(rows));return response.result;}
const header=await rpc('eth_getBlockByNumber',['latest',false]);
for(const to of ['0xbbd8f14be91b0eab9dcc6538b8360de243c8a4ca','0x65ee0e9d98ed1564655ac51d78ffd6ef61f66404','0x17df14744076421e165d04372f196885c6292417'])for(const data of ['0x0dfe1681','0xd21220a7','0xc45a0155'])await rpc('eth_call',[{to,data},header.number]);
for(const tx of ['0xd37d6413fd5aba87750143e94da9a1fcaec3bf274bc6ed224b18c160eb676e51','0x117b0ae19cee9b6e133a6bfe8a11d52096293e2ad3fced662a2a82b512f48e97','0x5d006335b0144f8bfb03c6a7a326fe35e5270578cabaf3ec0222d5df3887df1a'])await rpc('eth_getTransactionReceipt',[tx]);
console.log('Route evidence',rows.length,header.number);
