import fs from 'node:fs';import assert from 'node:assert/strict';import {performance} from 'node:perf_hooks';
const path=decodeURIComponent(new URL('../',import.meta.url).pathname);
function factory(build, count){
 const source=fs.readFileSync(path+build+'/js/scriptlets/epicker.js','utf8');
 const start=source.indexOf('const onOptimizeCandidates = function(details) {');
 const end=source.indexOf('/******************************************************************************/',start);
 let messages=[];
 const document={querySelectorAll(s){count.calls++;return {length:([ ...s ].reduce((h,v)=>h*17+v.charCodeAt(0),0)>>>24)};}};
 const pickerFramePort={postMessage(message){messages.push(message)}};
 const fn=new Function('document','pickerFramePort',source.slice(start,end)+'return onOptimizeCandidates;')(document,pickerFramePort);
 return {fn,messages,count};
}
let cases=0;
const baseline=factory('base',{calls:0});const optimized=factory('optimized',{calls:0});
let seed=101; const next=()=>{seed=Math.imul(seed,1664525)+1013904223|0;return seed>>>0};
for(let trial=0;trial<800;trial++){
 const candidates=[];
 for(let j=0;j<next()%20+1;j++){
  const parts=[];for(let k=0;k<next()%15+1;k++)parts.push(['div',' > span',':nth-child(2)','#id','.class','',null,undefined][next()%8]);
  candidates.push(parts);
 }
 const data={candidates,slot:next()%8};
 baseline.fn(data); optimized.fn(data);
 assert.deepEqual(optimized.messages.at(-1),baseline.messages.at(-1),'case '+trial);
 cases++;
}
const data={candidates:Array.from({length:130},(_,i)=>Array.from({length:25},(_,j)=>` .class${j}${i}`)),slot:3};
function bench(fn){const times=[];for(let k=0;k<2;k++)for(let i=0;i<60;i++)fn(data);for(let k=0;k<11;k++){const t=performance.now();for(let i=0;i<60;i++)fn(data);times.push(performance.now()-t);}times.sort((a,b)=>a-b);return {medianMs:+times[5].toFixed(2),samples:times.map(x=>+x.toFixed(2))};}
console.log(`PASS ${cases} selector-generation and candidate-ranking parity cases`);
console.log('benchmark baseline',bench(baseline.fn),'optimized',bench(optimized.fn));
