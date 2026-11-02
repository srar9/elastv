import {spawn} from 'node:child_process';import assert from 'node:assert/strict';import {setTimeout as wait} from 'node:timers/promises';import path from 'node:path';import {fileURLToPath} from 'node:url';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url))),base='http://127.0.0.1:8791/';
const server=spawn('php',['-S','127.0.0.1:8791','-t','public_html'],{cwd:root,stdio:['ignore','ignore','pipe'],windowsHide:true});let started=false,output='';server.stderr.on('data',d=>{output+=d;if(output.includes('Development Server')&&output.includes('started'))started=true;});
try{
 for(let i=0;i<50&&!started&&server.exitCode===null;i++)await wait(100);assert.ok(started,'El servidor de pruebas debe iniciar en un puerto libre.');
 const page=await fetch(base);assert.equal(page.status,200);const html=await page.text(),csp=page.headers.get('content-security-policy');assert.ok(csp.includes("frame-src 'none'"));assert.ok(csp.includes("connect-src 'self'"));assert.match(html,/app\.js\?v=[a-f0-9]{12}/);assert.match(html,/app\.css\?v=[a-f0-9]{12}/);
 const jsPath=html.match(/src="(assets\/app\.js\?v=[a-f0-9]+)"/)[1];assert.equal((await fetch(new URL(jsPath,base))).status,200);
 const agenda=await fetch(base+'api.php?action=agenda');assert.equal(agenda.status,200);const a=await agenda.json();assert.ok(Array.isArray(a.events));
 const invalid=await fetch(base+'api.php?action=media&t=invalid');assert.equal(invalid.status,403);
 const play=await fetch(base+'api.php?action=play&source=catalog-espn');assert.equal(play.status,200);const data=await play.json();const manifest=await fetch(new URL(data.url,base));assert.equal(manifest.status,200);const text=await manifest.text();assert.ok(text.startsWith('#EXTM3U'));assert.ok(text.includes('api.php?action=media&t='));
 console.log(JSON.stringify({page:200,localVideoOnly:true,externalFramesBlocked:true,versionedAssets:true,events:a.events.length,manifest:200}));
}finally{server.kill();}
