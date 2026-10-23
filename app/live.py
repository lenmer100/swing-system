"""Tagesdaten live (Yahoo Finance über yfinance, frei, ca. 15 Min. verzögert je Börse): Indizes intraday und
Tageskurse des Pools. Nur Kurs, Tagesveränderung und Intraday-Chart sind live; alle Langfrist-Rechnungen
(Fair Value, Einstiegsplan) bleiben auf dem Schlusskurs des Vortags. Fällt die Quelle aus, gelten die Snapshot-Schlusskurse."""
import threading, time, datetime as dt
import pandas as pd
import streamlit as st
from lib import D, prices

REFRESH = 300
IDX = [("SPX", "S&P 500", "^GSPC", 2), ("NDX", "Nasdaq 100", "^NDX", 2), ("ES", "S&P 500 Future", "ES=F", 2), ("NQ", "Nasdaq 100 Future", "NQ=F", 2), ("DAX", "DAX", "^GDAXI", 2), ("VIX", "VIX", "^VIX", 2),
       ("GOLD", "Gold", "GC=F", 2), ("TNX", "US-Rendite 10 J.", "^TNX", 3), ("EURUSD", "EUR/USD", "EURUSD=X", 4), ("BRENT", "Brent", "BZ=F", 2),
       ("BTC", "Bitcoin", "BTC-USD", 0)]
YF = {k: y for k, _, y, _ in IDX}
NAME = {k: n for k, n, _, _ in IDX}
DEC = {k: d for k, _, _, d in IDX}
UNIT = {"TNX": " %", "GOLD": " USD", "BRENT": " USD", "BTC": " USD"}
SNAP = {"SPX": "SPY", "NDX": "QQQ", "VIX": "VIX", "GOLD": "GOLD", "TNX": "TNX", "EURUSD": "EURUSD", "BRENT": "BRENT"}   # Fallback-Reihen
SPANS = {"1T": ("1d", "5m"), "5T": ("5d", "30m"), "1M": ("1mo", "1d"), "YTD": ("ytd", "1d"), "1J": ("1y", "1d"), "5J": ("5y", "1wk")}
BERLIN = "Europe/Berlin"

def _yf():
    import yfinance as yf
    return yf

def _close(df, t):
    try:
        s = (df[t] if isinstance(df.columns, pd.MultiIndex) else df)["Close"].dropna()
        return s
    except Exception:
        return pd.Series(dtype=float)

@st.cache_data(ttl=REFRESH, show_spinner=False)
def index_series(span="1T"):
    """{key: Series(Close, Index Berliner Zeit)} für alle Marktwerte; leer bei Ausfall."""
    per, iv = SPANS[span]
    try:
        df = _yf().download(list(YF.values()), period=per, interval=iv, progress=False, group_by="ticker", threads=True, auto_adjust=False)
    except Exception:
        return {}
    out = {}
    for k, y in YF.items():
        s = _close(df, y)
        if len(s):
            if s.index.tz is not None: s.index = s.index.tz_convert(BERLIN)
            if span == "1T":   # nur die letzte Sitzung
                last = s.index[-1].date(); s = s[[i.date() == last for i in s.index]]
            out[k] = s
    return out

@st.cache_data(ttl=REFRESH, show_spinner=False)
def index_quotes():
    """{key: dict(last, prev, ts)} mit Vortagesschluss aus Tagesdaten (exakt), Kurs aus dem letzten 5-Min.-Wert."""
    try:
        d = _yf().download(list(YF.values()), period="10d", interval="1d", progress=False, group_by="ticker", threads=True, auto_adjust=False)
    except Exception:
        d = None
    intr = index_series("1T"); out = {}
    for k, y in YF.items():
        s = _close(d, y) if d is not None else pd.Series(dtype=float)
        i = intr.get(k)
        if len(s) < 2 or i is None or not len(i): continue
        sess = i.index[-1].date()
        dates = [x.date() for x in s.index]
        prev = s[[x < sess for x in dates]]
        if not len(prev): continue
        out[k] = dict(last=float(i.iloc[-1]), prev=float(prev.iloc[-1]), ts=i.index[-1], live=True)
    return out

