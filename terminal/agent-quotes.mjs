// Keep exchange sockets open while Python analyzes candles and checks delivery.
import {createInterface} from 'node:readline';
import {readFile} from 'node:fs/promises';
import {setTimeout as delay} from 'node:timers/promises';
import {livePrices} from './lib.mjs';

const symbols=JSON.parse(process.argv[2]);
const audit=process.env.LIAM_QUOTE_PARITY==='1' && symbols.length>1;
const inspect=audit?{TRUTHUSDT:'Bitunix futures',DOSUSDT:'Bitunix futures',LITUSDT:'Bitunix futures',PUMPUSDT:'OKX swap'}:{};
const watch=audit?[...new Set([...symbols,'UMXUSDT',...Object.keys(inspect)])]:symbols;
const feed=livePrices(()=>{}, {direct:true,inspect});
const started=Date.now();
feed.watch(watch);

// The optional acceptance run uses an independent Chromium connection on the
// published panel origin. Verify the downloaded module before comparing prices.
let browser;
async function openPanel() {
  const {chromium}=await import('playwright');
  browser=await chromium.launch({executablePath:process.env.LIAM_CHROME || '/usr/bin/google-chrome'});
  const page=await browser.newPage({serviceWorkers:'block'});
  const base='https://auraliam18.github.io/.sognal/terminal/';
  await page.route(base+'quote-verification',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><title>Live quote verification</title>'}));
  await page.goto(base+'quote-verification',{timeout:20000});
  const url=base+'lib.mjs?verify='+started;
  const download=page.waitForResponse(r=>r.url()===url,{timeout:15000});
  const [,response]=await Promise.all([page.evaluate(async ({url,watch,inspect})=>{
    const {livePrices}=await import(url);
    window.panelQuotes=livePrices(()=>{},{inspect});
    window.panelQuotes.watch(watch);
  },{url,watch,inspect}),download]);
  if(!(await response.body()).equals(await readFile(new URL('./lib.mjs',import.meta.url)))) throw Error('published panel version differs');
  await delay(12000);
  return {page};
}
const observer=audit?openPanel().catch(e=>({error:e.message})):null;

function quote(symbol,at,venue) {
  const q=feed.best(symbol,at,venue);
  if(!q) return null;
  return {symbol,price:q.price,venue:q.venue,observed_at:q.at,transport:q.transport,
    clock:q.venue==='Bitunix futures' && q.transport==='rest'?'http_date':'exchange_timestamp'};
}
async function snapshot(request) {
  // A single-symbol cold delivery check can return after its first Bitunix tick.
  const waitUntil=started+(request.execution?3000:11000);
  while(Date.now()<waitUntil && !(request.execution && feed.best(request.execution,Date.now(),'Bitunix futures')?.transport==='websocket')) await delay(100);
  if(request.execution) return quote(request.execution,Date.now(),'Bitunix futures');
  let comparison, markets;
  if(observer && request.audit) {
    const {page,error}=await observer;
    if(error) comparison={error};
    else {
      // Give the browser only the venue selected for publication, never the price.
      // The production UI uses this same routing table from the cycle's quote book.
      const selectedAt=Date.now();
      markets=Object.fromEntries(watch.map(s=>[s,feed.best(s,selectedAt)?.venue]).filter(([,v])=>v));
      try {comparison=await page.evaluate(async ({symbols,markets})=>{
        window.panelQuotes.watch(symbols,markets);
        const deadline=Date.now()+6000;
        while(Date.now()<deadline && Object.keys(markets).some(s=>!window.panelQuotes.best(s))) {
          await new Promise(resolve=>setTimeout(resolve,150));
        }
        const at=Date.now();
        return {captured_at:at,quotes:Object.fromEntries(symbols.map(s=>[s,window.panelQuotes.best(s,at)])),feed_checks:window.panelQuotes.evidence()};
      },{symbols:watch,markets});} catch(e) {comparison={error:e.message};}
    }
  }
  const at=Date.now(), quotes={}, missing=[];
  for(const s of request.symbols) {
    const q=quote(s,at,markets?.[s]);
    if(q) quotes[s]=q; else missing.push(s);
  }
  const book={captured_at:at,requested:request.symbols.length,quotes,missing,source_errors:Object.fromEntries(feed.errors)};
  book.markets=markets || Object.fromEntries(Object.entries(quotes).map(([s,q])=>[s,q.venue]));
  if(comparison) {
    book.feed_checks=feed.evidence();
    book.panel_comparison=comparison;
    if(!request.symbols.includes('UMXUSDT')) book.probe_umx=quote('UMXUSDT',at,markets?.UMXUSDT);
  }
  return book;
}
try {
  for await(const line of createInterface({input:process.stdin})) {
    try {process.stdout.write(JSON.stringify(await snapshot(JSON.parse(line)))+'\n');}
    catch(e) {process.stdout.write(JSON.stringify({error:e.message})+'\n');}
  }
} finally {feed.close();await browser?.close();}
