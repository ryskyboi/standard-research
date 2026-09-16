// Read-only exact headers and transaction envelopes for the documented burst.
import fs from 'node:fs';
const root=new URL('tape-evidence/',import.meta.url);
const q=JSON.parse(fs.readFileSync(new URL('detail-requests.json',root),'utf8'));
const raw=[];let id=0;
for(const [method,args] of [
 ['eth_chainId',[]],
 ...q.blocks.map(b=>['eth_getBlockByNumber',['0x'+b.toString(16),false]]),
 ...q.transactions.map(tx=>['eth_getTransactionByHash',[tx]])
]){
 const request={jsonrpc:'2.0',id:++id,method,params:args};
 const response=await fetch('https://rpc.mainnet.chain.robinhood.com',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request),signal:AbortSignal.timeout(30000)}).then(r=>r.json());
 if(response.error||!response.result)throw Error('Missing RPC result for '+method);
 if(method==='eth_chainId'&&BigInt(response.result)!==4663n)throw Error('Wrong chain');
 raw.push({request,response});
}
fs.writeFileSync(new URL('details.json',root),JSON.stringify(raw,null,2));
console.log('Saved '+raw.length+' read-only responses');
