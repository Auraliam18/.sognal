export const escapeHTML = value => String(value ?? '—').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const numeric = value => typeof value === 'number' && Number.isFinite(value);
export function timestamp(value) { return numeric(value) && value > 0 ? (value > 1e11 ? value : value * 1000) : null; }
export function freshness(feed, now = Date.now()) {
  if (!feed || feed.data == null) return 'missing';
  const ts = timestamp(feed.generated);
  if (!ts) return 'unknown';
  if (ts - now > 300000) return 'clock_error';
  return now - ts <= feed.ttl * 1000 ? 'fresh' : 'stale';
}
export function validateSnapshot(s) {
  if (!s || s.schema_version !== 1 || s.live_execution !== false || !s.feeds || !s.ledger || !Array.isArray(s.ledger.pages) || !Array.isArray(s.engines) || s.engines.length !== 26) throw new Error('قرارداد دادهٔ پنل معتبر نیست.');
  if (s.engines.some((e,i) => e.id !== `E${String(i).padStart(2,'0')}`)) throw new Error('شناسه‌های ایجنت‌ها معتبر نیست.');
  if (!numeric(s.generated) || !numeric(s.ledger.records) || s.ledger.pages.reduce((n,p)=>n+p.count,0)!==s.ledger.records) throw new Error('شمارش آرشیو با قرارداد داده سازگار نیست.');
  for (const p of s.ledger.pages) if (!/^history\/[a-f0-9]{16}\.json$/.test(p.url)) throw new Error('مسیر آرشیو معتبر نیست.');
  return s;
}
export function engineState(e, feeds, ledger, now = Date.now(), engines = null, trail = []) {
  const own = ownState(e, feeds, ledger, now);
  if (own !== 'fresh') return own;
  if (trail.includes(e.id)) return 'partial';
  if (engines && (e.dependencies || []).some(id => {
    const d = engines.find(x => x.id === id);
    return !d || engineState(d,feeds,ledger,now,engines,[...trail,e.id]) !== 'fresh';
  })) return 'partial';
  return !engines && e.blocked_dependencies?.length ? 'partial' : own;
}
function ownState(e, feeds, ledger, now) {
  if (e.feed === 'ledger' && !ledger.available) return 'missing';
  if (e.feed === 'terminal') return 'fresh';
  const primary = e.feed === 'ledger' ? {data:ledger,generated:ledger.computed_at,ttl:3600} : feeds[e.feed];
  const state = freshness(primary, now);
  if (state !== 'fresh') return state;
  if (e.evidence_ttl) {
    const evidenceState = freshness({data:e.evidence,generated:e.observed_at,ttl:e.evidence_ttl},now);
    if (evidenceState !== 'fresh') return evidenceState;
  }
  if (e.feed === 'conformance' && feeds[e.feed]?.data?.ok === false) return 'attention';
  return e.own_state === "partial" || e.missing?.length ? 'partial' : 'fresh';
}
export function historyPages(pages, book, symbol) {
  const sym = symbol.trim().toUpperCase();
  return pages.filter(p => (!book || p.books.includes(book)) && (!sym || p.symbols.some(s => s.includes(sym))));
}
export function filterRows(rows, book, symbol) {
  const sym = symbol.trim().toUpperCase();
  return rows.filter(r => (!book || r.book === book) && (!sym || String(r.sym).toUpperCase().includes(sym)));
}
export async function getJSON(url, {signal, timeout=15000, cache='no-cache'}={}) {
  const abort = new AbortController();
  const onAbort = () => abort.abort();
  if (signal?.aborted) abort.abort(); else signal?.addEventListener('abort',onAbort,{once:true});
  const timer = setTimeout(()=>abort.abort(),timeout);
  try { const response = await fetch(url,{signal:abort.signal,cache}); if (!response.ok) throw new Error(`HTTP ${response.status}`); return await response.json(); }
  finally { clearTimeout(timer); signal?.removeEventListener('abort',onAbort); }
}
export function csv(rows) {
  if (!rows.length) return '';
  const keys=Object.keys(rows[0]);
  const cell=v=>'"'+String(v??'').replace(/^[=+@\-]/,"'$&").replaceAll('"','""')+'"';
  return '\uFEFF'+[keys.map(cell).join(','),...rows.map(r=>keys.map(k=>cell(r[k])).join(','))].join('\r\n');
}

