import test from 'node:test';
import assert from 'node:assert/strict';
import {normalize,merge,publicAgenda,grant,verify,manifest} from '../lib/core.mjs';
import {safeURL} from '../lib/network.mjs';
process.env.HLS_PROXY_SECRET='test-only-secret-that-is-at-least-32-characters';
const now=new Date('2026-11-03T16:00:00Z');
const fixture=(overrides={})=>[{diary_description:'Liga: A vs B',date_diary:'2026-11-03',diary_hour:'14:00',embeds:[
  {embed_name:'Canal HD',embed_iframe:'https://tvf90.com/5.php?stream=liga1max'},
  {embed_name:'Canal OP2',embed_iframe:'https://tvf90.com/plus1.php?stream=liga1max'},
  {embed_name:'Duplicado',embed_iframe:'https://tvf90.com/5.php?stream=liga1max'}],...overrides}];
test('same slug distinct published players retain distinct identities',()=>{
  const events=normalize(fixture(),now);assert.equal(events[0].signals.length,2);assert.notEqual(events[0].signals[0].id,events[0].signals[1].id);assert.equal(events[0].time,'15:00');
});
test('merge preserves competition and exact kick-off identity',()=>{
  const feed=normalize(fixture(),now),other=normalize(fixture({diary_description:'Copa: A vs B'}),now),later=normalize(fixture({diary_hour:'16:00'}),now);
  assert.equal(merge([feed,feed]).length,1);assert.equal(merge([feed,feed])[0].signals.length,2);assert.equal(merge([feed,other,later]).length,3);
});
test('old schedules excluded and public response hides upstream sources',()=>{
  assert.deepEqual(normalize(fixture({date_diary:'2026-11-02'}),now),[]);
  const data=publicAgenda({day:'2026-11-03',events:normalize(fixture(),now)});assert.ok(!JSON.stringify(data).includes('https://'));assert.equal(data.channels.length,2);
});
test('manifest signs variants, key and relative segments; rejects tampering and expiry',()=>{
  const expiry=Math.floor(Date.now()/1000)+60;
  const text=manifest('#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="key.bin"\nsub/playlist.m3u8\nsegment.ts','https://cdn.example.com/a/master.m3u8','https://tvf90.com/',expiry);
  const urls=[...text.matchAll(/\/api\/media\?t=([^"\n]+)/g)].map(m=>verify(decodeURIComponent(m[1])));
  assert.equal(urls.length,3);assert.equal(urls[0].url,'https://cdn.example.com/a/key.bin');assert.equal(urls[1].url,'https://cdn.example.com/a/sub/playlist.m3u8');assert.equal(urls[2].expiry,expiry);
  assert.throws(()=>verify(grant('https://cdn.example.com/a','',1)));assert.throws(()=>verify(grant('https://cdn.example.com/a')+'bad'));
});
test('arbitrary local URLs and non-HTTP protocols cannot be proxied',()=>{
  for(const url of ['http://127.0.0.1/','http://[::1]/','http://metadata.google.internal/','file:///etc/passwd','https://user:pass@example.com/','http://example.com:8080/'])assert.throws(()=>safeURL(url));
  assert.equal(safeURL('https://cdn.example.com/a').hostname,'cdn.example.com');
});
