import {test} from 'node:test';import assert from 'node:assert/strict';
import {matchLink,currentLink,telegramShare,initTelegram} from '../src/telegram.ts';
const state={href:'',target:''};
Object.defineProperty(globalThis,'location',{value:{get href(){return state.href;},assign:(s:string)=>{state.target=s;}},configurable:true});
Object.defineProperty(globalThis,'window',{value:{},configurable:true});
test('enlaces compartidos mantienen el partido y eliminan datos privados de Telegram',()=>{
 state.href='https://example.com/futbol/?partido=42&fecha=2026-10-19&tgWebAppData=private&tracking=one#tgWebAppData=private';
 assert.equal(currentLink(),'https://example.com/futbol/?partido=42&fecha=2026-10-19');
 assert.equal(matchLink('A&B','2026-10-20'),'https://example.com/futbol/?partido=A%26B&fecha=2026-10-20');
 state.href='https://example.com/?canal=catalog-espn#private';assert.equal(currentLink(),'https://example.com/?canal=catalog-espn');
});
test('compartir utiliza el selector oficial y conserva caracteres y parámetros',()=>{
 telegramShare('https://example.com/?partido=1&fecha=2026-10-19','⚽ A vs B\n@elasdelfutbol');const u=new URL(state.target);assert.equal(u.origin+u.pathname,'https://t.me/share/url');assert.equal(u.searchParams.get('url'),'https://example.com/?partido=1&fecha=2026-10-19');assert.equal(u.searchParams.get('text'),'⚽ A vs B\n@elasdelfutbol');
});
test('Mini App es opcional y solo se inicializa en una sesión real del SDK',()=>{
 let calls=0;window.Telegram={WebApp:{initData:'',ready:()=>calls++,expand:()=>calls++}};initTelegram();assert.equal(calls,0);window.Telegram.WebApp!.initData='test-session';initTelegram();assert.equal(calls,2);window.Telegram=undefined;
});
