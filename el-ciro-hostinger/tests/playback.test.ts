import {test} from 'node:test';import assert from 'node:assert/strict';
import {localMediaURL,retryDelay,playFailure} from '../src/playback.ts';
test('el video solo acepta la API local, también al instalar en una subcarpeta',()=>{
 const base='https://example.com/futbol/?partido=42';assert.equal(localMediaURL('api.php?action=media&t=test',base),'https://example.com/futbol/api.php?action=media&t=test');
 for(const value of [undefined,'javascript:alert(1)','https://ads.example.com/player','https://example.com/futbol/anuncio','api.php?action=play&t=test','api.php?action=media','https://user:pass@example.com/futbol/api.php?action=media&t=test'])assert.throws(()=>localMediaURL(value,base));
});
test('la reconexión tiene espera progresiva y se detiene después de dos intentos',()=>{assert.deepEqual([0,1,2,3].map(retryDelay),[1200,2800,null,null]);});
test('autoplay bloqueado permite pulsar play; interrupción de carga no es un fallo',()=>{assert.equal(playFailure({name:'NotAllowedError'}),'gesture');assert.equal(playFailure({name:'AbortError'}),'ignore');assert.equal(playFailure({name:'NotSupportedError'}),'failed');});
