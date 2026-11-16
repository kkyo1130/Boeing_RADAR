import {createRequire} from 'node:module';
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
const {chromium}=createRequire(new URL('../../frontend/package.json',import.meta.url))('@playwright/test');
const [beforeURL,afterURL,ocrURL,output]=process.argv.slice(2);
if(!beforeURL||!afterURL||!ocrURL||!output)throw Error('Usage: node scripts/evaluation/compare-cockpit-proportions.mjs <before-url> <after-url> <ocr-url> <output-directory>');
const dir=resolve(output);await mkdir(dir,{recursive:true});
const browser=await chromium.launch({headless:true});const results=[];
for(const source of ['before','after']){
 const displayURL=source==='before'?beforeURL:afterURL;
 for(const viewport of [{width:1440,height:1000},{width:1024,height:768}]){
 const page=await browser.newPage({viewport,deviceScaleFactor:1});await page.goto(new URL('/cockpit',displayURL).href);await page.locator('.cockpit-3d[data-state=ready]').waitFor();
 for(const view of ['조종석 시점','MCP 정면']){
  await page.getByRole('button',{name:view,exact:true}).click();await page.waitForTimeout(200);
  for(const [heading,altitude] of [[15,4500],[45,7000],[123,15000],[180,24000],[225,32000],[315,41000]]){
   for(const [key,value] of [['HEADING',heading],['ALTITUDE',altitude]]){page.once('dialog',dialog=>dialog.accept(String(value)));await page.getByRole('button',{name:new RegExp('^'+key+' [0-9]+$')}).click();}
   await page.waitForTimeout(70);
   const image=await page.locator('.cockpit-3d canvas').screenshot();
   const filename=`${source}-${viewport.width}-${view==='MCP 정면'?'mcp':'pilot'}-${heading}.png`;await writeFile(dir+'/'+filename,image);
   const response=await page.request.post(new URL('/infer-frame',ocrURL).href,{data:{image:image.toString('base64')}});const data=await response.json();
   const row={source,viewport,view,heading,altitude,status:response.status(),data};results.push(row);
   await writeFile(dir+'/results.json',JSON.stringify(results,null,2));
   console.log(JSON.stringify({source,width:viewport.width,view,expected:[heading,altitude],actual:[data.hdg?.value,data.alt?.value],reasons:[data.hdg?.reason,data.alt?.reason]}));
  }
 }
 await page.close();
 }
}
await browser.close();

const summary={scope:'Rendered screenshots only; not physical camera evaluation or calibrated model accuracy',sources:{}};
for(const row of results){
 const views=summary.sources[row.source]??={};
 const key=`${row.viewport.width}x${row.viewport.height}/${row.view}`;
 const counts=views[key]??={correct:0,wrong:0,held:0,total:0};
 for(const [kind,expected] of [['hdg',String(row.heading).padStart(3,'0')],['alt',String(row.altitude).padStart(5,'0')]]){
  const value=row.data[kind]?.value;counts.total++;
  counts[value===expected?'correct':value==null?'held':'wrong']++;
 }
}
await writeFile(dir+'/summary.json',JSON.stringify(summary,null,2));console.log(JSON.stringify(summary,null,2));
