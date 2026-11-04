import {mkdir, copyFile, cp} from 'node:fs/promises';
const root=new URL('./',import.meta.url);
await mkdir(new URL('dist/',root), {recursive:true});
await cp(new URL('public/',root), new URL('dist/',root), {recursive:true});
await copyFile(new URL('../static/minimal.css',root), new URL('dist/minimal.css',root));
await copyFile(new URL('node_modules/hls.js/dist/hls.min.js',root), new URL('dist/hls.min.js',root));
console.log('Sitio Netlify compilado. Las funciones se despliegan por separado del contenido público.');
