import test from 'node:test';
import assert from 'node:assert/strict';
import handler from '../functions/api.mjs';
test('statistics rejects unauthenticated website requests',async()=>{
  assert.equal((await handler(new Request('https://test.netlify.app/api/statistics'))).status,403);
});
test('media rejects unsigned arbitrary targets',async()=>{
  assert.equal((await handler(new Request('https://test.netlify.app/api/media?t=invalid'))).status,403);
});
test('presence rejects cross-origin writes',async()=>{
  assert.equal((await handler(new Request('https://test.netlify.app/api/presence',{method:'POST',body:'{}'}))).status,403);
});
test('agenda rejects unsupported mutations',async()=>{
  assert.equal((await handler(new Request('https://test.netlify.app/api/agenda',{method:'POST'}))).status,405);
});
