import {useEffect,useRef,useState} from 'react';
import {Play,RefreshCw,Maximize2,WifiOff} from './icons';
import {localMediaURL,retryDelay,playFailure} from './playback';
type Phase='loading'|'paused'|'playing'|'buffering'|'error';
export default function VideoPlayer({sourceId,onNext}:{sourceId:string;onNext?:()=>void}){
 const video=useRef<HTMLVideoElement>(null),frame=useRef<HTMLDivElement>(null),engine=useRef<import('hls.js').default|null>(null);
 const intent=useRef(false),disposed=useRef(false),repairing=useRef(false),recovery=useRef<()=>void>(()=>{});
 const [phase,setPhase]=useState<Phase>('loading'),[message,setMessage]=useState('Conectando con la señal…'),[reload,setReload]=useState(0),[muted,setMuted]=useState(false);
 const [levels,setLevels]=useState<{index:number;label:string}[]>([]),[quality,setQuality]=useState('-1');
 const play=()=>{const el=video.current;if(!el||phase==='loading'||phase==='error')return;intent.current=true;void el.play().catch(e=>{if(disposed.current||playFailure(e)==='ignore')return;intent.current=false;if(playFailure(e)==='gesture'){setPhase('paused');setMessage('Pulsa reproducir para comenzar.');}else{setPhase('error');setMessage('No se pudo reproducir esta señal. Reintenta o elige otra.');}});};
 const pause=()=>{intent.current=false;video.current?.pause();setPhase('paused');};
 const fullscreen=()=>{const native=()=>{(video.current as (HTMLVideoElement&{webkitEnterFullscreen?:()=>void})|null)?.webkitEnterFullscreen?.();};if(frame.current?.requestFullscreen)void frame.current.requestFullscreen().catch(native);else native();};
 useEffect(()=>{
  const el=video.current!;const abort=new AbortController();const timers=new Set<ReturnType<typeof setTimeout>>();let gone=false,networkRetries=0,mediaRetries=0;disposed.current=false;
  repairing.current=false;setPhase('loading');setMessage('Conectando con la señal…');setLevels([]);setQuality('-1');
  const later=(fn:()=>void,ms:number)=>{const timer=setTimeout(()=>{timers.delete(timer);if(!gone)fn();},ms);timers.add(timer);};
  const fail=(text:string)=>{if(gone)return;intent.current=false;setPhase('error');setMessage(text);engine.current?.stopLoad();};
  const resume=()=>{if(!intent.current)return;void el.play().catch(e=>{if(gone||e?.name==='AbortError')return;intent.current=false;setPhase('paused');setMessage('La señal está lista. Pulsa reproducir.');});};
  recovery.current=()=>{if(!gone&&intent.current){setPhase('buffering');setMessage('Recuperando la conexión…');}};
  const start=async()=>{try{
   if(!sourceId)throw new Error('No hay señales publicadas para este evento.');
   const response=await fetch('api.php?action=play&source='+encodeURIComponent(sourceId),{signal:abort.signal});
   const data=await response.json() as {url?:string;error?:string};if(!response.ok)throw new Error(data.error||'Esta señal no está disponible.');
   const url=localMediaURL(data.url,location.href);if(gone)return;
   if(el.canPlayType('application/vnd.apple.mpegurl')){el.src=url;el.load();}
   else {const Hls=(await import('hls.js')).default;if(gone)return;if(!Hls.isSupported())throw new Error('Este navegador no admite la señal. Prueba un navegador actualizado.');
    const hls=new Hls({enableWorker:true,capLevelToPlayerSize:true,maxBufferLength:30,maxMaxBufferLength:60,backBufferLength:15,liveSyncDurationCount:3,liveMaxLatencyDurationCount:8});engine.current=hls;
    hls.on(Hls.Events.MANIFEST_PARSED,(_,data)=>{if(gone)return;setLevels(data.levels.map((l,index)=>({index,label:l.height?l.height+'p':Math.round(l.bitrate/1000)+' kbps'})));setPhase('paused');setMessage('La señal está lista.');resume();});
    hls.on(Hls.Events.ERROR,(_,data)=>{if(gone||!data.fatal)return;
     if(data.type===Hls.ErrorTypes.NETWORK_ERROR){const delay=retryDelay(networkRetries++);if(delay!==null){setPhase('buffering');setMessage('Reconectando con la señal…');later(()=>hls.startLoad(),delay);return;}}
     if(data.type===Hls.ErrorTypes.MEDIA_ERROR&&mediaRetries++<1){repairing.current=true;setPhase('buffering');setMessage('Recuperando el video…');hls.recoverMediaError();return;}
     fail('Esta señal se ha interrumpido. Puedes reintentar o elegir otra.');
    });hls.attachMedia(el);hls.loadSource(url);
   }
   // A stalled segment may recover through hls.js; report the wait without hiding controls.
  }catch(error){if(!gone&&!abort.signal.aborted)fail(error instanceof Error?error.message:'No se pudo conectar con la señal.');}};
  void start();
  const online=()=>{if(intent.current){networkRetries=0;engine.current?.startLoad();resume();}};
  const visible=()=>{if(document.visibilityState==='visible'&&intent.current){const hls=engine.current;if(hls&&Number.isFinite(hls.liveSyncPosition)&&el.currentTime<(hls.liveSyncPosition||0)-15)el.currentTime=hls.liveSyncPosition!;resume();}};
  window.addEventListener('online',online);document.addEventListener('visibilitychange',visible);
  return()=>{gone=true;disposed.current=true;abort.abort();timers.forEach(clearTimeout);window.removeEventListener('online',online);document.removeEventListener('visibilitychange',visible);engine.current?.destroy();engine.current=null;el.pause();el.removeAttribute('src');el.load();};
 },[sourceId,reload]);
 const busy=phase==='loading'||phase==='buffering',playing=phase==='playing'||phase==='buffering'&&intent.current;
 return <div className="smooth-player" ref={frame}>
  <video ref={video} playsInline preload="auto" muted={muted} tabIndex={0} aria-label="Video del partido. Espacio para reproducir o pausar." onKeyDown={e=>{if(e.key===' '||e.key==='Enter'){e.preventDefault();playing?pause():play();}}} onClick={()=>playing?pause():play()}
   onPlaying={()=>{repairing.current=false;setPhase('playing');setMessage('');}} onPause={()=>{if(!disposed.current&&!repairing.current){intent.current=false;setPhase('paused');}}}
   onWaiting={()=>{if(intent.current){setPhase('buffering');setMessage('Cargando video…');}}} onStalled={()=>recovery.current()}
   onCanPlay={()=>{repairing.current=false;if(!intent.current&&phase!=='error'){setPhase('paused');setMessage('La señal está lista.');}if(intent.current)void video.current?.play().catch(()=>{intent.current=false;setPhase('paused');});}}
   onEnded={()=>{intent.current=false;setPhase('error');setMessage('La señal ha terminado. Puedes reintentar o elegir otra.');}}
   onError={()=>{if(!disposed.current&&!engine.current){intent.current=false;setPhase('error');setMessage('No se pudo abrir esta señal. Reintenta o prueba otra opción.');}}}/>
  <img className="video-watermark" src="assets/el-ciro.png" alt="EL CIRO"/>
  {busy&&<div className="stream-loading" role="status"><span className="loader"/><span>{message}</span></div>}
  {phase==='paused'&&<button type="button" className="stream-start" aria-label="Reproducir video" onClick={play}><Play size={32} fill="currentColor"/><span>Reproducir</span></button>}
  {phase==='error'&&<div className="stream-error" role="alert"><WifiOff size={32}/><p>{message}</p><div><button type="button" className="primary small" onClick={()=>setReload(n=>n+1)}><RefreshCw size={16}/> Reintentar</button>{onNext&&<button type="button" className="secondary" onClick={onNext}>Probar otra señal</button>}</div></div>}
  <div className="stream-controls">
   <div className="stream-state">{playing?<button type="button" aria-label="Pausar video" onClick={pause}><svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M6 4h4v16H6zm8 0h4v16h-4z"/></svg><span>Pausar</span></button>:<span>{phase==='paused'?'Señal lista':phase==='error'?'Señal no disponible':'Conectando'}</span>}</div>
   <div className="stream-options"><button type="button" aria-label={muted?'Activar sonido':'Silenciar'} aria-pressed={muted} onClick={()=>setMuted(x=>!x)}><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M11 4 5 9H2v6h3l6 5Z"/>{muted?<path d="m16 9 6 6m-6 0 6-6"/>:<path d="M15 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/>}</svg><span>{muted?'Sin sonido':'Sonido'}</span></button>
   {levels.length>1&&<select aria-label="Calidad del video" value={quality} onChange={e=>{setQuality(e.target.value);if(engine.current)engine.current.currentLevel=Number(e.target.value);}}><option value="-1">Auto</option>{levels.map(l=><option key={l.index} value={l.index}>{l.label}</option>)}</select>}
   <button type="button" aria-label="Pantalla completa" onClick={fullscreen}><Maximize2 size={19}/></button></div>
  </div>
 </div>;
}
