import {createRequire} from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url));
let require=createRequire(new URL('./package.json',import.meta.url));
let esbuild;try{esbuild=require('esbuild');}catch{require=createRequire(new URL('../el-ciro-plataforma/package.json',import.meta.url));esbuild=require('esbuild');}
await esbuild.build({entryPoints:[path.join(root,'src/main.tsx')],bundle:true,splitting:true,format:'esm',platform:'browser',target:['es2020'],outdir:path.join(root,'public_html/assets'),entryNames:'app',chunkNames:'chunk-[hash]',minify:true,jsx:'automatic',nodePaths:[path.resolve(root,'node_modules'),path.resolve(root,'../el-ciro-plataforma/node_modules')],define:{'process.env.NODE_ENV':'"production"'},legalComments:'eof',metafile:true}).then(r=>fs.writeFileSync(path.join(root,'build-meta.json'),JSON.stringify(r.metafile,null,2)));
const css=fs.readFileSync(path.join(root,'src/app.css'),'utf8').replace("@import 'tailwindcss';",'');
fs.writeFileSync(path.join(root,'public_html/assets/app.css'),css);
console.log('Frontend compilado para Hostinger Premium.');
