import {getStore} from '@netlify/blobs';
import {normalize, merge, dayOf} from './core.mjs';
import {request,read} from './network.mjs';
let cached,loading;
export async function agenda() {
  const now=new Date(),day=dayOf(now);
  if(cached?.day===day&&Date.now()-cached.loaded<90000)return cached;
  if(loading)return loading;
  loading=(async()=>{
    const store=getStore('agenda');
    if(!cached)cached=await store.get('current',{type:'json'});
    if(cached?.day===day&&Date.now()-cached.loaded<90000)return cached;
    const results=await Promise.allSettled([
      process.env.AGENDA_URL || 'https://api.wqxag.com/diaries.json',
      process.env.TARJETA_DIGITAL_AGENDA_URL || 'https://tarjetadigital.club/api/agenda'
    ].map(async url=>{const {response}=await request(url);if(response.statusCode!==200){response.resume();throw Error('AGENDA_HTTP');}return normalize(JSON.parse(await read(response,6000000)),now);}));
    const valid=results.filter(r=>r.status==='fulfilled');
    if(!valid.length){if(cached?.day===day&&Date.now()-cached.loaded<1800000)return {...cached,stale:true};throw Error('AGENDA_UNAVAILABLE');}
    cached={day,events:merge(valid.map(r=>r.value)),updatedAt:new Date().toISOString(),loaded:Date.now(),stale:false};
    await store.setJSON('current',cached);
    return cached;
  })();
  try{return await loading;}finally{loading=null;}
}
