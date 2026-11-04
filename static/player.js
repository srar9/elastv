'use strict';
(() => {
    const config=JSON.parse(document.getElementById('playerConfig').textContent);
    const frame=document.getElementById('liveFrame'), wrapper=document.getElementById('playerWrapper');
    const select=document.getElementById('signalSelect'), status=document.getElementById('playerStatus');
    const session=crypto.randomUUID?crypto.randomUUID():'s_'+Date.now()+Math.random().toString(36).slice(2);
    let playing=false,lastReport=0,currentChannel=config.channel,switching=false,disposed=false;
    const tried=new Set([currentChannel]);
    function presence(leaving=false) {
        fetch('/api/audience',{method:'POST',headers:{'Content-Type':'application/json'},keepalive:true,
            body:JSON.stringify({session_id:session,match_id:config.match,title:config.title,playing:!leaving&&playing&&Date.now()-lastReport<6000})}).catch(()=>{});
    }
    function message(text) {status.textContent=text;status.hidden=!text;}
    function optionChannel(option) {return decodeURIComponent(new URL(option.value,location.origin).pathname.split('/').pop());}
    function switchSignal(option, automatic=false) {
        if(!option||disposed)return;
        if(!automatic)tried.clear();
        currentChannel=optionChannel(option);tried.add(currentChannel);
        select.value=option.value;playing=false;presence();
        message(automatic?'Cambiando a otra señal del mismo partido…':'Conectando la señal…');
        frame.src='/embed/'+encodeURIComponent(currentChannel);
        history.replaceState(null,'',new URL(option.value,location.origin).href);
    }
    // Load only alternatives registered for this exact event, while the first
    // video is already connecting. A channel alone never switches to a random channel.
    const signalsReady=config.match===config.channel?Promise.resolve():fetch('/api/partidos').then(response=>response.ok?response.json():null).then(data=>{
        const event=data?.events?.find(event=>event.match_slug===config.match);
        if(!event)return;
        const known=new Set([...select.options].map(optionChannel));
        for(const channel of event.channels||[]) {
            if(known.has(channel.slug))continue;
            const url=new URL('/ver/'+encodeURIComponent(channel.slug),location.origin);
            url.search=new URLSearchParams({m:config.match,title:config.title,c:config.competition,mode:config.mode});
            const option=document.createElement('option');option.value=url.href;option.textContent=channel.name;
            select.append(option);known.add(channel.slug);
        }
    }).catch(()=>{});
    async function nextSignal() {
        if(switching||disposed)return;
        switching=true;const failedChannel=currentChannel;
        message('La señal falló. Buscando otra opción del mismo partido…');
        try {
            const available=()=>[...select.options].find(option=>!tried.has(optionChannel(option)));
            let next=available();
            if(!next){await signalsReady;next=available();}
            if(disposed||failedChannel!==currentChannel)return;
            if(next)switchSignal(next,true);
            else message('No hay otra señal disponible para este '+(config.match===config.channel?'canal':'partido')+'. Puedes reconectar o volver al bot.');
        }finally{switching=false;}
    }
    window.addEventListener('message',event=>{
        if(event.origin!==location.origin||event.source!==frame.contentWindow)return;
        const data=event.data;
        if(!data||data.slug&&data.slug!==currentChannel)return;
        if(data.type==='elciro-playback') {
            const changed=playing!==(data.playing===true);playing=data.playing===true;lastReport=Date.now();if(changed)presence();
        }else if(data.type==='elciro-player-state') {
            if(data.state==='playing')message('');
            else if(data.state==='failed'){playing=false;presence();nextSignal();}
            else if(data.state==='interaction'||data.state==='unsupported')message(data.reason);
        }
    });
    presence();const timer=setInterval(presence,10000);
    window.addEventListener('pagehide',()=>{disposed=true;clearInterval(timer);presence(true);});
    select.addEventListener('change',()=>switchSignal(select.options[select.selectedIndex]));
    document.getElementById('backToBot')?.addEventListener('click',event=>{if(window.Telegram?.WebApp?.initData){event.preventDefault();window.Telegram.WebApp.close();}});
    document.getElementById('reconnect').addEventListener('click',()=>{
        tried.clear();tried.add(currentChannel);playing=false;presence();message('Reconectando la señal…');frame.src='/embed/'+encodeURIComponent(currentChannel)+'?refresh=1';
    });
    document.getElementById('fullscreen').addEventListener('click',async()=>{
        try{
            if(document.fullscreenElement){await document.exitFullscreen();return;}
            if(wrapper.requestFullscreen){await wrapper.requestFullscreen();return;}
            if(frame.webkitRequestFullscreen){frame.webkitRequestFullscreen();return;}
        }catch(_){}
        try{if(window.Telegram?.WebApp?.requestFullscreen)window.Telegram.WebApp.requestFullscreen();else message('Puedes ampliar el video con el control del reproductor.');}catch(_){message('Puedes ampliar el video con el control del reproductor.');}
    });
})();
