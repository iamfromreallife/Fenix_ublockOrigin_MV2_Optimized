import assert from 'node:assert/strict';
import fs from 'node:fs';
import { performance } from 'node:perf_hooks';
import { TextEncoder } from 'node:util';
const base=decodeURIComponent(new URL('../',import.meta.url).pathname);
function factory(path) {
  const source=fs.readFileSync(base+path+'/js/resources/scriptlets.js','utf8');
  const start=source.indexOf('    const streamWatchResponse = responseBefore => {');
  const end=source.indexOf('\n    self.fetch = new Proxy(self.fetch, {',start);
  assert(start>=0 && end>start, 'Watch stream function must exist');
  return new Function('safe','logPrefix',source.slice(start,end)+'\nreturn streamWatchResponse;')({uboLog(){}},'test');
}
const original=factory('base');
const improved=factory('optimized');
const needle=new TextEncoder().encode('"adSlots"');
const repl=new TextEncoder().encode('"no_ads"');
function expected(bytes){
  const pos=Buffer.from(bytes).indexOf(needle);
  return pos<0?Buffer.from(bytes):Buffer.concat([Buffer.from(bytes.subarray(0,pos)),Buffer.from(repl),Buffer.from(bytes.subarray(pos+needle.length))]);
}
async function run(rewrite,bytes,sizes){
  let off=0;
  const source=new ReadableStream({
    pull(c){
      if(off>=bytes.length){c.close();return}
      const size=sizes[(off>>>1)%sizes.length] || 1;
      const end=Math.min(bytes.length,off+size);
      c.enqueue(bytes.subarray(off,end));off=end;
    }
  });
  const response=new Response(source, {status:200,headers:{'content-type':'application/json'}});
  const out=rewrite(response);
  assert.equal(out.status,200);
  assert.equal(out.headers.get('content-type'),'application/json');
  return new Uint8Array(await out.arrayBuffer());
}
let total=0;
async function check(bytes,sizes,label){
  const want=expected(bytes);
  const [old, now] = await Promise.all([run(original,bytes,sizes),run(improved,bytes,sizes)]);
  assert.deepEqual(Buffer.from(old),want, 'baseline mismatch: '+label);
  assert.deepEqual(Buffer.from(now),want,'optimized mismatch: '+label);
  total++;
}
const enc=new TextEncoder();
for(const value of ['', 'abc', '"adSlots"', 'aaaaadSlota', '"adSlotS"', 'start "adSlots" tail', '"adSlots" X "adSlots"']){
  for (const sizes of [[1],[2],[3],[8],[9],[16],[128],[1,2,3,8,34]]) await check(enc.encode(value),sizes,value);
}
let seed=0x1234abcd;
function next(){seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return seed>>>0;}
for (let iteration=0;iteration<1300;iteration++) {
  const size=next()%700;
  const bytes=new Uint8Array(size);
  for(let i=0;i<size;i++) bytes[i]=next()%256;
  if (size>=needle.length && iteration%3!==0){
    let start=next()%(size-needle.length+1);
    bytes.set(needle,start);
    if(size>=2*needle.length && iteration%9===0)bytes.set(needle,size-needle.length);
  }
  const split=[1+next()%51,1+next()%15,1+next()%80];
  await check(bytes,split,'random '+iteration);
}
console.log(`PASS: ${total} baseline/optimized paired deterministic byte-exact cases`);
async function benchmark(rewrite,chunkSize,bytes,iterations=9){
  const sample=[];
  for(let n=0;n<iterations;n++){
    const a=performance.now();
    const out=await run(rewrite,bytes,[chunkSize]);
    assert.deepEqual(Buffer.from(out),expected(bytes));
    sample.push(performance.now()-a);
  }
  sample.sort((a,b)=>a-b);return {medianMs:sample[Math.floor(sample.length/2)],all:sample.map(v=>+v.toFixed(2))};
}
const payload = new Uint8Array(4*1024*1024);
payload.fill(65); // no replacement: worst case for continued incremental searching
for(const cs of [4096,16384,65536]){
  const old=await benchmark(original,cs,payload);
  const now=await benchmark(improved,cs,payload);
  console.log('benchmark watch 4MiB chunk',cs,'baseline',JSON.stringify(old),'optimized',JSON.stringify(now),'speedup',+(old.medianMs/now.medianMs).toFixed(2));
}
