#!/usr/bin/env python3
"""
Hamid Agent — Autonomous hourly analysis script.
Runs via Claude Routine (server-side cron), commits findings to repo.
"""
import json, math, time, urllib.request, urllib.error, os
from datetime import datetime, timezone

FAPI = "https://fapi.binance.com"
COINgecko = "https://api.coingecko.com/api/v3/global"
FNG = "https://api.alternative.me/fng/?limit=1"
TOP_N = 20
LOG_FILE = os.path.join(os.path.dirname(__file__), "hamid-log.json")
MAX_LOG = 48  # keep last 48 hourly entries

LOCKED = dict(
    min_signal_score=74, watch_score=62, ready_score=70,
    strong_signal_score=82, min_quote_volume_usd=25_000_000, min_rr=1.8
)

def fetch(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "HamidAgent/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def sma(a, p):
    if len(a) < p: return None
    return sum(a[-p:]) / p

def ema_series(a, p):
    if len(a) < p: return []
    k = 2 / (p + 1)
    o = [None] * p
    prev = sum(a[:p]) / p
    o[p-1] = prev
    for x in a[p:]:
        prev = x * k + prev * (1 - k)
        o.append(prev)
    return o

def ema_last(a, p):
    s = ema_series(a, p)
    return next((x for x in reversed(s) if x is not None), a[-1])

def rsi_wilder(c, p=14):
    if len(c) < p + 1: return 50
    g = l = 0
    for i in range(1, p + 1):
        d = c[i] - c[i-1]
        if d >= 0: g += d
        else: l -= d
    g /= p; l /= p
    for i in range(p + 1, len(c)):
        d = c[i] - c[i-1]
        g = (g * (p-1) + (d if d > 0 else 0)) / p
        l = (l * (p-1) + (-d if d < 0 else 0)) / p
    return 100 if l == 0 else 100 - 100 / (1 + g / l)

def macd_hist(c, f=12, s=26, sg=9):
    if len(c) < s + sg: return 0
    ef, es = ema_series(c, f), ema_series(c, s)
    m = [ef[i] - es[i] for i in range(len(c)) if ef[i] is not None and es[i] is not None]
    if len(m) < sg: return 0
    sl = ema_series(m, sg)
    return m[-1] - sl[-1]

def atr_fn(h, l, c, p=14):
    if len(c) < p + 1:
        return (h[-1] - l[-1]) or c[-1] * 0.004
    tr = [max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1])) for i in range(1, len(c))]
    a = sum(tr[:p]) / p
    for t in tr[p:]: a = (a * (p-1) + t) / p
    return a

def adx_fn(h, l, c, p=14):
    if len(c) < 2 * p: return 0
    tr, pdm, ndm = [], [], []
    for i in range(1, len(c)):
        up, dn = h[i]-h[i-1], l[i-1]-l[i]
        pdm.append(up if up > dn and up > 0 else 0)
        ndm.append(dn if dn > up and dn > 0 else 0)
        tr.append(max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1])))
    def wl(a):
        s = sum(a[:p]); o = [s]
        for x in a[p:]: s = s - s/p + x; o.append(s)
        return o
    T, P, N = wl(tr), wl(pdm), wl(ndm)
    dx = []
    for i in range(len(T)):
        pi, ni = 100*P[i]/(T[i] or 1), 100*N[i]/(T[i] or 1)
        sm = pi + ni
        dx.append(100 * abs(pi - ni) / sm if sm else 0)
    if len(dx) < p: return dx[-1] if dx else 0
    a = sum(dx[:p]) / p
    for d in dx[p:]: a = (a * (p-1) + d) / p
    return a

def bb_pos(c, p=20, m=2):
    if len(c) < p: return 50
    mid = sma(c, p)
    sd = math.sqrt(sum((c[i]-mid)**2 for i in range(len(c)-p, len(c))) / p)
    up, lo = mid + m*sd, mid - m*sd
    return max(0, min(100, 100 * (c[-1]-lo) / (up-lo))) if up != lo else 50

