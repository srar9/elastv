'use strict';
(() => {
    const config=JSON.parse(document.getElementById('nativeConfig').textContent);
    const video=document.getElementById('video'), notice=document.getElementById('notice');
    let hls, retryTimer, startupTimer, retries=0, lastPosition=-1, lastAdvance=Date.now();
    let state='connecting', reason='Conectando la señal…', healthySince=0, waitingForTap=false, disposed=false;
    function emit(type, data) {parent.postMessage({type,slug:config.slug,...data},location.origin);}
    function status(next, message) {state=next;reason=message;emit('elciro-player-state',{state,reason});}
    function show(message) {document.getElementById('message').textContent=message;notice.hidden=false;}
    function fail(message) {
        clearTimeout(startupTimer);status('failed',message);show(message);
        emit('elciro-playback',{playing:false});
    }
    function play() {
        video.play().catch(() => {
            video.muted=true;
            video.play().catch(() => {waitingForTap=true;clearTimeout(startupTimer);status('interaction','Toca reproducir para iniciar el video.');show(reason);});
        });
    }
    function reconnect() {
        if(disposed||retryTimer||state==='failed')return;
        emit('elciro-playback',{playing:false});
        if(++retries>2){fail('La señal no responde. Buscando otra opción del partido…');return;}
        status('connecting','Reconectando la señal…');show(reason);
        retryTimer=setTimeout(() => {retryTimer=null;start();},Math.min(6000,1500*retries));
    }
    function start() {
        if(disposed)return;
        if(hls){hls.destroy();hls=null;}
        clearTimeout(startupTimer);lastAdvance=Date.now();lastPosition=-1;healthySince=0;waitingForTap=false;
        status('connecting','Conectando la señal…');
        if(!config.source){fail('Esta señal no está disponible. Buscando otra opción del partido…');return;}
        startupTimer=setTimeout(() => {if(state!=='playing'&&!waitingForTap)fail('La señal está tardando demasiado. Buscando otra opción…');},25000);
        if(video.canPlayType('application/vnd.apple.mpegurl')){video.src=config.source;video.load();play();}
        else if(window.Hls&&Hls.isSupported()){
            hls=new Hls({enableWorker:true,lowLatencyMode:false,liveSyncDurationCount:3,liveMaxLatencyDurationCount:8,maxBufferLength:30,maxMaxBufferLength:60,backBufferLength:20});
            hls.attachMedia(video);hls.on(Hls.Events.MEDIA_ATTACHED,()=>hls.loadSource(config.source));hls.on(Hls.Events.MANIFEST_PARSED,play);
            hls.on(Hls.Events.ERROR,(_,data)=>{if(data.fatal)reconnect();});
        }else{clearTimeout(startupTimer);status('unsupported','Este dispositivo no admite la reproducción de esta señal.');show(reason);}
    }
    video.addEventListener('playing',()=>{waitingForTap=false;clearTimeout(startupTimer);healthySince=Date.now();notice.hidden=true;status('playing','');emit('elciro-playback',{playing:true});});
    video.addEventListener('pause',()=>{status('paused','');emit('elciro-playback',{playing:false});});
    for(const event of ['waiting','ended','error','emptied'])video.addEventListener(event,()=>emit('elciro-playback',{playing:false}));
    video.addEventListener('error',reconnect);video.addEventListener('loadedmetadata',play);
    video.addEventListener('timeupdate',()=>{if(video.currentTime!==lastPosition){lastPosition=video.currentTime;lastAdvance=Date.now();}});
    const monitor=setInterval(()=>{
        const advancing=Date.now()-lastAdvance<5000;
        emit('elciro-playback',{playing:!video.paused&&!video.ended&&video.readyState>=3&&advancing});
        emit('elciro-player-state',{state,reason});
        if(advancing&&healthySince&&Date.now()-healthySince>30000)retries=0;
        if(!video.paused&&!waitingForTap&&config.source&&Date.now()-lastAdvance>20000)reconnect();
    },3000);
    document.getElementById('retry').onclick=()=>{
        if(!config.source){location.replace('/embed/'+encodeURIComponent(config.slug)+'?refresh=1');return;}
        clearTimeout(retryTimer);retryTimer=null;retries=0;state='connecting';start();
    };
    window.addEventListener('pagehide',()=>{disposed=true;emit('elciro-playback',{playing:false});clearInterval(monitor);clearTimeout(startupTimer);clearTimeout(retryTimer);if(hls)hls.destroy();});
    start();
})();
