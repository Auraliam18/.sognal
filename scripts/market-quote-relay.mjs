// Public, read-only last prices for the two exchange REST feeds that lack browser CORS.
// Deploy as liam-market-quotes on the panel owner's workers.dev subdomain.
const venues = {
  'Bitunix futures': 'https://fapi.bitunix.com/api/v1/futures/market/tickers',
  'MEXC spot': 'https://api.mexc.com/api/v3/ticker/24hr',
};
const origin = 'https://auraliam18.github.io';
const ttl = 15000;
const batches = new Map();
const cors = {'Access-Control-Allow-Origin':origin, 'Cache-Control':'no-store', 'Vary':'Origin'};
let catalog;

async function readContracts() {
  const res=await fetch('https://fapi.bitunix.com/api/v1/futures/market/trading_pairs',{signal:AbortSignal.timeout(4500),cache:'no-store'});
  if (!res.ok) throw Error('contract directory unavailable');
  const body=await res.json();
  if (String(body.code)!=='0' || !Array.isArray(body.data)) throw Error('invalid contract directory');
  const active=new Set(body.data.filter(r=>r.symbolStatus==='OPEN' && r.quote==='USDT').map(r=>r.symbol));
  if (!active.size) throw Error('empty contract directory');
  return active;
}
function contracts() {
  if (!catalog || Date.now()-catalog.started>=60000) {
    const item=catalog={started:Date.now(),promise:readContracts()};
    item.promise.catch(()=>{if(catalog===item) catalog=null;});
  }
  return catalog.promise;
}

async function readBatch(venue) {
  const res = await fetch(venues[venue], {signal: AbortSignal.timeout(4500), cache: 'no-store'});
  if (!res.ok) throw Error('exchange unavailable');
  const body = await res.json();
  const futures = venue === 'Bitunix futures';
  const active = futures ? await contracts() : null;
  const rows = futures && body.code === 0 ? body.data : body;
  if (!Array.isArray(rows)) throw Error('invalid exchange response');
  const httpDate = Date.parse(res.headers.get('Date'));
  const quotes = new Map();
  for (const row of rows) {
    if (active && !active.has(row.symbol)) continue;
    const price = Number(row.lastPrice);
    const at = futures ? httpDate : Number(row.closeTime);
    if (typeof row.symbol === 'string' && row.symbol.endsWith('USDT') &&
        Number.isFinite(price) && price > 0 && Number.isSafeInteger(at)) {
      quotes.set(row.symbol, {symbol: row.symbol, price, at, venue});
    }
  }
  return quotes;
}

function batch(venue) {
  const cached = batches.get(venue);
  if (cached && Date.now() - cached.started < 4000) return cached.promise;
  const item = {started: Date.now(), promise: readBatch(venue)};
  batches.set(venue, item);
  item.promise.catch(() => { if (batches.get(venue) === item) batches.delete(venue); });
  return item.promise;
}

async function candles(params) {
  const symbol = params.get('symbol') || '';
  const venue = params.get('venue');
  const tf = params.get('tf');
  if (!/^[A-Z0-9]{1,20}USDT$/.test(symbol) || !['5m','15m','1h','4h','1d'].includes(tf) ||
      !Object.hasOwn(venues, venue)) return new Response(null, {status:400, headers:cors});
  const futures = venue === 'Bitunix futures';
  if (futures && !(await contracts()).has(symbol)) return new Response(null, {status:404, headers:cors});
  const url = new URL(futures ? 'https://fapi.bitunix.com/api/v1/futures/market/kline' : 'https://api.mexc.com/api/v3/klines');
  url.search = new URLSearchParams({symbol, interval: !futures && tf === '1h' ? '60m' : tf, limit:'200'});
  const res = await fetch(url, {signal:AbortSignal.timeout(4500)});
  if (!res.ok) throw Error('candles unavailable');
  const packet = await res.json();
  const rows = futures && String(packet.code) === '0' ? packet.data : packet;
  if (!Array.isArray(rows) || rows.length < 2) throw Error('insufficient candles');
  const bars = rows.map(r => (futures ? [r.time,r.open,r.high,r.low,r.close] : r.slice(0,5)).map(Number))
                   .sort((a,b)=>a[0]-b[0]);
  const valid = bars.filter(([t,o,h,l,c],i)=>Number.isSafeInteger(t) && t>0 && (!i || t>bars[i-1][0]) &&
      [o,h,l,c].every(n=>Number.isFinite(n) && n>0) && h>=Math.max(o,c) && l<=Math.min(o,c));
  if (valid.length<2 || valid.at(-1)!==bars.at(-1)) throw Error('invalid candles');
  return Response.json(valid,{headers:cors});
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (request.method !== 'GET') return new Response(null, {status:404});
    if (request.headers.has('Origin') && request.headers.get('Origin') !== origin) return new Response(null, {status:403});
    if (url.pathname==='/v1/candles') {
      try {return await candles(url.searchParams);}
      catch {return new Response(null,{status:503,headers:cors});}
    }
    if (url.pathname==='/v1/bitunix-contracts') {
      try {return Response.json({symbols:[...await contracts()]},{headers:cors});}
      catch {return new Response(null,{status:503,headers:cors});}
    }
    if (url.pathname!=='/v1/tickers') return new Response(null,{status:404});
    const symbols = [...new Set((url.searchParams.get('symbols') || '').split(','))];
    if (symbols.length > 300 || symbols.some(s => s.length > 48 || !s.endsWith('USDT'))) return new Response(null, {status:400});
    const quotes = [], unavailable = [];
    await Promise.all(Object.keys(venues).map(async venue => {
      try {
        const data = await batch(venue);
        for (const symbol of symbols) {
          const q = data.get(symbol);
          if (q && Date.now() - q.at <= ttl && q.at <= Date.now() + 2000) quotes.push(q);
        }
      } catch { unavailable.push(venue); }
    }));
    return Response.json({quotes, unavailable}, {headers:{
      'Access-Control-Allow-Origin':origin, 'Cache-Control':'no-store', 'Vary':'Origin',
    }});
  },
};
