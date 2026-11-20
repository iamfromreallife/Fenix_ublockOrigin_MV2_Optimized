import fs from 'node:fs';import assert from 'node:assert/strict';
const root=decodeURIComponent(new URL('../',import.meta.url).pathname).replace(/\/$/,'');
const source=fs.readFileSync(root+'/optimized/js/storage.js','utf8');
const start=source.indexOf('const fenixYouTubeQuickFixReplacements = [');
const end=source.indexOf('µb.compileFilters = function',start);
const {fn,one,two}=new Function(source.slice(start,end)+ '\nreturn {fn:fenixOptimizeYouTubeQuickFix,one:fenixYouTubeQuickFixReplacements,two:fenixYouTubeQuickFix2026b6Replacements}')();
let count=0;
for(const pairs of [one,two]){
 const line='www.youtube.com##+js(rpnt, script, "YOUTUBE_PREMIUM_LOGO", '+pairs.map(([before])=>before).join(',')+')';
 const output=fn(line);
 for(const [before,after] of pairs) {assert(output.includes(after));assert(!output.includes(before));count++;}
 assert.equal(fn(line.replace('"YOUTUBE_PREMIUM_LOGO"','"unknown"')),line.replace('"YOUTUBE_PREMIUM_LOGO"','"unknown"'));count++;
 assert.equal(fn(line.replace(pairs[0][0],'not-recognized')),line.replace(pairs[0][0],'not-recognized'));count++;
}
assert.equal(fn('example.org##+js(anything)'), 'example.org##+js(anything)');count++;
console.log(`PASS: ${count} Quick Fix conservative replacement / non-target preservation checks`);