def tf_metrics(klines, tf):
    H = [k[2] for k in klines]
    L = [k[3] for k in klines]
    C = [k[4] for k in klines]
    V = [k[5] for k in klines]
    cl = C[-1]
    e9, e21, e50 = ema_last(C, 9), ema_last(C, 21), ema_last(C, min(50, len(C)-1))
    rsi = rsi_wilder(C)
    mh = macd_hist(C)
    adx = adx_fn(H, L, C)
    bb = bb_pos(C)
    a = atr_fn(H, L, C)
    lk = min(20, len(H))
    rh, rl = max(H[-lk:]), min(L[-lk:])
    vl = V[-min(20, len(V)):]
    vm = sum(vl) / len(vl)
    vsd = math.sqrt(sum((v-vm)**2 for v in vl) / len(vl)) or 1
    vz = (V[-1] - vm) / vsd
    ls = ss = 0
    if cl > e21: ls += 16
    else: ss += 16
    if e9 > e21: ls += 13
    else: ss += 13
    if e21 > e50: ls += 11
    else: ss += 11
    if mh > 0: ls += 20
    elif mh < 0: ss += 20
    if 50 <= rsi <= 72: ls += 14
    elif 28 <= rsi <= 50: ss += 14
    if rsi > 72: ss += 5
    if rsi < 28: ls += 5
    vc = max(0, min(3, vz))
    ls += vc * 6; ss += vc * 6
    if bb > 50: ls += 8
    else: ss += 8
    ls = max(0, min(100, ls)); ss = max(0, min(100, ss))
    direction = 'NEUTRAL'
    if ls - ss >= 8: direction = 'LONG'
    elif ss - ls >= 8: direction = 'SHORT'
    return dict(tf=tf, close=cl, ema9=e9, ema21=e21, rsi=round(rsi,1),
                macd_hist=round(mh,6), adx=round(adx,1), bb=round(bb,1),
                atr=a, recent_high=rh, recent_low=rl, volume_z=round(vz,2),
                long_score=round(ls,1), short_score=round(ss,1), direction=direction)

def get_klines(symbol, interval, limit):
    data = fetch(f"{FAPI}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}")
    return [[float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])] for k in data]
    # [open, high, low, close, volume]

