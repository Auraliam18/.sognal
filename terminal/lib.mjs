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