def snapshot_series(key):
    """Fallback: Snapshot-Tagesreihe (Schlusskurse)."""
    f = D / f"market_hist_{SNAP.get(key, key)}.parquet"
    if not f.exists(): return None
    df = pd.read_parquet(f); c = "close" if "close" in df else df.columns[-1]
    dc = "date" if "date" in df else None
    s = df.set_index(pd.to_datetime(df[dc]))[c] if dc else df[c]
    return s.dropna()

# ---------------------------------------------------------------- Pool-Tageskurse: Hintergrund-Thread, alle 5 Min.
class _Pool:
    def __init__(self, syms):
        self.syms = syms; self.data = {}; self.ts = None; self.lock = threading.Lock()
        threading.Thread(target=self._loop, daemon=True).start()
    def _loop(self):
        while True:
            try:
                df = _yf().download(self.syms, period="5d", interval="1d", progress=False, group_by="ticker", threads=True, auto_adjust=False)
                out = {}
                for s in self.syms:
                    c = _close(df, s)
                    if len(c) >= 2: out[s] = (float(c.iloc[-1]), float(c.iloc[-2]), c.index[-1].strftime("%Y-%m-%d"))
                if len(out) > len(self.syms) * 0.5:
                    with self.lock: self.data, self.ts = out, dt.datetime.now()
            except Exception:
                pass
            time.sleep(REFRESH)

# ---------------------------------------------------------------- Vor- und nachbörsliche Kurse (US), alle 5 Min.
ET = "America/New_York"
class _Ext:
    """{sym: dict(last, close, sess 'pre'|'post', ts Berlin)} – nur, wenn außerhalb der regulären US-Sitzung gehandelt wurde."""
    def __init__(self, syms):
        self.syms = [s for s in syms if "." not in s]; self.data = {}; self.lock = threading.Lock()
        threading.Thread(target=self._loop, daemon=True).start()
    def _loop(self):
        while True:
            try:
                out = {}
                for i in range(0, len(self.syms), 400):
                    df = _yf().download(self.syms[i:i + 400], period="5d", interval="5m", prepost=True, progress=False,
                                        group_by="ticker", threads=True, auto_adjust=False)
                    for s in self.syms[i:i + 400]:
                        c = _close(df, s)
                        if len(c) < 2: continue
                        if c.index.tz is None: c.index = c.index.tz_localize("UTC")
                        c = c.tz_convert(ET); hm = c.index.hour * 60 + c.index.minute
                        reg = c[(hm >= 570) & (hm < 960)]
                        if not len(reg): continue
                        t = c.index[-1]; tm = t.hour * 60 + t.minute
                        if t.date() > reg.index[-1].date() and tm < 570: sess = "pre"
                        elif t.date() == reg.index[-1].date() and tm >= 960: sess = "post"
                        else: continue
                        close = float(reg.iloc[-1])
                        out[s] = dict(last=float(c.iloc[-1]), close=close, sess=sess, ts=t.tz_convert(BERLIN))
                with self.lock: self.data = out
            except Exception:
                pass
            time.sleep(REFRESH)

@st.cache_resource(show_spinner=False)
def _ext(syms):
    return _Ext(list(syms))

def ext_quotes(syms):
    p = _ext(tuple(syms))
    with p.lock: return dict(p.data)

EXT_LAB = {"pre": "Vorbörslich", "post": "Nachbörslich"}
def ext_tag(e):
    """'Vorbörslich +1,2 % · 11:05 Uhr' (Veränderung zum letzten regulären Schluss)."""
    from lib import fpct
    ch = e["last"] / e["close"] - 1
    return f'{EXT_LAB[e["sess"]]} {"+" if ch >= 0 else "−"}{fpct(abs(ch), 1)} · {e["ts"].strftime("%H:%M" if e["ts"].date() == dt.date.today() else "%d.%m. %H:%M")} Uhr'

@st.cache_resource(show_spinner=False)
def _pool(syms):
    return _Pool(list(syms))

def pool_quotes(syms):
    """{sym: (last, prev, date)} live (wenn der Hintergrundlauf Daten hat), sonst Snapshot-Schlusskurse. + Zeitstempel oder None."""
    p = _pool(tuple(syms))
    with p.lock: data, ts = dict(p.data), p.ts
    return data, ts