// A price is bound to one instrument, one venue and the exchange's timestamp.
export const QUOTE_TTL = 15000;
export function marketQuote(symbol, price, at, venue, now = Date.now()) {
  if (typeof symbol !== 'string' || !symbol.endsWith('USDT') || (typeof price !== 'number' && typeof price !== 'string')) return null;
  price = Number(price); at = Number(at);
  if (!Number.isFinite(price) || price <= 0 || !Number.isSafeInteger(at) || at < now - QUOTE_TTL || at > now + 2000) return null;
  return {symbol, price, at, venue};
}

// Wire fields used by the exchange's PublicMiniTickersV3Api and PushDataV3ApiWrapper.
function fields(bytes, visit) {
  let i=0;
  function integer() {
    let value=0, factor=1;
    for (let n=0; n<8 && i<bytes.length; n++) {
      const byte=bytes[i++];
      value+=(byte&127)*factor;
      if (!Number.isSafeInteger(value)) break;
      if (byte<128) return value;
      factor*=128;
    }
    throw Error('invalid protobuf integer');
  }
  while (i<bytes.length) {
    const tag=integer(), wire=tag%8, field=Math.floor(tag/8);
    if (!field) throw Error('invalid protobuf field');
    if (wire===0) {visit(field,integer());continue;}
    const size=wire===2?integer():wire===1?8:wire===5?4:-1;
    if (size<0 || size>bytes.length-i) throw Error('invalid protobuf length');
    const part=bytes.subarray(i,i+size);i+=size;
    if (wire===2) visit(field,part);
  }
}
const decoder=new TextDecoder();
export function mexcTickers(buffer, accept) {
  if (!(buffer instanceof ArrayBuffer) || buffer.byteLength>2000000) return;
  let batch,single,ts;
  fields(new Uint8Array(buffer),(id,v)=>{
    if(id===310 && v instanceof Uint8Array) batch=v;
    if(id===309 && v instanceof Uint8Array) single=v;
    if(id===6 && typeof v==='number') ts=v;
  });
  if(!ts) return;
  function readItem(item) {
    let sym,px;
    fields(item,(k,v)=>{
      if(v instanceof Uint8Array && k===1) sym=decoder.decode(v);
      if(v instanceof Uint8Array && k===2) px=decoder.decode(v);
    });
    accept(sym,px,ts);
  }
  if(single) readItem(single);
  if(batch) fields(batch,(id,item)=>{if(id===1 && item instanceof Uint8Array) readItem(item);});
}

function priceSocket(url, subscribe, receive, ping, onState) {
  let socket, retryAt=0, backoff=1000, lastData=0, lastPing=0;
  function stop() {
    if(!socket) return;
    const old=socket;socket=null;
    old.onclose=old.onmessage=old.onopen=old.onerror=null;
    old.close();
  }
  function delay(now) {retryAt=now+backoff;backoff=Math.min(backoff*2,30000);}
  function tick(now) {
    if(socket && now-lastData>25000) {stop();delay(now);}
    if(!socket && now>=retryAt) {
      try {
        const ws=socket=new WebSocket(url);
        ws.binaryType='arraybuffer';lastData=lastPing=now;
        ws.onopen=()=>{if(subscribe) ws.send(JSON.stringify(subscribe()));onState?.('subscribed');};
        ws.onmessage=e=>{
          try {if(receive(e.data)) {lastData=Date.now();backoff=1000;}}
          catch { /* Discard malformed messages without renewing their lifetime. */ }
        };
        ws.onclose=e=>{if(ws===socket){socket=null;onState?.('closed '+e.code);delay(Date.now());}};
        ws.onerror=()=>{onState?.('error');ws.close();};
      } catch {stop();delay(now);}
    }
      if(ping && socket?.readyState===WebSocket.OPEN && now-lastPing>=10000) {
        const msg=ping(now);
        socket.send(typeof msg==='string'?msg:JSON.stringify(msg));lastPing=now;
    }
  }
  return {tick,reset(){stop();retryAt=0;backoff=1000;}};
}


