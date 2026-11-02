export function localMediaURL(value:unknown,base:string){
 if(typeof value!=='string')throw new Error('La señal no devolvió un video válido.');
 const url=new URL(value,base),expected=new URL('api.php',base);
 if(url.username||url.password||url.origin!==expected.origin||url.pathname!==expected.pathname||url.searchParams.get('action')!=='media'||!url.searchParams.get('t'))throw new Error('La señal no devolvió un video válido.');
 return url.href;
}
export function retryDelay(attempt:number){return attempt<2?[1200,2800][attempt]:null;}
export function playFailure(error:unknown){const name=(error as {name?:string})?.name;return name==='AbortError'?'ignore':name==='NotAllowedError'?'gesture':'failed';}