def snap_quote(sym):
    px = prices(sym); return float(px.close.iloc[-1]), float(px.close.iloc[-2]), px.date.iloc[-1].strftime("%Y-%m-%d")

@st.cache_data(ttl=REFRESH, show_spinner=False)
def stock_intraday(syms):
    """Intraday-Kurve (5 Min.) der letzten Sitzung je Aktie; leer bei Ausfall."""
    try:
        df = _yf().download(list(syms), period="1d", interval="5m", progress=False, group_by="ticker", threads=True, auto_adjust=False)
    except Exception:
        return {}
    return {s: _close(df, s).tolist() for s in syms if len(_close(df, s))}

# ---------------------------------------------------------------- Zahlentermine: Detaildaten beim Anklicken
@st.cache_data(ttl=3600, show_spinner=False)
def implied_move(sym, date):
    """Erwartete Bewegung aus Optionen: ATM-Straddle des ersten Verfalls am/nach dem Termin ÷ Kurs. None ohne Optionsdaten."""
    try:
        t = _yf().Ticker(sym); exps = [e for e in t.options if e >= date]
        if not exps: return None
        ch = t.option_chain(exps[0]); px = t.fast_info["last_price"]
        c = ch.calls.iloc[(ch.calls.strike - px).abs().argsort()[:1]]; p = ch.puts.iloc[(ch.puts.strike - px).abs().argsort()[:1]]
        mid = lambda r: (r.bid.iloc[0] + r.ask.iloc[0]) / 2 if r.bid.iloc[0] > 0 and r.ask.iloc[0] > 0 else r.lastPrice.iloc[0]
        v = (mid(c) + mid(p)) / px
        return dict(move=float(v), expiry=exps[0], strike=float(c.strike.iloc[0])) if 0 < v < 1 else None
    except Exception:
        return None

# ---------------------------------------------------------------- Marktleiste oben (jede Seite), gleiche Quelle wie die Startseite
STRIP = ["SPX", "NDX", "ES", "NQ", "DAX", "VIX", "GOLD", "TNX", "EURUSD", "BRENT"]

def day_tag(d):
    """Kennzeichnung einer Tagesveränderung: 'heute' nur, wenn der Wert aus der laufenden Sitzung stammt."""
    if d is None: return "Schluss"
    if isinstance(d, str): d = dt.date.fromisoformat(d[:10])
    elif hasattr(d, "hour"): d = d.date()
    return "heute" if d == dt.date.today() else f"Schluss {d.strftime('%d.%m.')}"

@st.fragment(run_every=REFRESH)
def strip():
    from lib import fnum, pill, load_v3, fdate
    q = index_quotes(); src = "live"
    if len(q) < 5:
        m = {x["key"]: x for x in load_v3()[0]}; q = {}; src = "snap"
        for k, s in SNAP.items():
            x = m.get(s)
            if x and x.get("last") is not None: q[k] = dict(last=x["last"], prev=x["prev"], ts=None)
    items = []
    for k in STRIP:
        v = q.get(k)
        if not v: continue
        link = f'/aktienanalyse?m={SNAP[k]}' if k in SNAP else None
        tg = day_tag(v.get("ts")) if src == "live" else None
        body = f'<b>{NAME[k]}</b><span>{fnum(v["last"], DEC[k])}{UNIT.get(k, "") if k == "TNX" else ""}</span>{pill(v["last"] / v["prev"] - 1, 2)}' + (f'<i class="dtag">{tg}</i>' if tg and tg != "heute" else "")
        items.append(f'<a class="it" href="{link}" target="_self">{body}</a>' if link else f'<span class="it">{body}</span>')
    ts = max((v["ts"] for v in q.values() if v.get("ts") is not None), default=None)
    asof = f'Live · {ts.strftime("%H:%M")} Uhr' if src == "live" and ts is not None else "Schlusskurse " + fdate(__import__("common").META["asof"])
    st.markdown('<style>.mstrip .dtag{font-style:normal;font-size:11px;color:var(--muted);margin-left:4px}@media (max-width:640px){.mstrip{overflow-x:auto !important}}</style>' + f'<div class="mstrip">{"".join(items)}<span class="asof">{asof}</span></div>', unsafe_allow_html=True)