export function livePrices(onChange, {direct=false,inspect={}}={}) {
  const books = new Map(), order = ['Bitunix futures','OKX swap','Bitget spot','MEXC spot','Binance spot'];
  const errors = new Map(), subscriptions = new Map();
  let wanted = new Set(), markets = new Map();
  let lastPoll = 0, pollAbort;
  let bitunixMarkets=new Set(), catalogAt=0;
  const relay='https://liam-market-quotes.phoenix-hamid-2026.workers.dev';
  const bitunixOpen=s=>Date.now()-catalogAt<120000 && bitunixMarkets.has(s);
  const diagnostics=Object.fromEntries(Object.keys(inspect).map(s=>[s,{venue:inspect[s],ticks:0,lastTick:null,maxGap:0}]));
  function save(q, transport='rest') {
    if (!q || !wanted.has(q.symbol)) return;
    const trace=diagnostics[q.symbol];
    if(trace?.venue===q.venue && transport==='websocket' && q.at>(trace.lastTick||0)) {
      if(trace.lastTick) trace.maxGap=Math.max(trace.maxGap,q.at-trace.lastTick);
      trace.lastTick=q.at;trace.ticks++;
    }
    const book = books.get(q.symbol) || new Map();
    const key=q.venue+' '+transport;
    if (!book.has(key) || book.get(key).at<=q.at) book.set(key,{...q,transport});
    books.set(q.symbol, book);
  }
  function best(sym, now = Date.now(), venue) {
    const required=venue || markets.get(sym);
    for (const v of required?[required]:order) {
      if (v==='Bitunix futures' && !bitunixOpen(sym)) continue;
      for (const transport of ['websocket','rest']) {
        const q = books.get(sym)?.get(v+' '+transport);
        if (q && q.at <= now+2000 && q.at >= now-QUOTE_TTL) return q;
      }
    }
    return null;
  }
  const bitunix=priceSocket('wss://fapi.bitunix.com/public/',
    ()=>({op:'subscribe',args:[...wanted].slice(0,300).map(symbol=>({symbol,ch:'tickers'}))}),
    raw=>{
      const m=JSON.parse(raw);
      if(m.op==='ping' && m.pong!=null) return true;
      if(m.ch!=='tickers' || !Array.isArray(m.data)) return false;
      for(const row of m.data) save(marketQuote(row.s,row.la,m.ts,order[0]),'websocket');
      return true;
    }, now=>({op:'ping',ping:Math.floor(now/1000)}));
  function receiveMexc(raw) {
      if(!(raw instanceof ArrayBuffer)) return false;
      mexcTickers(raw,(sym,price,at)=>save(marketQuote(sym,price,at,'MEXC spot'),'websocket'));
      return true;
  }
  const mexcUrl='wss://wbs-api.mexc.com/ws';
  const mexc=priceSocket(mexcUrl,()=>({method:'SUBSCRIPTION',params:['spot@public.miniTickers.v3.api.pb@UTC+8']}),receiveMexc,()=>({method:'PING'}));
  const binance=priceSocket('wss://data-stream.binance.vision/ws/!miniTicker@arr',null,raw=>{
    const packet=JSON.parse(raw);
    if(!Array.isArray(packet)) return false;
    for(const row of packet) if(wanted.has(row.s)) save(marketQuote(row.s,row.c,row.E,'Binance spot'),'websocket');
    return true;
  },null);
  function listedSocket(venue,symbols) {
    const state=msg=>{for(const s of symbols) if(diagnostics[s]?.venue===venue) diagnostics[s].socket=msg;};
    if(venue==='Bitunix futures') return priceSocket('wss://fapi.bitunix.com/public/',
      ()=>({op:'subscribe',args:symbols.flatMap(symbol=>['ticker','trade'].map(ch=>({symbol,ch})))}),raw=>{
        const m=JSON.parse(raw);
        if(m.op==='ping' && m.pong!=null) return true;
        if(m.ch==='trade' && Array.isArray(m.data) && symbols.includes(m.symbol)) {
          for(const r of m.data) save(marketQuote(m.symbol,r.p,Date.parse(r.t),venue),'websocket');
          return true;
        }
        if(m.ch!=='ticker' || !m.data || m.data.s!==m.symbol) return false;
        save(marketQuote(m.symbol,m.data.la,m.ts,venue),'websocket');
        return true;
      },now=>({op:'ping',ping:Math.floor(now/1000)}),state);
    if(venue==='MEXC spot') return priceSocket(mexcUrl,()=>({method:'SUBSCRIPTION',
      params:symbols.map(s=>'spot@public.miniTicker.v3.api.pb@'+s+'@UTC+8')}),receiveMexc,()=>({method:'PING'}));
    const okx=venue==='OKX swap';
    const args=okx?symbols.flatMap(s=>['tickers','trades'].map(channel=>({channel,instId:s.slice(0,-4)+'-USDT-SWAP'}))):
      symbols.map(s=>({instType:'SPOT',channel:'ticker',instId:s}));
    return priceSocket(okx?'wss://ws.okx.com/ws/v5/public':'wss://ws.bitget.com/v2/ws/public',()=>({op:'subscribe',args}),raw=>{
      if(raw==='pong') return true;
      const m=JSON.parse(raw);
      if(!Array.isArray(m.data) || !(okx?['tickers','trades']:['ticker']).includes(m.arg?.channel)) return false;
      for(const r of m.data) {
        if(okx && !r.instId?.endsWith('-USDT-SWAP')) continue;
        const sym=okx?r.instId.slice(0,-10)+'USDT':m.arg.instId;
        const price=okx?(m.arg.channel==='trades'?r.px:r.last):r.lastPr;
        save(marketQuote(sym,price,r.ts,venue),'websocket');
      }
      return true;
    },()=> 'ping',state);
  }
  function subscribeListedMarkets() {
    const needed=new Set();
    for(const venue of ['Bitunix futures','OKX swap','Bitget spot','MEXC spot']) {
      const symbols=[...wanted].filter(s=>{
        if(venue==='Bitunix futures' && !bitunixOpen(s)) return false;
        if(markets.has(s)) return markets.get(s)===venue;
        if(venue==='Bitunix futures') return true;
        // A cached ticker on another market must not prevent this subscription.
        return books.get(s)?.has(venue+' rest') || books.get(s)?.has(venue+' websocket');
      }).sort();
      for(let i=0;i<symbols.length;i+=25) {
        const chunk=symbols.slice(i,i+25),key=venue+' '+chunk.join(',');
        needed.add(key);
        if(!subscriptions.has(key)) subscriptions.set(key,listedSocket(venue,chunk));
      }
    }
    for(const [key,sub] of subscriptions) if(!needed.has(key)) {sub.reset();subscriptions.delete(key);}
  }
  async function poll() {
    const abort = pollAbort = new AbortController();
    const timeout=setTimeout(()=>abort.abort(),7500);
    // These two exchanges do not expose REST tickers to cross-origin browsers.
    // Their change-only streams can stay silent for an otherwise listed market.
    async function pollRelay(symbols) {
      const url = new URL(relay+'/v1/tickers');
      url.searchParams.set('symbols', symbols.join(','));
      const response = await fetch(url, {cache:'no-store', signal:abort.signal});
      if (!response.ok) throw Error('relay unavailable');
      const packet = await response.json();
      if (abort.signal.aborted || !Array.isArray(packet.quotes)) return;
      for (const row of packet.quotes) {
        if (row?.venue === 'Bitunix futures' || row?.venue === 'MEXC spot') {
          save(marketQuote(row.symbol, row.price, row.at, row.venue));
        }
      }
      onChange();
    }
    async function provider(url, venue) {
      const response=await fetch(url,{cache:'no-store',signal:abort.signal});
      if (!response.ok) throw Error('quote feed unavailable');
      const packet=await response.json();
      if (venue === 'Binance spot' || venue === 'MEXC spot') {
        if (abort.signal.aborted || !Array.isArray(packet)) return;
        for (const row of packet) {
          if (wanted.has(row.symbol)) save(marketQuote(row.symbol,row.lastPrice,row.closeTime,venue));
        }
        onChange();
        return;
      }
      if (abort.signal.aborted || !['0','00000'].includes(String(packet.code)) || !Array.isArray(packet.data)) return;
      for (const row of packet.data) {
        if (venue === 'OKX swap') {
          if (row.instId?.endsWith('-USDT-SWAP')) save(marketQuote(row.instId.slice(0,-10)+'USDT',row.last,row.ts,venue));
          } else if (venue==='Bitunix futures') {
            save(marketQuote(row.symbol,row.lastPrice,Date.parse(response.headers.get('date')),venue));
          } else save(marketQuote(row.symbol,row.lastPr,row.ts,venue));
      }
      onChange();
    }
    try {
      const symbols = [...wanted], batches = [];
      if(Date.now()-catalogAt>=60000) batches.push((async()=>{
        const url=direct?'https://fapi.bitunix.com/api/v1/futures/market/trading_pairs':relay+'/v1/bitunix-contracts';
        try {
          const response=await fetch(url,{cache:'no-store',signal:abort.signal});
          if(!response.ok) throw Error('contract directory unavailable');
          const packet=await response.json();
          const rows=direct && String(packet.code)==='0'?packet.data.filter(r=>r.symbolStatus==='OPEN' && r.quote==='USDT').map(r=>r.symbol):packet.symbols;
          if(!Array.isArray(rows) || !rows.length) throw Error('empty contract directory');
          if(pollAbort===abort && !abort.signal.aborted) {bitunixMarkets=new Set(rows);catalogAt=Date.now();errors.delete('Bitunix contracts');}
        } catch(e) {if(pollAbort===abort) errors.set('Bitunix contracts',e.message);}
      })());
      if (!direct) for (let i=0; i<symbols.length; i+=100) batches.push(pollRelay(symbols.slice(i,i+100)));
      const sources=[
        ['OKX swap','https://www.okx.com/api/v5/market/tickers?instType=SWAP'],
        ['Bitget spot','https://api.bitget.com/api/v2/spot/market/tickers'],
        ['Binance spot','https://data-api.binance.vision/api/v3/ticker/24hr?type=MINI']
      ];
      if(direct) sources.push(['Bitunix futures','https://fapi.bitunix.com/api/v1/futures/market/tickers'],['MEXC spot','https://api.mexc.com/api/v3/ticker/24hr']);
      await Promise.allSettled([...batches,...sources.map(async ([venue,url])=>{
        try {await provider(url,venue); if(!abort.signal.aborted) errors.delete(venue);}
        catch(e) {if(pollAbort===abort) errors.set(venue,e.name);}
      })]);
      if(pollAbort===abort) subscribeListedMarkets();
    } finally { clearTimeout(timeout); if (pollAbort===abort) pollAbort=null; }
  }
  function tick() {
    if (!wanted.size || globalThis.document?.hidden) return;
    const now=Date.now();
    bitunix.tick(now); mexc.tick(now); binance.tick(now);
    for (const sub of subscriptions.values()) sub.tick(now);
    if (!pollAbort && now-lastPoll>=8000) {lastPoll=now; void poll();}
    onChange();
  }
  function watch(symbols, venues={}) {
    const next=new Set(symbols.filter(s=>typeof s==='string' && s.endsWith('USDT')));
    markets=new Map([...next].filter(s=>order.includes(venues[s])).map(s=>[s,venues[s]]));
    if (next.size===wanted.size && [...next].every(s=>wanted.has(s))) {
      subscribeListedMarkets();onChange();return;
    }
    reset(); wanted=next; books.clear(); errors.clear(); lastPoll=0;
    subscribeListedMarkets();
    tick();
  }
  function reset() {
    for(const sub of [bitunix,mexc,binance,...subscriptions.values()]) sub.reset();
    subscriptions.clear(); pollAbort?.abort(); pollAbort=null;
  }
  const timer=setInterval(tick,1000);
  function visibility() {
    if (document.hidden) reset();
    else {lastPoll=0;tick();}
  }
  globalThis.document?.addEventListener('visibilitychange',visibility);
  function close() {clearInterval(timer);reset();globalThis.document?.removeEventListener('visibilitychange',visibility);}
  function evidence() {
    return Object.fromEntries(Object.entries(diagnostics).map(([s,r])=>[s,{...r,
      contractOpen:r.venue==='Bitunix futures' && Date.now()-catalogAt<120000?bitunixMarkets.has(s):null,
      quote:best(s,Date.now(),r.venue)}]));
  }
  return {watch,best,close,errors,evidence};
}

