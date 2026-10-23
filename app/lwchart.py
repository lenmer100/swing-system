"""Kurschart mit TradingView Lightweight Charts™ v4.2.3 (Apache-2.0, unverändert eingebunden, Attribution-Logo aktiv).
Gesperrt: kein Scrollen/Zoomen/Ziehen; sichtbarer Bereich über den Zeitraum-Schalter."""
import json
import pandas as pd
import streamlit.components.v1 as components
from lib import ROOT, FONT

_JS = (ROOT / "vendor/lightweight-charts.standalone.production.js").read_text()
SPAN = {"6M": 182, "1J": 365, "3J": 365 * 3, "Max": None}

def swings(df, w=10, n=4):
    hi, lo = df.high.values, df.low.values
    out = []
    for i in range(w, len(df) - w):
        if hi[i] == hi[i - w:i + w + 1].max(): out.append(("H", i))
        if lo[i] == lo[i - w:i + w + 1].min(): out.append(("L", i))
    return [x for x in out if x[0] == "H"][-n:] + [x for x in out if x[0] == "L"][-n:]

def render(px, span="1J", lines=(), bands=(), show_swings=False, earnings=None, height=640):
    full = px.copy()
    full["sma50"] = full.close.rolling(50).mean(); full["sma200"] = full.close.rolling(200).mean()
    wk = full.set_index("date").close.resample("W-FRI").last().rolling(30).mean()
    full["w30"] = wk.reindex(full.date, method="ffill").values
    days = SPAN.get(span)
    view = full if days is None else full[full.date >= full.date.max() - pd.Timedelta(days=days)]
    t = lambda d: d.strftime("%Y-%m-%d")
    candles = [dict(time=t(r.date), open=r.open, high=r.high, low=r.low, close=r.close) for r in view.itertuples()]
    ser = lambda col: [dict(time=t(d), value=round(v, 4)) for d, v in zip(view.date, view[col]) if v == v]
    markers = []
    if show_swings:
        v = view.reset_index(drop=True)
        for kind, i in sorted(swings(v), key=lambda x: x[1]):
            r = v.iloc[i]
            val = r.high if kind == "H" else r.low
            markers.append(dict(time=t(r.date), position="aboveBar" if kind == "H" else "belowBar",
                                color="#b42318" if kind == "H" else "#067647", shape="arrowDown" if kind == "H" else "arrowUp",
                                text=("H " if kind == "H" else "T ") + f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")))
    lo, hi = float(view.low.min()), float(view.high.max())
    span_ = hi - lo
    for l in lines:   # Kernlinien (Einstieg, Stopp) nur einbeziehen, wenn sie nahe am Kursbereich liegen
        if l.get("core") and lo - 0.35 * span_ <= l["price"] <= hi + 0.35 * span_:
            lo, hi = min(lo, l["price"]), max(hi, l["price"])
    for b in bands:
        if b.get("core") and lo - 0.35 * span_ <= b["lo"] and b["hi"] <= hi + 0.35 * span_:
            lo, hi = min(lo, b["lo"]), max(hi, b["hi"])
    payload = dict(candles=candles, sma50=ser("sma50"), sma200=ser("sma200"), w30=ser("w30"), markers=markers,
                   lines=list(lines), bands=list(bands), earnings=earnings, lo=lo, hi=hi)
    html = f"""<!doctype html><html><head><style>
html,body{{margin:0;padding:0;background:#fff;font-family:{FONT};-webkit-user-select:none;user-select:none;overflow:hidden}}
*{{-webkit-user-drag:none;user-drag:none}}
#lg{{position:absolute;left:12px;top:8px;z-index:3;font-size:13px;color:#344054;pointer-events:none;font-variant-numeric:tabular-nums}}
#lg b{{color:#101828;font-weight:600}} .k{{display:inline-block;width:14px;height:3px;vertical-align:middle;margin:0 4px 0 12px;border-radius:2px}}
.lab{{position:absolute;z-index:4;font-size:12px;font-weight:600;line-height:16px;padding:0 6px;border-radius:4px;color:#fff;white-space:nowrap;pointer-events:none;font-variant-numeric:tabular-nums}}
.edge{{background:#fff !important;border:1px solid;font-weight:600}}
#fs{{position:absolute;right:76px;top:6px;z-index:6;font:600 12.5px {FONT};color:#337ab7;background:#fff;border:1px solid #c9dbee;border-radius:6px;padding:5px 11px;cursor:pointer}}
#fs:hover{{background:#f4f8fb}} body.full #wrap{{padding:14px 18px}}
.ev{{position:absolute;z-index:4;font-size:12px;font-weight:600;color:#b42318;background:#fff;border:1px solid #fda29b;border-radius:4px;padding:0 6px;line-height:16px;pointer-events:none;white-space:nowrap}}
</style></head><body>
<div id="wrap" style="position:relative"><div id="lg"><span id="ohlc"></span><br>
<span class="k" style="background:#f79009;margin-left:0"></span>50-Tage-Linie<span class="k" style="background:#7a5af8"></span>200-Tage-Linie<span class="k" style="background:#1849a9;height:4px"></span>30-Wochen-Linie</div>
<button id="fs" title="Chart im Vollbild anzeigen (Esc schließt)">Vollbild</button>
<div id="c" style="height:{height}px"></div><div id="labs"></div></div>
<script>{_JS}</script>
<script>
const P = {json.dumps(payload)};
const de = (x, d=2) => x.toLocaleString('de-DE', {{minimumFractionDigits: d, maximumFractionDigits: d}});
const chart = LightweightCharts.createChart(document.getElementById('c'), {{
  autoSize: true, handleScroll: {{mouseWheel: false, pressedMouseMove: false, horzTouchDrag: false, vertTouchDrag: false}}, handleScale: {{mouseWheel: false, pinch: false, axisPressedMouseMove: false, axisDoubleClickReset: false}}, kineticScroll: {{touch: false, mouse: false}},
  layout: {{background: {{color: '#ffffff'}}, textColor: '#344054', fontSize: 12, fontFamily: {json.dumps(FONT)}, attributionLogo: false}},
  localization: {{locale: 'de-DE', priceFormatter: p => de(p), timeFormatter: t => (typeof t === 'object' ? [String(t.day).padStart(2,'0'), String(t.month).padStart(2,'0'), t.year] : String(t).split('-').reverse()).join('.')}},
  grid: {{vertLines: {{color: '#f2f4f7'}}, horzLines: {{color: '#f2f4f7'}}}},
  rightPriceScale: {{borderColor: '#eaecf0', scaleMargins: {{top: .14, bottom: .08}}}},
  timeScale: {{borderColor: '#eaecf0', rightOffset: 0, fixLeftEdge: true, fixRightEdge: false, lockVisibleTimeRangeOnResize: true}},
  crosshair: {{mode: 0, vertLine: {{color: '#98a2b3', labelBackgroundColor: '#344054'}}, horzLine: {{color: '#98a2b3', labelBackgroundColor: '#344054'}}}} }});
const none = () => null;
const pad = (P.hi - P.lo) * 0.03;
const auto = () => ({{priceRange: {{minValue: P.lo - pad, maxValue: P.hi + pad}}}});
const days = P.candles.map(c => c.time);
P.bands.forEach(b => {{
  const s = chart.addBaselineSeries({{ baseValue: {{type: 'price', price: b.lo}}, topFillColor1: b.fill, topFillColor2: b.fill,
     topLineColor: 'rgba(0,0,0,0)', bottomFillColor1: 'rgba(0,0,0,0)', bottomFillColor2: 'rgba(0,0,0,0)', bottomLineColor: 'rgba(0,0,0,0)',
     priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, autoscaleInfoProvider: none }});
  s.setData(days.map(d => ({{time: d, value: b.hi}})));
  if (b.title) P.lines.push({{price: b.hi, color: b.line, title: b.title, style: 2}});
  if (b.title_lo) P.lines.push({{price: b.lo, color: b.line, title: b.title_lo, style: 2}});
}});
const cs = chart.addCandlestickSeries({{ upColor: '#12b76a', downColor: '#f04438', borderVisible: false, wickUpColor: '#12b76a',
  wickDownColor: '#f04438', autoscaleInfoProvider: auto, priceLineColor: '#475467' }});
cs.setData(P.candles); cs.setMarkers(P.markers);
const add = (data, color, w, step) => {{ const s = chart.addLineSeries({{color, lineWidth: w, lineType: step ? 1 : 0, priceLineVisible: false,
  lastValueVisible: false, crosshairMarkerVisible: false, autoscaleInfoProvider: none}}); s.setData(data); return s; }};
add(P.sma50, '#f79009', 1.5); add(P.sma200, '#7a5af8', 1.5); add(P.w30, '#1849a9', 2.5, true);
P.lines.forEach(l => cs.createPriceLine({{price: l.price, color: l.color, lineWidth: l.w || 1, lineStyle: l.style ?? 2, axisLabelVisible: false, title: ''}}));
if (P.earnings) {{
  const e = chart.addHistogramSeries({{priceScaleId: 'ev', color: 'rgba(180,35,24,.35)', priceLineVisible: false, lastValueVisible: false, autoscaleInfoProvider: () => ({{priceRange: {{minValue: 0, maxValue: 1}}}})}});
  chart.priceScale('ev').applyOptions({{scaleMargins: {{top: 0.1, bottom: 0}}, visible: false}});
  e.setData([{{time: P.earnings, value: 1}}]);
}}
{{ const _n = chart.timeScale().getVisibleLogicalRange() ? Math.round(chart.timeScale().getVisibleLogicalRange().to) + 1 : 0; chart.timeScale().fitContent(); const _r = chart.timeScale().getVisibleLogicalRange(); if (_r) {{ const _x = {{from: -0.5, to: _r.to + Math.max(12, Math.round((_r.to - _r.from) * .1))}}; chart.timeScale().setVisibleLogicalRange(_x); requestAnimationFrame(() => chart.timeScale().setVisibleLogicalRange(_x)); }} }}
function place() {{
  const box = document.getElementById('labs'); box.innerHTML = '';
  const H = document.getElementById('c').clientHeight - 28;   // ohne Zeitachse
  const right = chart.priceScale('right').width() + 4;
  const ins = [], up = [], dn = [];
  P.lines.forEach(l => {{
    const y = cs.priceToCoordinate(l.price);
    if (y === null || y < 4) up.push(l); else if (y > H - 4) dn.push(l); else ins.push({{l, y: Math.max(y, 46)}});  // oberer Rand: Legende und Vollbild-Schaltfläche freihalten
  }});
  ins.sort((a, b) => a.y - b.y);
  const G = 18;
  for (let i = 1; i < ins.length; i++) if (ins[i].y - ins[i-1].y < G) ins[i].y = ins[i-1].y + G;
  for (let i = ins.length - 1; i >= 0; i--) {{ const lim = (i === ins.length - 1 ? H - 9 : ins[i+1].y - G); if (ins[i].y > lim) ins[i].y = lim; }}
  const mk = (txt, css, top, edge, col) => {{ const d = document.createElement('div'); d.className = 'lab' + (edge ? ' edge' : ''); d.textContent = txt;
    d.style.cssText += css; d.style.top = top + 'px'; d.style.right = right + 'px';
    if (edge) {{ d.style.color = col; d.style.borderColor = col; }} else d.style.background = col; box.appendChild(d); }};
  ins.forEach(o => mk(o.l.title + '  ' + de(o.l.price), '', o.y - 8, false, o.l.color));
  up.sort((a, b) => a.price - b.price).forEach((l, i) => mk('↑ ' + l.title + '  ' + de(l.price), '', 44 + i * 19, true, l.color));
  dn.sort((a, b) => b.price - a.price).forEach((l, i) => mk('↓ ' + l.title + '  ' + de(l.price), '', H - 20 - i * 19, true, l.color));
  if (P.earnings) {{
    const x = chart.timeScale().timeToCoordinate(P.earnings);
    if (x !== null) {{ const d = document.createElement('div'); d.className = 'ev';
      d.textContent = 'Quartalszahlen ' + P.earnings.slice(8,10) + '.' + P.earnings.slice(5,7) + '.';
      d.style.top = (H - 22) + 'px'; d.style.right = (document.getElementById('c').clientWidth - x + 6) + 'px'; box.appendChild(d); }}
  }}
}}
requestAnimationFrame(() => requestAnimationFrame(place));
const FE = window.frameElement, H0 = {height};
let full = false, saved = '';
function setFull(on) {{
  full = on; document.body.classList.toggle('full', on);
  const pd = window.parent.document;
  if (FE) {{
    if (on) {{ saved = FE.getAttribute('style') || ''; FE.style.cssText = saved + ';position:fixed;inset:0;width:100vw;height:100vh;z-index:999999;background:#fff';
               pd.body.style.overflow = 'hidden'; }}
    else {{ FE.setAttribute('style', saved); pd.body.style.overflow = ''; }}
  }}
  document.getElementById('c').style.height = (on ? (window.parent.innerHeight - 30) : H0) + 'px';
  document.getElementById('fs').textContent = on ? 'Vollbild schließen' : 'Vollbild';
  setTimeout(place, 80);
}}
document.getElementById('fs').onclick = () => setFull(!full);
const esc = e => {{ if (e.key === 'Escape' && full) setFull(false); }};
document.addEventListener('keydown', esc); try {{ window.parent.document.addEventListener('keydown', esc); }} catch (e) {{}}
setTimeout(place, 300);
let _lw = 0; new ResizeObserver(e => {{ const w = Math.round(e[0].contentRect.width); if (w !== _lw) {{ _lw = w; setTimeout(place, 50); }} }}).observe(document.getElementById('c'));
const last = P.candles[P.candles.length - 1];
const showOhlc = c => {{ document.getElementById('ohlc').innerHTML = c ? `<b>${{c.time.split('-').reverse().join('.')}}</b> &nbsp; Eröffnung <b>${{de(c.open)}}</b> &nbsp; Hoch <b>${{de(c.high)}}</b> &nbsp; Tief <b>${{de(c.low)}}</b> &nbsp; Schluss <b>${{de(c.close)}}</b>` : ''; }};
showOhlc(last);
chart.subscribeCrosshairMove(p => {{ const d = p && p.seriesData ? p.seriesData.get(cs) : null; showOhlc(d ? Object.assign({{time: typeof p.time === 'object' ? `${{p.time.year}}-${{String(p.time.month).padStart(2,'0')}}-${{String(p.time.day).padStart(2,'0')}}` : String(p.time)}}, d) : last); }});
</script></body></html>"""
    components.html(html, height=height + 6)

# ---------------------------------------------------------------- v3: Kurschart der Aktienanalyse (ohne Einblendungen)
def render_clean(px, height=430, cur="USD"):
    """Reiner Kursverlauf: Fläche mit Verlauf oder Kerzen, Zeitraum-Schalter im Chart (ohne Neuladen). Gesperrt: kein Zoomen/Ziehen."""
    t = lambda d: d.strftime("%Y-%m-%d")
    data = [dict(time=t(r.date), open=round(r.open, 4), high=round(r.high, 4), low=round(r.low, 4), close=round(r.close, 4)) for r in px.itertuples()]
    html = f"""<!doctype html><html><head><style>
html,body{{margin:0;padding:0;background:#fff;font-family:{FONT};-webkit-user-select:none;user-select:none;overflow:hidden}}
.bar{{display:flex;justify-content:space-between;align-items:center;margin:0 0 8px}}
.g{{display:flex;gap:2px;background:#f4f8fb;border:1px solid #e3e8ef;border-radius:6px;padding:2px}}
.g button{{font:600 12.5px {FONT};color:#344054;background:transparent;border:0;border-radius:4px;padding:5px 10px;cursor:pointer}}
.g button.on{{background:#fff;color:#337ab7;box-shadow:0 1px 2px rgba(16,24,40,.12)}}
#lg{{font-size:13px;color:#5d6b7e;font-variant-numeric:tabular-nums}} #lg b{{color:#1d2939}}
.p{{display:inline-block;border-radius:5px;padding:1px 7px;font-weight:600;margin-left:6px}} .pos{{background:#e3f4ea;color:#1e7b45}} .neg{{background:#fbe9e7;color:#c0322b}}
</style></head><body>
<div class="bar"><div id="lg"></div><div style="display:flex;gap:10px"><div class="g" id="rg"></div><div class="g" id="ty"></div></div></div>
<div id="c" style="height:{height - 44}px"></div>
<script>{_JS}</script>
<script>
const D = {json.dumps(data)};
const de = (x, d=2) => x.toLocaleString('de-DE', {{minimumFractionDigits: d, maximumFractionDigits: d}});
const dd = s => s.split('-').reverse().join('.');
const chart = LightweightCharts.createChart(document.getElementById('c'), {{
  autoSize: true, handleScroll: {{mouseWheel: false, pressedMouseMove: false, horzTouchDrag: false, vertTouchDrag: false}}, handleScale: {{mouseWheel: false, pinch: false, axisPressedMouseMove: false, axisDoubleClickReset: false}}, kineticScroll: {{touch: false, mouse: false}},
  layout: {{background: {{color: '#ffffff'}}, textColor: '#5d6b7e', fontSize: 12, fontFamily: {json.dumps(FONT)}, attributionLogo: false}},
  localization: {{locale: 'de-DE', priceFormatter: p => de(p), timeFormatter: t => (typeof t === 'object' ? [String(t.day).padStart(2,'0'), String(t.month).padStart(2,'0'), t.year] : String(t).split('-').reverse()).join('.')}},
  grid: {{vertLines: {{visible: false}}, horzLines: {{color: '#eef2f6'}}}},
  rightPriceScale: {{borderVisible: false, scaleMargins: {{top: .08, bottom: .04}}}},
  timeScale: {{borderColor: '#e3e8ef', rightOffset: 0, fixLeftEdge: true, fixRightEdge: false, lockVisibleTimeRangeOnResize: true}},
  crosshair: {{mode: 1, vertLine: {{color: '#98a2b3', labelBackgroundColor: '#337ab7'}}, horzLine: {{color: '#98a2b3', labelBackgroundColor: '#337ab7'}}}} }});
let ser = null, kind = 'area', rng = '1J';
const R = {{'1M': 31, '6M': 183, '1J': 365, '3J': 1096, '5J': 1827, 'Max': null}};
function view() {{
  const days = R[rng]; if (!days) return D;
  const end = new Date(D[D.length-1].time); end.setDate(end.getDate() - days);
  const s = end.toISOString().slice(0, 10); return D.filter(x => x.time >= s);
}}
function legend(v, c) {{
  const f = v[0], l = c || v[v.length-1], ch = l.close / f.close - 1;
  document.getElementById('lg').innerHTML = `<b>${{dd(l.time)}}</b> &nbsp; Schluss <b>${{de(l.close)}} {cur}</b>` +
     (c ? ` &nbsp; Hoch ${{de(c.high)}} · Tief ${{de(c.low)}}` : ` <span class="p ${{ch >= 0 ? 'pos' : 'neg'}}">${{ch >= 0 ? '↑' : '↓'}} ${{de(Math.abs(ch) * 100)}} %</span> <span style="margin-left:4px">im Zeitraum</span>`);
}}
function draw() {{
  if (ser) chart.removeSeries(ser);
  const v = view(), up = v[v.length-1].close >= v[0].close;
  if (kind === 'area') {{
    ser = chart.addAreaSeries({{lineColor: '#337ab7', lineWidth: 2, topColor: 'rgba(51,122,183,.28)', bottomColor: 'rgba(51,122,183,.02)', priceLineVisible: false, lastValueVisible: true, crosshairMarkerRadius: 4}});
    ser.setData(v.map(x => ({{time: x.time, value: x.close}})));
  }} else {{
    ser = chart.addCandlestickSeries({{upColor: '#1e9e5a', downColor: '#d64541', borderVisible: false, wickUpColor: '#1e9e5a', wickDownColor: '#d64541', priceLineVisible: false}});
    ser.setData(v);
  }}
  {{ const _n = chart.timeScale().getVisibleLogicalRange() ? Math.round(chart.timeScale().getVisibleLogicalRange().to) + 1 : 0; chart.timeScale().fitContent(); const _r = chart.timeScale().getVisibleLogicalRange(); if (_r) {{ const _x = {{from: -0.5, to: _r.to + Math.max(12, Math.round((_r.to - _r.from) * .1))}}; chart.timeScale().setVisibleLogicalRange(_x); requestAnimationFrame(() => chart.timeScale().setVisibleLogicalRange(_x)); }} }} legend(v);
  document.querySelectorAll('#rg button').forEach(b => b.classList.toggle('on', b.textContent === rng));
  document.querySelectorAll('#ty button').forEach(b => b.classList.toggle('on', b.dataset.k === kind));
}}
const mk = (id, lab, on) => {{ const b = document.createElement('button'); b.textContent = lab; b.onclick = on; document.getElementById(id).appendChild(b); return b; }};
Object.keys(R).forEach(k => mk('rg', k, () => {{ rng = k; draw(); }}));
mk('ty', 'Linie', () => {{ kind = 'area'; draw(); }}).dataset.k = 'area';
mk('ty', 'Kerzen', () => {{ kind = 'candle'; draw(); }}).dataset.k = 'candle';
chart.subscribeCrosshairMove(p => {{ const v = view(); if (!p || !p.time) return legend(v);
  const t = typeof p.time === 'object' ? `${{p.time.year}}-${{String(p.time.month).padStart(2,'0')}}-${{String(p.time.day).padStart(2,'0')}}` : String(p.time);
  const c = D.find(x => x.time === t); legend(v, c); }});
draw();
</script></body></html>"""
    components.html(html, height=height)

# ---------------------------------------------------------------- v4: ruhiger Plan-Chart des Swing-Tools
def render_plan(px, zone, stop, target, extras=None, earnings=None, height=600, cur="USD"):
    """Standard: Kerzen, EIN Zonenband (hellgrün), EINE Stopplinie (rot), EINE Ziellinie (blau), max. 3 Achsenlabels.
    Linien (50/200-Tage, 30 Wochen), Unterstützungen und Zahlentermin nur über Schalter (aus). Kopfzeile über dem Chart statt Legende im Chart."""
    full = px.copy()
    full["sma50"] = full.close.rolling(50).mean(); full["sma200"] = full.close.rolling(200).mean()
    wk = full.set_index("date").close.resample("W-FRI").last().rolling(30).mean()
    full["w30"] = wk.reindex(full.date, method="ffill").values
    full = full[full.date >= full.date.max() - pd.Timedelta(days=365 * 3)]
    t = lambda d: d.strftime("%Y-%m-%d")
    C = [dict(time=t(r.date), open=round(r.open, 4), high=round(r.high, 4), low=round(r.low, 4), close=round(r.close, 4)) for r in full.itertuples()]
    ser = lambda col: [dict(time=t(d), value=round(v, 4)) for d, v in zip(full.date, full[col]) if v == v]
    cl = full.close.values; zs = len(cl) - 1; k = 0
    while zs > 0 and k < 120 and not cl[zs - 1] < zone[0] * 0.97: zs -= 1; k += 1
    P = dict(zstart=t(full.date.iloc[zs]), c=C, ma={"50-Tage-Linie": ser("sma50"), "200-Tage-Linie": ser("sma200"), "30-Wochen-Linie": ser("w30")}, zone=zone, stop=stop, target=target,
             sup=list(extras or []), earn=earnings)
    html = f"""<!doctype html><html><head><style>
html,body{{margin:0;padding:0;background:#fff;font-family:{FONT};-webkit-user-select:none;user-select:none;overflow:hidden}}
.bar{{display:flex;justify-content:space-between;align-items:center;gap:10px;margin:0 0 8px;flex-wrap:nowrap}}
.g{{display:flex;gap:2px;background:#f4f8fb;border:1px solid #e3e8ef;border-radius:6px;padding:2px}}
.g button,.chip{{font:600 12.5px {FONT};color:#344054;background:transparent;border:0;border-radius:4px;padding:5px 10px;cursor:pointer;white-space:nowrap}}
.g button.on{{background:#fff;color:#337ab7;box-shadow:0 1px 2px rgba(16,24,40,.12)}}
.chip{{border:1px solid #d0d7e2;border-radius:14px;padding:4px 11px;color:#5d6b7e;background:#fff}} .chip.on{{border-color:#337ab7;color:#337ab7;background:#eef4fa}}
#lg{{font-size:13px;color:#5d6b7e;font-variant-numeric:tabular-nums;white-space:nowrap}} #lg b{{color:#1d2939;font-weight:600}}
#fs{{font:600 12.5px {FONT};color:#337ab7;background:#fff;border:1px solid #c9dbee;border-radius:6px;padding:5px 11px;cursor:pointer}}
body.full{{padding:14px 18px}}
</style></head><body>
<div class="bar"><div id="lg"></div><div style="display:flex;gap:8px;align-items:center"><div class="g" id="rg"></div><button id="fs" title="Vollbild (Esc schließt)">Vollbild</button></div></div>
<div class="bar" style="justify-content:flex-start;gap:6px" id="chips"></div>
<div id="c" style="height:{height}px"></div>
<script>{_JS}</script>
<script>
const P = {json.dumps(P)};
const de = (x, d=2) => x.toLocaleString('de-DE', {{minimumFractionDigits: d, maximumFractionDigits: d}});
const dd = s => s.split('-').reverse().join('.');
const chart = LightweightCharts.createChart(document.getElementById('c'), {{
  autoSize: true, handleScroll: {{mouseWheel: false, pressedMouseMove: false, horzTouchDrag: false, vertTouchDrag: false}}, handleScale: {{mouseWheel: false, pinch: false, axisPressedMouseMove: false, axisDoubleClickReset: false}}, kineticScroll: {{touch: false, mouse: false}},
  layout: {{background: {{color: '#ffffff'}}, textColor: '#5d6b7e', fontSize: 12, fontFamily: {json.dumps(FONT)}, attributionLogo: false}},
  localization: {{locale: 'de-DE', priceFormatter: p => de(p), timeFormatter: t => (typeof t === 'object' ? [String(t.day).padStart(2,'0'), String(t.month).padStart(2,'0'), t.year] : String(t).split('-').reverse()).join('.')}},
  grid: {{vertLines: {{visible: false}}, horzLines: {{color: '#f2f4f7'}}}},
  rightPriceScale: {{borderVisible: false, scaleMargins: {{top: .08, bottom: .06}}}},
  timeScale: {{borderColor: '#e3e8ef', fixLeftEdge: true, fixRightEdge: false, lockVisibleTimeRangeOnResize: true, rightOffset: 0,
    tickMarkFormatter: (t, ty) => {{ const M = ['Jan','Feb','März','Apr','Mai','Juni','Juli','Aug','Sep','Okt','Nov','Dez']; const d = typeof t === 'object' ? t : (()=>{{const a = String(t).split('-'); return {{year: +a[0], month: +a[1]}};}})();
      return ty === 0 ? String(d.year) : ty === 1 ? M[d.month - 1] : ''; }} }},
  crosshair: {{mode: 1, vertLine: {{color: '#98a2b3', labelBackgroundColor: '#344054'}}, horzLine: {{color: '#98a2b3', labelBackgroundColor: '#344054'}}}} }});
const none = () => null;
let rng = '6M'; const R = {{'3M': 92, '6M': 183, '1J': 365, '3J': null}};
const view = () => {{ const d = R[rng]; if (!d) return P.c; const e = new Date(P.c[P.c.length-1].time); e.setDate(e.getDate() - d); const s = e.toISOString().slice(0,10); return P.c.filter(x => x.time >= s); }};
const band = chart.addBaselineSeries({{ baseValue: {{type: 'price', price: P.zone[0]}}, topFillColor1: 'rgba(30,123,69,.13)', topFillColor2: 'rgba(30,123,69,.13)',
  topLineColor: 'rgba(30,123,69,.45)', lineWidth: 1, bottomFillColor1: 'rgba(0,0,0,0)', bottomFillColor2: 'rgba(0,0,0,0)', bottomLineColor: 'rgba(0,0,0,0)',
  priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, autoscaleInfoProvider: none }});
const cs = chart.addCandlestickSeries({{ upColor: '#1e9e5a', downColor: '#d64541', borderVisible: false, wickUpColor: '#1e9e5a', wickDownColor: '#d64541',
  priceLineVisible: false, lastValueVisible: true }});
const pl = (price, color, title, w, st) => cs.createPriceLine({{price, color, lineWidth: w, lineStyle: st, axisLabelVisible: true, title}});
pl(P.zone[1], 'rgba(30,123,69,.9)', 'Zone', 1, 2);
pl(P.stop, '#c0322b', 'Stopp', 2, 0);
if (P.target) pl(P.target, '#337ab7', 'Ziel', 2, 0);
const MA_COL = {{'50-Tage-Linie': '#f79009', '200-Tage-Linie': '#7a5af8', '30-Wochen-Linie': '#1849a9'}};
const opt = {{}};
Object.keys(P.ma).forEach(k => {{ const s = chart.addLineSeries({{color: MA_COL[k], lineWidth: k === '30-Wochen-Linie' ? 2 : 1.5, lineType: k === '30-Wochen-Linie' ? 1 : 0, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, visible: false, autoscaleInfoProvider: none}}); opt[k] = {{s, on: false}}; }});
let supLines = [], earnS = null;
opt['Unterstützungen'] = {{on: false, set: on => {{ supLines.forEach(l => cs.removePriceLine(l)); supLines = on ? P.sup.map(v => cs.createPriceLine({{price: v, color: '#98a2b3', lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: ''}})) : []; }}}};
if (P.earn) opt['Zahlentermin'] = {{on: false, set: on => {{ if (on && !earnS) {{ earnS = chart.addHistogramSeries({{priceScaleId: 'ev', color: 'rgba(192,50,43,.25)', priceLineVisible: false, lastValueVisible: false, autoscaleInfoProvider: () => ({{priceRange: {{minValue: 0, maxValue: 1}}}})}});
  chart.priceScale('ev').applyOptions({{scaleMargins: {{top: 0, bottom: 0}}, visible: false}}); earnS.setData([{{time: P.earn, value: 1}}]); }} else if (!on && earnS) {{ chart.removeSeries(earnS); earnS = null; }} }}}};
function draw() {{
  const v = view(); cs.setData(v); band.setData(v.filter(x => x.time >= P.zstart).map(x => ({{time: x.time, value: P.zone[1]}})));
  Object.keys(P.ma).forEach(k => opt[k].s.setData(P.ma[k].filter(x => x.time >= v[0].time)));
  const lo = Math.min(...v.map(x => x.low), P.stop, P.zone[0]), hi = Math.max(...v.map(x => x.high), P.target || 0, P.zone[1]);
  const pad = (hi - lo) * .04; cs.applyOptions({{autoscaleInfoProvider: () => ({{priceRange: {{minValue: lo - pad, maxValue: hi + pad}}}})}});
  {{ const _n = chart.timeScale().getVisibleLogicalRange() ? Math.round(chart.timeScale().getVisibleLogicalRange().to) + 1 : 0; chart.timeScale().fitContent(); const _r = chart.timeScale().getVisibleLogicalRange(); if (_r) {{ const _x = {{from: -0.5, to: _r.to + Math.max(12, Math.round((_r.to - _r.from) * .1))}}; chart.timeScale().setVisibleLogicalRange(_x); requestAnimationFrame(() => chart.timeScale().setVisibleLogicalRange(_x)); }} }} legend();
  document.querySelectorAll('#rg button').forEach(b => b.classList.toggle('on', b.textContent === rng));
}}
const PL = [['Einstiegszone', P.zone[0], P.zone[1]], ['Stopp', P.stop, P.stop]].concat(P.target ? [['Ziel', P.target, P.target]] : []);
const avg = (P.zone[0] + P.zone[1]) / 2;
function near(y) {{ if (y == null) return ''; const pr = cs.coordinateToPrice(y); if (pr == null) return '';
  for (const [n, a, b] of PL) {{ if (pr >= a * 0.99 && pr <= b * 1.01) {{ const v = n === 'Einstiegszone' ? `${{de(a)}} – ${{de(b)}}` : de(a);
    const d = n === 'Einstiegszone' ? '' : ` (${{a >= avg ? '+' : '−'}}${{de(Math.abs(a / avg - 1) * 100, 1)}} % vom Ø Einstieg)`; return ` &nbsp;·&nbsp; <b style="color:${{n === 'Stopp' ? '#c0322b' : n === 'Ziel' ? '#337ab7' : '#1e7b45'}}">${{n}} ${{v}}</b>${{d}}`; }} }} return ''; }}
let NY = null;
function legend(c) {{
  const v = view(), f = v[0], l = c || v[v.length-1], ch = l.close / f.close - 1;
  document.getElementById('lg').innerHTML = `<b>${{dd(l.time)}}</b> &nbsp; Schluss <b>${{de(l.close)}} {cur}</b>` + (c ? ` &nbsp; Hoch ${{de(c.high)}} · Tief ${{de(c.low)}}` + near(NY) :
     ` &nbsp; <span style="color:${{ch >= 0 ? '#1e7b45' : '#c0322b'}};font-weight:600">${{ch >= 0 ? '+' : '−'}}${{de(Math.abs(ch) * 100, 1)}} %</span> im Zeitraum`);
}}
const mk = (id, lab, on, cls) => {{ const b = document.createElement('button'); b.textContent = lab; if (cls) b.className = cls; b.onclick = on; document.getElementById(id).appendChild(b); return b; }};
Object.keys(R).forEach(k => mk('rg', k, () => {{ rng = k; draw(); }}));
Object.keys(opt).forEach(k => {{ const b = mk('chips', k, () => {{ const o = opt[k]; o.on = !o.on; b.classList.toggle('on', o.on); if (o.s) o.s.applyOptions({{visible: o.on}}); else o.set(o.on); }}, 'chip'); }});
chart.subscribeCrosshairMove(p => {{ NY = p && p.point ? p.point.y : null; if (!p || !p.time) return legend(); const d = p.seriesData.get(cs); if (d) legend(Object.assign({{time: typeof p.time === 'object' ? `${{p.time.year}}-${{String(p.time.month).padStart(2,'0')}}-${{String(p.time.day).padStart(2,'0')}}` : String(p.time)}}, d)); }});
draw();
const FE = window.frameElement, H0 = {height}; let full = false, saved = '';
function setFull(on) {{ full = on; document.body.classList.toggle('full', on);
  if (FE) {{ if (on) {{ saved = FE.getAttribute('style') || ''; FE.style.cssText = saved + ';position:fixed;inset:0;width:100vw;height:100vh;z-index:999999;background:#fff'; window.parent.document.body.style.overflow = 'hidden'; }}
             else {{ FE.setAttribute('style', saved); window.parent.document.body.style.overflow = ''; }} }}
  document.getElementById('c').style.height = (on ? window.parent.innerHeight - 110 : H0) + 'px'; document.getElementById('fs').textContent = on ? 'Vollbild schließen' : 'Vollbild'; }}
document.getElementById('fs').onclick = () => setFull(!full);
const esc = e => {{ if (e.key === 'Escape' && full) setFull(false); }};
document.addEventListener('keydown', esc); try {{ window.parent.document.addEventListener('keydown', esc); }} catch (e) {{}}
</script></body></html>"""
    components.html(html, height=height + 92)