def main():
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    log_entry = dict(timestamp=ts, signals=[], watching=[], market={}, activity=[])
    act = log_entry['activity']

    def note(msg):
        act.append(msg)
        print(msg)

    note(f"=== حمید Agent — {ts} ===")

    # Dominance
    try:
        dom = fetch(COINECKER := COINECKO if (COINECKO := COINECKER if False else COINECKER) else COINECKER)
    except:
        pass
    try:
        gdata = fetch(COINEGKO := COINEGKO if False else COINEGKO)
    except:
        gdata = None
    # Correct the variable name issue
    try:
        g = fetch("https://api.coingecko.com/api/v3/global")
        btc_dom = g['data']['market_cap_percentage'].get('btc', 0)
        eth_dom = g['data']['market_cap_percentage'].get('eth', 0)
        log_entry['market']['btc_dominance'] = round(btc_dom, 2)
        log_entry['market']['eth_dominance'] = round(eth_dom, 2)
        note(f"BTC Dominance: {btc_dom:.1f}% | ETH: {eth_dom:.1f}%")
        if btc_dom > 56:
            note("⚠️ BTC Season — altcoins weaker")
        elif btc_dom < 48:
            note("💡 Alt Season possible — BTC dom low")
    except Exception as e:
        note(f"⚠️ Dominance fetch failed: {e}")

    # Fear & Greed
    try:
        fg = fetch(FNG)
        fgv = int(fg['data'][0]['value'])
        fgl = fg['data'][0]['value_classification']
        log_entry['market']['fear_greed'] = fgv
        log_entry['market']['fear_greed_label'] = fgl
        note(f"Fear & Greed: {fgv} — {fgl}")
    except Exception as e:
        note(f"⚠️ Fear & Greed failed: {e}")

    # Top tickers
    try:
        tickers = fetch(f"{FAPI}/fapi/v1/ticker/24hr")
        tickers = [t for t in tickers if t['symbol'].endswith('USDT')]
        tickers.sort(key=lambda x: -float(x['quoteVolume']))
        tickers = tickers[:TOP_N]
        note(f"Got {len(tickers)} tickers from Binance")
    except Exception as e:
        note(f"❌ Ticker fetch failed: {e}")
        save_log(log_entry)
        return

    # Analyze
    for tk in tickers:
        sym = tk['symbol']
        try:
            k5  = get_klines(sym, '5m',  100)
            k15 = get_klines(sym, '15m', 180)
            k1h = get_klines(sym, '1h',  100)
            m5  = tf_metrics([[0,k[1],k[2],k[3],k[4]] for k in k5],  '5m')
            m15 = tf_metrics([[0,k[1],k[2],k[3],k[4]] for k in k15], '15m')
            m1h = tf_metrics([[0,k[1],k[2],k[3],k[4]] for k in k1h], '1h')
            lt = .35*m5['long_score']  + .40*m15['long_score']  + .25*m1h['long_score']
            st = .35*m5['short_score'] + .40*m15['short_score'] + .25*m1h['short_score']
            direction = 'NEUTRAL'
            if lt - st >= 6: direction = 'LONG'
            elif st - lt >= 6: direction = 'SHORT'
            tfa = sum(1 for m in [m5,m15,m1h] if m['direction'] == direction)
            score = max(0, min(100, lt if direction=='LONG' else st if direction=='SHORT' else max(lt,st)))
            cur, at = m15['close'], m15['atr']
            rr = 2.1
            vol_ok = float(tk['quoteVolume']) >= LOCKED['min_quote_volume_usd']
            trend_ok = (m15['adx'] >= 16 or m5['adx'] >= 18) and m15['adx'] >= 12
            enough = tfa >= 3 or (tfa >= 2 and score >= LOCKED['strong_signal_score'])
            status = 'NO_SETUP'
            if direction in ('LONG', 'SHORT'):
                if score >= LOCKED['min_signal_score'] and enough and trend_ok and rr >= LOCKED['min_rr'] and vol_ok:
                    status = 'SIGNAL'
                elif score >= LOCKED['ready_score'] and rr >= LOCKED['min_rr']:
                    status = 'WAITING_CONFIRMATION'
                elif score >= LOCKED['watch_score']:
                    status = 'WATCHING'
                else:
                    status = 'APPROACHING_ENTRY_ZONE'
            if not vol_ok: status = 'LOW_LIQUIDITY'
            if m15['adx'] < 14 and m5['adx'] < 14: status = 'RANGE_FILTERED'

            rec = dict(symbol=sym, direction=direction, score=round(score,1),
                       status=status, price=cur, rsi_15m=m15['rsi'], adx_15m=m15['adx'])
            if status == 'SIGNAL':
                log_entry['signals'].append(rec)
                note(f"⚡ SIGNAL: {sym} {direction} score={score:.1f}")
            elif status in ('WAITING_CONFIRMATION', 'WATCHING'):
                log_entry['watching'].append(rec)
            time.sleep(0.08)
        except Exception as e:
            pass  # skip failed symbols

    note(f"✅ Done — {len(log_entry['signals'])} signals, {len(log_entry['watching'])} watching")
    save_log(log_entry)

def save_log(entry):
    existing = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE) as f:
                existing = json.load(f)
            if not isinstance(existing, list):
                existing = []
        except:
            existing = []
    existing.insert(0, entry)
    existing = existing[:MAX_LOG]
    with open(LOG_FILE, 'w') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    print(f"Log saved: {LOG_FILE} ({len(existing)} entries)")

if __name__ == '__main__':
    main()
