const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

const flush=()=>new Promise(resolve=>setImmediate(resolve));
function harness(events, config={match:'a-vs-b',title:'A vs B',channel:'first',competition:'Liga',mode:'watch'}) {
    const elements={}, listeners={}, calls=[];
    for(const id of ['liveFrame','playerWrapper','signalSelect','playerStatus','reconnect','fullscreen','backToBot']) {
        elements[id]={hidden:true,textContent:'',listeners:{},addEventListener(event,fn){this.listeners[event]=fn;}};
    }
    elements.playerConfig={textContent:JSON.stringify(config)};
    const frame=elements.liveFrame;frame.contentWindow={};frame.src='/embed/'+config.channel;
    const select=elements.signalSelect;select.options=[{value:`https://test.local/ver/${config.channel}?m=${config.match}&mode=watch`}];select.selectedIndex=0;
    select.append=option=>select.options.push(option);
    Object.defineProperty(select,'value',{get(){return this.options[this.selectedIndex].value;},set(value){this.selectedIndex=this.options.findIndex(option=>option.value===value);}});
    const document={getElementById:id=>elements[id],createElement:()=>({})};
    const window={addEventListener:(event,fn)=>listeners[event]=fn};
    const fetch=(url,options)=>{calls.push([url,options]);return Promise.resolve({ok:true,json:async()=>({events})});};
    vm.runInNewContext(fs.readFileSync('static/player.js','utf8'),{document,window,fetch,location:{origin:'https://test.local'},history:{replaceState(){}},crypto:{randomUUID:()=> 'session-123'},setInterval:()=>1,clearInterval(){},URL,URLSearchParams,Date,Set,Promise});
    const state=(slug,state,extra={})=>listeners.message({origin:'https://test.local',source:frame.contentWindow,data:{type:'elciro-player-state',slug,state},...extra});
    return {elements,listeners,calls,state,frame,select};
}

(async()=>{
    const fixture=[{match_slug:'a-vs-b',channels:[{slug:'first',name:'Primera'},{slug:'backup',name:'Respaldo'}]},
                   {match_slug:'unrelated',channels:[{slug:'wrong-game',name:'Otro partido'}]}];
    const run=harness(fixture);await flush();
    run.state('first','failed',{origin:'https://untrusted.example'});await flush();
    assert.equal(run.frame.src,'/embed/first','Untrusted iframe messages must not switch the video');
    run.state('first','failed');await flush();
    assert.equal(run.frame.src,'/embed/backup','An unavailable source must use the same match backup');
    assert.equal(run.select.options.length,2,'Signals from other matches must never be offered');
    run.state('first','failed');await flush();
    assert.equal(run.frame.src,'/embed/backup','Late errors from an old iframe must be ignored');
    run.state('backup','failed');await flush();
    assert.equal(run.frame.src,'/embed/backup','Do not cycle forever after all sources fail');
    assert.match(run.elements.playerStatus.textContent,/No hay otra señal/);
    run.elements.reconnect.listeners.click();
    assert.equal(run.frame.src,'/embed/backup?refresh=1','Reconnect must refresh the selected source, not the original one');
    run.state('backup','playing');
    assert.equal(run.elements.playerStatus.hidden,true);

    const channel=harness(fixture,{match:'first',title:'Canal',channel:'first',competition:'',mode:'watch'});
    await flush();channel.state('first','failed');await flush();
    assert.equal(channel.frame.src,'/embed/first','A standalone channel must never switch to another match');
    assert.equal(channel.calls.some(([url])=>url==='/api/partidos'),false);

    const missing=harness([{match_slug:'other',channels:[{slug:'wrong',name:'Incorrecta'}]}]);
    await flush();missing.state('first','failed');await flush();assert.equal(missing.frame.src,'/embed/first');
    console.log('Player behavior OK: correct fallback, origin checks, no unrelated sources, bounded recovery, selected-source reconnect.');
})().catch(error=>{console.error(error);process.exitCode=1;});
