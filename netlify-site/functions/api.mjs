import {Readable} from 'node:stream';
import {timingSafeEqual} from 'node:crypto';
import {getStore} from '@netlify/blobs';
import {agenda} from '../lib/agenda.mjs';
import {publicAgenda,grant,verify,manifest,dayOf} from '../lib/core.mjs';
import {resolve,request,read} from '../lib/network.mjs';
const json=(value,status=200,headers={})=>Response.json(value,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',...headers}});
export default async function handler(req) {
  const url=new URL(req.url),action=url.pathname.split('/').filter(Boolean).at(-1);
  const expectedMethod=action==='presence'?'POST':'GET';
  if(req.method!==expectedMethod)return json({error:'Método no permitido.'},405,{'Allow':expectedMethod});
  try {
    if(action==='agenda')return json(publicAgenda(await agenda()),200,{'Netlify-CDN-Cache-Control':'public, max-age=45, stale-while-revalidate=45'});
    if(action==='play'){
      const data=await agenda(),source=data.events.flatMap(e=>e.signals).find(s=>s.id===url.searchParams.get('source'));
      if(!source)return json({error:'Esta señal ya no está publicada. Actualiza la agenda.'},404);
      const resolved=await resolve(source.url);
      return json({url:'/api/media?t='+encodeURIComponent(grant(resolved.url,resolved.referer)),name:source.name});
    }
    if(action==='media'){
      let permission;try{permission=verify(url.searchParams.get('t'));}catch{return json({error:'La sesión venció. Vuelve a abrir la señal.'},403);}
      const {response,url:finalURL}=await request(permission.url,permission.referer,req.headers.get('range')||'');
      const type=String(response.headers['content-type']||'application/octet-stream');
      if(response.statusCode<200||response.statusCode>=300||/html|javascript|json|svg/i.test(type)){response.resume();return json({error:'Señal no disponible.'},502);}
      if(/mpegurl/i.test(type)||new URL(finalURL).pathname.endsWith('.m3u8'))return new Response(manifest(await read(response,1000000),finalURL,permission.referer,permission.expiry),{headers:{'Content-Type':'application/vnd.apple.mpegurl','Cache-Control':'no-store'}});
      const headers={'Content-Type':type,'Cache-Control':'private, max-age=5','X-Content-Type-Options':'nosniff'};
      for(const key of ['content-range','accept-ranges'])if(response.headers[key])headers[key]=response.headers[key];
      // HLS uses short segments; stop before the platform's streamed response limit.
      let size=0;
      const bounded=Readable.toWeb(response).pipeThrough(new TransformStream({transform(chunk,controller){size+=chunk.byteLength;if(size>19000000)throw Error('SEGMENT_LIMIT');controller.enqueue(chunk);}}));
      return new Response(bounded,{status:response.statusCode,headers});
    }
    if(action==='presence'){
      if(req.headers.get('origin')!==url.origin)return json({error:'Origen no válido.'},403);
      if(Number(req.headers.get('content-length')||0)>2048)return json({error:'Solicitud demasiado grande.'},413);
      const text=await req.text();if(text.length>2048)return json({error:'Solicitud demasiado grande.'},413);
      const body=JSON.parse(text);
      if(!/^[a-f0-9-]{36}$/.test(body.session||''))return json({error:'Sesión no válida.'},400);
      const data=await agenda(),event=data.events.find(e=>e.id===body.match);
      if(body.match&&!event)return json({error:'Partido no válido.'},400);
      const store=getStore('audience'),key=`${dayOf(new Date())}/${body.session}`;
      await store.setJSON(key,{match:event?.id||'',title:event?.title||'',playing:body.playing===true,at:Date.now()});
      return json({ok:true});
    }
    if(action==='statistics'){
      const secret=process.env.ADMIN_PASSWORD||'',actual=Buffer.from(req.headers.get('authorization')?.replace(/^Bearer /,'')||''),expected=Buffer.from(secret);
      if(secret.length<16||actual.length!==expected.length||!timingSafeEqual(actual,expected))return json({error:'Acceso privado.'},403);
      const store=getStore('audience'),{blobs}=await store.list({prefix:dayOf(new Date())+'/'});
      const sessions=(await Promise.all(blobs.map(b=>store.get(b.key,{type:'json'})))).filter(Boolean);
      const events=new Map();let watching=0;
      for(const session of sessions){if(!session.match)continue;const row=events.get(session.match)||{title:session.title,visitors:0,watching:0};row.visitors++;if(session.playing&&Date.now()-session.at<75000){row.watching++;watching++;}events.set(session.match,row);}
      return json({visitors:sessions.length,watching,events:[...events.values()]});
    }
    return json({error:'Ruta no encontrada.'},404);
  }catch{return json({error:action==='agenda'?'No se pudo actualizar la agenda. Intenta de nuevo.':'La señal no está disponible. Prueba otra opción.'},503);}
}
