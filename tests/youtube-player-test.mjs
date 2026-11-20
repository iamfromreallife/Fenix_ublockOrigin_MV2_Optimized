import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const root=decodeURIComponent(new URL('../',import.meta.url).pathname).replace(/\/$/,'');
function init(build){
  const source=fs.readFileSync(`${root}/${build}/js/scriptlets/youtube-player.js`,'utf8');
  class LocalEncoder extends TextEncoder { encode(v){return super.encode(v)} }
  class FakeRequest {constructor(url,init){this.url=url;this.body=init?.body}}
  class FakeXHR {open(method,url){this.url=url}send(body){this.body=body}}
  class FakePromise {then(fn){return fn}}
  let calls=0;
  const scope={URL,TextEncoder:LocalEncoder,Request:FakeRequest,XMLHttpRequest:FakeXHR,Promise:FakePromise,TransformStream,Response,ReadableStream,WeakMap,WeakSet,Symbol,
    queueMicrotask,location:{hostname:'www.youtube.com',pathname:'/watch',href:'https://www.youtube.com/watch?v=x'},
    document:{getElementById(){return null}},fetch(...args){calls++;return Promise.resolve(args[1]?.response ?? new Response('not UMP'))}};
  scope.self=scope;
  vm.createContext(scope);
  vm.runInContext(source,scope,{filename:'youtube-player.js'});
  scope.JSON = vm.runInContext('JSON',scope);
  return {scope, get calls(){return calls;}};
}
const u=init('optimized');
let cases=0;
const req=()=>({videoId:'abc',context:{client:{clientName:'WEB'}},playbackContext:{contentPlaybackContext:{},adPlaybackContext:{pyv:true}}});
let obj=req();
let serialized=u.scope.JSON.stringify(obj);
assert.equal(obj.params,'eAFgAQ');
assert.equal(obj.playbackContext.params,'eAFgAQ');
assert.equal(obj.playbackContext.contentPlaybackContext.isInlinePlaybackNoAd,true);
assert(serialized.includes('eAFgAQ'));
cases++;
obj=req();u.scope.location.pathname='/shorts/id';u.scope.JSON.stringify(obj);assert.equal(obj.params,undefined);cases++;
u.scope.location.pathname='/watch';
obj=req();const encoded=JSON.stringify(obj);
const bytes=new u.scope.TextEncoder().encode(encoded);
const changed=JSON.parse(new TextDecoder().decode(bytes));
assert.equal(changed.params,'eAFgAQ');cases++;
let normal=()=> 'normal';
let abnormal=function onAbnormalityDetected(){return 'bad'};
const p=new u.scope.Promise();
assert.equal(p.then(normal),normal);
assert.notEqual(p.then(abnormal),abnormal);
for(let i=0;i<200;i++) {const f=i%3===0 ? abnormal : normal;const out=p.then(f);assert.equal(out===abnormal,false)}
cases++;
let request=new u.scope.Request('/youtubei/v1/player',{body:encoded});
assert.equal(JSON.parse(request.body).params,'eAFgAQ');cases++;
let xhr=new u.scope.XMLHttpRequest();xhr.open('POST','/youtubei/v1/player');xhr.send(encoded);
assert.equal(JSON.parse(xhr.body).params,'eAFgAQ');cases++;
const backoff=Uint8Array.from([35,3,32,0xd0,0x0f]);
const expected=Uint8Array.from([35,3,32,0x80,0]);
const other=Uint8Array.from([34,3,32,0xd0,0x0f]);
const media=Uint8Array.from([5,9,1,2,3,4,5,6,7,8,9]);
async function fetchSabr(bytes,chunks,url='https://r1---sn.googlevideo.com/videoplayback?sabr=1'){
  let off=0;
  let stream=new ReadableStream({pull(c){if(off>=bytes.length){c.close();return}const n=Math.min(chunks,bytes.length-off);c.enqueue(bytes.subarray(off,off+n));off+=n;}});
  const response = new Response(stream,{status:200,statusText:'OK',headers:{'content-type':'application/vnd.yt-ump'}});
  let res=await u.scope.fetch(url,{response});
  return {bytes:new Uint8Array(await res.arrayBuffer()),res};
}
for(let chunkSize=1;chunkSize<=20;chunkSize++){
  let bytes=Uint8Array.from([...media,...backoff,...other,...media]);
  const out=await fetchSabr(bytes,chunkSize);
  assert.deepEqual(Buffer.from(out.bytes),Buffer.from([...media,...expected,...other,...media]));
  assert.equal(out.res.status,200);cases++;
}
for(let input of [Uint8Array.from([35,3,32,0x80,0x80]),Uint8Array.from([35,3,32,0xD0,0x0f]),Uint8Array.from([35,2,32,0x80])]){
  let out=await fetchSabr(input,1); // malformed payload must pass through
  if(input[4]===0x0f){assert.deepEqual([...out.bytes],[...expected]);}
  else assert.deepEqual([...out.bytes],[...input]);cases++;
}
// Oversized type-35 policies must never be buffered or modified.
const bigPayload=new Uint8Array(4097);
bigPayload.set([32,0xd0,0x0f]);
const bigFrame=Uint8Array.from([35,0x81,0x40,...bigPayload]);
for (const n of [1,17,4096,8192]) {
  const out=await fetchSabr(bigFrame,n);
  assert.deepEqual(Buffer.from(out.bytes),Buffer.from(bigFrame));cases++;
}
// Truncated UMP headers are emitted on stream flush, not silently lost.
for (const incomplete of [Uint8Array.from([0x80]),Uint8Array.from([35,0x80])]) {
  const out=await fetchSabr(incomplete,1);
  assert.deepEqual([...out.bytes],[...incomplete]);cases++;
}
// Validate progressive output without waiting for EOF and cancellation through
// the TransformStream into the original ReadableStream.
let cancelled=false;
let rawStream=new ReadableStream({
  start(controller){controller.enqueue(media)},
  cancel(){cancelled=true},
});
let rawResponse=new Response(rawStream,{headers:{'content-type':'application/vnd.yt-ump'}});
let progressive=await u.scope.fetch('https://r1---sn.googlevideo.com/videoplayback?sabr=1',{response:rawResponse});
let reader=progressive.body.getReader();
let first=await Promise.race([reader.read(),new Promise((_,reject)=>setTimeout(()=>reject(Error('No first media bytes before EOF')),1500))]);
assert.equal(first.done,false);assert(first.value.length>0);
await reader.cancel('no more data');
await new Promise(resolve=>setImmediate(resolve));
assert.equal(cancelled,true);cases++;
let notSabr=await fetchSabr(backoff,2,'https://r1---sn.googlevideo.com/videoplayback?sabr=0');
assert.deepEqual([...notSabr.bytes],[...backoff]);cases++;
assert.equal(u.calls,31);
console.log(`PASS: ${cases} YouTube hook/player/SABR cases; verified request scoping, 20 framing fragmentations, malformed data and metadata`);
