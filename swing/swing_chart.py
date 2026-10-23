"""Swing-Tool: Plan-Chart (Lightweight Charts, gesperrt). Zeiträume 1M/3M/6M/1J auf Tageskerzen, 3J/5J auf Wochenkerzen.
Unterstützungs-/Widerstandszonen aus swing_levels als Bänder, Einstiegszone, Stopp, Ziele als Linien, gleitende Durchschnitte per Schalter."""
import json
import pandas as pd
import streamlit.components.v1 as components
from lib import ROOT, FONT

_JS = (ROOT / "vendor/lightweight-charts.standalone.production.js").read_text()

def _bars(df):
    t = lambda d: d.strftime("%Y-%m-%d")
    return [dict(time=t(r.date), open=round(r.open, 4), high=round(r.high, 4), low=round(r.low, 4), close=round(r.close, 4)) for r in df.itertuples()]

def render(px, an, plan, height=560, cur="USD", key="sc"):
    px = px[px.close > 0].reset_index(drop=True).copy()
    for n in (20, 50, 100, 200): px[f"m{n}"] = px.close.rolling(n).mean()
    t = lambda d: d.strftime("%Y-%m-%d")
    wk = px.set_index("date").resample("W-FRI").agg(dict(open="first", high="max", low="min", close="last", volume="sum", m20="last", m50="last", m100="last", m200="last")).dropna(subset=["close"])
    wk = wk.reset_index(); wk["date"] = [min(d, px.date.iloc[-1]) for d in wk.date]
    def pack(df):
        ma = {str(n): [dict(time=t(d), value=round(v, 4)) for d, v in zip(df.date, df[f"m{n}"]) if v == v] for n in (20, 50, 100, 200)}
        vol = [dict(time=t(r.date), value=float(r.volume), color="rgba(30,158,90,.28)" if r.close >= r.open else "rgba(214,69,65,.28)") for r in df.itertuples()]
        return dict(c=_bars(df), ma=ma, vol=vol)
    zones = [dict(lo=z["lo"], hi=z["hi"], n=z["touches"], role=z["role"], first=z["first"], conf=z["conf"]) for z in an["zones"]]
    P = dict(d=pack(px), w=pack(wk), zones=zones,
             plan=None if not plan else dict(lo=plan["lo"], hi=plan["hi"], stop=plan["stop"], t1=plan["t1"], t2=plan.get("t2"), second=plan.get("second"), entry=plan["entry"], ko=plan.get("ko")),
             piv=[dict(time=d, position="belowBar" if k == "T" else "aboveBar", color="#1e7b45" if k == "T" else "#c0322b", shape="circle", size=0.6) for d, p, k in an["pivots"]])
    html = f"""<!doctype html><html><head><style>
html,body{{margin:0;padding:0;background:#fff;font-family:{FONT};-webkit-user-select:none;user-select:none;overflow:hidden}}
.bar{{display:flex;justify-content:space-between;align-items:center;gap:10px;margin:0 0 8px;flex-wrap:nowrap}}
.g{{display:flex;gap:2px;background:#f4f8fb;border:1px solid #e3e8ef;border-radius:6px;padding:2px}}
.g button,.chip{{font:600 12.5px {FONT};color:#344054;background:transparent;border:0;border-radius:4px;padding:5px 10px;cursor:pointer;white-space:nowrap}}
.g button.on{{background:#fff;color:#337ab7;box-shadow:0 1px 2px rgba(16,24,40,.12)}}
.chip{{border:1px solid #d0d7e2;border-radius:14px;padding:4px 11px;color:#5d6b7e;background:#fff;display:inline-flex;align-items:center;gap:6px}} .chip.on{{border-color:#337ab7;color:#1d2939;background:#eef4fa}}
.chip i{{display:inline-block;width:12px;height:3px;border-radius:2px}}
#lg{{font-size:13px;color:#5d6b7e;font-variant-numeric:tabular-nums;white-space:nowrap}} #lg b{{color:#1d2939;font-weight:600}}
#fs{{font:600 12.5px {FONT};color:#337ab7;background:#fff;border:1px solid #c9dbee;border-radius:6px;padding:5px 11px;cursor:pointer}}
body.full{{padding:14px 18px}}
</style></head><body>
<div class="bar"><div id="lg"></div><div style="display:flex;gap:8px;align-items:center"><div class="g" id="rg"></div><button id="fs">Vollbild</button></div></div>
<div class="bar" style="justify-content:flex-start;gap:6px" id="chips"></div>
<div id="c" style="height:{height}px"></div>
<script>{_JS}</script>
<script>
const P = {json.dumps(P)};
const ts_ = t => typeof t === 'object' ? `${{t.year}}-${{String(t.month).padStart(2,'0')}}-${{String(t.day).padStart(2,'0')}}` : String(t);
const de = (x, d=2) => x.toLocaleString('de-DE', {{minimumFractionDigits: d, maximumFractionDigits: d}});
const dd = s => s.split('-').reverse().join('.');
const chart = LightweightCharts.createChart(document.getElementById('c'), {{
  autoSize: true, handleScroll: false, handleScale: false, kineticScroll: {{touch: false, mouse: false}},
  layout: {{background: {{color: '#ffffff'}}, textColor: '#5d6b7e', fontSize: 12, fontFamily: {json.dumps(FONT)}, attributionLogo: false}},
  localization: {{locale: 'de-DE', priceFormatter: p => de(p), timeFormatter: t => (typeof t === 'object' ? [String(t.day).padStart(2,'0'), String(t.month).padStart(2,'0'), t.year] : String(t).split('-').reverse()).join('.')}},
  grid: {{vertLines: {{visible: false}}, horzLines: {{color: '#f2f4f7'}}}},
  rightPriceScale: {{borderVisible: false, minimumWidth: 86, autoScale: true, scaleMargins: {{top: .06, bottom: .16}}}},
  timeScale: {{borderColor: '#e3e8ef', fixLeftEdge: false, fixRightEdge: false, lockVisibleTimeRangeOnResize: false, rightOffset: 0, shiftVisibleRangeOnNewBar: false,
    tickMarkFormatter: (t, ty) => {{ const M = ['Jan','Feb','März','Apr','Mai','Juni','Juli','Aug','Sep','Okt','Nov','Dez']; const a = ts_(t).split('-');
      return ty === 0 ? a[0] : ty === 1 ? M[+a[1] - 1] : (a[2] + '.' + a[1] + '.'); }} }},
  crosshair: {{mode: 1, vertLine: {{color: '#98a2b3', labelBackgroundColor: '#344054'}}, horzLine: {{color: '#98a2b3', labelBackgroundColor: '#344054'}}}} }});
const none = () => null;
const R = {{'1M': [31, 'd'], '3M': [92, 'd'], '6M': [183, 'd'], '1J': [365, 'd'], '3J': [1096, 'w'], '5J': [1827, 'w'], 'D1 Detail': [365, 'd']}};
const DET = () => rng === 'D1 Detail';
let rng = '6M';
const cut = (arr, s) => arr.filter(x => x.time >= s);
const start = () => {{ const L = P.d.c[P.d.c.length-1].time; const e = new Date(L); e.setDate(e.getDate() - R[rng][0]); return e.toISOString().slice(0,10); }};
const view = () => cut(src().c, start());
const src = () => R[rng][1] === 'd' ? P.d : P.w;
const vol = chart.addHistogramSeries({{priceScaleId: 'vol', priceFormat: {{type: 'volume'}}, priceLineVisible: false, lastValueVisible: false}});
chart.priceScale('vol').applyOptions({{scaleMargins: {{top: .88, bottom: 0}}, visible: false}});
const bandS = [];
const mkBand = (lo, hi, fill, line) => {{ const s = chart.addBaselineSeries({{ baseValue: {{type: 'price', price: lo}}, topFillColor1: fill, topFillColor2: fill, topLineColor: line, lineWidth: 1,
  bottomFillColor1: 'rgba(0,0,0,0)', bottomFillColor2: 'rgba(0,0,0,0)', bottomLineColor: 'rgba(0,0,0,0)', priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, autoscaleInfoProvider: none }}); bandS.push(s); return s; }};
const cs = chart.addCandlestickSeries({{ upColor: '#1e9e5a', downColor: '#d64541', borderVisible: false, wickUpColor: '#1e9e5a', wickDownColor: '#d64541', priceLineVisible: false, lastValueVisible: true }});
const MA = {{'20': ['20-Tage', '#12b76a', false], '50': ['50-Tage', '#f79009', true], '100': ['100-Tage', '#2e90fa', false], '200': ['200-Tage', '#7a5af8', true]}};
const maS = {{}};
Object.keys(MA).forEach(k => {{ maS[k] = chart.addLineSeries({{color: MA[k][1], lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, visible: MA[k][2], autoscaleInfoProvider: none}}); }});
let showZ = true, showP = false, lines = []; const maOn = {{}}; Object.keys(MA).forEach(k => maOn[k] = MA[k][2]);
function draw() {{
  const s = start(), S = src(), v = cut(S.c, s);
  cs.setData(v); vol.setData(cut(S.vol, s));
  Object.keys(MA).forEach(k => maS[k].setData(cut(S.ma[k], s)));
  Object.keys(MA).forEach(k => maS[k].applyOptions({{visible: DET() ? k !== '100' : maOn[k]}}));
  cs.setMarkers((showP || DET()) && R[rng][1] === 'd' ? P.piv.filter(m => m.time >= s) : []);
  bandS.forEach(b => chart.removeSeries(b)); bandS.length = 0; lines.forEach(l => cs.removePriceLine(l)); lines = [];
  let lo = Math.min(...v.map(x => x.low)), hi = Math.max(...v.map(x => x.high));
  const pl = P.plan;
  const h0 = hi;
  if (pl) {{ lo = Math.min(lo, pl.stop, pl.ko || pl.stop); hi = Math.max(hi, pl.t1 <= h0 * 1.15 ? pl.t1 : hi, pl.t2 && pl.t2 <= h0 * 1.15 ? pl.t2 : hi, pl.hi); }}
  const span = hi - lo, last = v[v.length-1].close;
  const ts = v.map(x => x.time);
  const band = (a, b, fill, line, from) => mkBand(a, b, fill, line).setData(ts.filter(t => t >= (from && from > ts[0] ? from : ts[0])).map(t => ({{time: t, value: b}})));
  if (showZ) {{
    P.zones.filter(z => z.hi >= lo && z.lo <= hi && !(pl && z.lo <= pl.hi && z.hi >= pl.lo))
      .sort((a, b) => Math.abs((a.lo + a.hi) / 2 - last) - Math.abs((b.lo + b.hi) / 2 - last)).slice(0, 6).forEach(z => {{
        const sup = z.hi < last; band(z.lo, z.hi, sup ? 'rgba(52,64,84,.07)' : 'rgba(192,50,43,.07)', sup ? 'rgba(52,64,84,.25)' : 'rgba(192,50,43,.3)', R[rng][1] === 'd' ? z.first : null);
      }});
  }}
  if (pl) {{
    band(pl.lo, pl.hi, 'rgba(30,123,69,.16)', 'rgba(30,123,69,.6)', null);
    const L = (p, c, t, w, st) => lines.push(cs.createPriceLine({{price: p, color: c, lineWidth: w, lineStyle: st, axisLabelVisible: true, title: t}}));
    L(pl.entry, '#1e7b45', 'Einstieg', 1, 2); L(pl.stop, '#c0322b', 'Stopp', 2, 0);
    if (pl.t1 <= hi * 1.001) L(pl.t1, '#337ab7', 'Ziel 1', 2, 0);
    if (pl.t2 && pl.t2 <= hi) L(pl.t2, '#1849a9', 'Ziel 2', 1, 2);
    if (pl.ko) L(pl.ko, '#7a271a', 'Knock-out', 1, 1);
    if (pl.second && pl.second >= lo) L(pl.second, '#1e7b45', 'Tranche 2', 1, 3);
  }}
  // feste Spannen je Zeitraum: y aus sichtbaren Kerzen, Zonen, Stopp, KO, Zielen + 6 % Rand; x = alle Kerzen + 10 % Freiraum rechts
  const zs = showZ ? P.zones.filter(z => z.hi >= lo && z.lo <= hi) : [];
  zs.forEach(z => {{ lo = Math.min(lo, z.lo); hi = Math.max(hi, z.hi); }});
  const pad = (hi - lo) * .06, yr = {{minValue: Math.max(0, lo - pad), maxValue: hi + pad}};
  cs.applyOptions({{autoscaleInfoProvider: () => ({{priceRange: yr}})}});
  const xr = {{from: -0.5, to: v.length - 0.5 + Math.max(6, Math.round(v.length * .1))}};
  const fix = () => {{ chart.timeScale().setVisibleLogicalRange(xr); chart.priceScale('right').applyOptions({{autoScale: true}}); }};
  chart.timeScale().applyOptions({{fixRightEdge: false}}); fix(); chart.timeScale().applyOptions({{fixRightEdge: true}}); requestAnimationFrame(() => {{ fix(); requestAnimationFrame(fix); }});
  document.body.dataset.view = JSON.stringify([rng, v.length, +yr.minValue.toFixed(4), +yr.maxValue.toFixed(4), xr.to]);
  legend(); document.querySelectorAll('#rg button').forEach(b => b.classList.toggle('on', b.textContent === rng));
}}
function legend(c) {{
  const v = cut(src().c, start()), f = v[0], l = c || v[v.length-1], ch = l.close / f.close - 1;
  document.getElementById('lg').innerHTML = `<b>${{dd(l.time)}}</b>${{R[rng][1] === 'w' && !c ? ' (Woche)' : ''}} &nbsp; Schluss <b>${{de(l.close)}} {cur}</b>` + (c ? ` &nbsp; Eröffnung ${{de(c.open)}} · Hoch ${{de(c.high)}} · Tief ${{de(c.low)}}` :
     ` &nbsp; <span style="color:${{ch >= 0 ? '#1e7b45' : '#c0322b'}};font-weight:600">${{ch >= 0 ? '+' : '−'}}${{de(Math.abs(ch) * 100, 1)}} %</span> im Zeitraum · ${{DET() ? 'Tageskerzen, 12 Monate, 20/50/200-Tage-Linie, Wendepunkte' : R[rng][1] === 'd' ? 'Tageskerzen' : 'Wochenkerzen'}}`);
}}
const mk = (id, html, on, cls) => {{ const b = document.createElement('button'); b.innerHTML = html; if (cls) b.className = cls; b.onclick = on; document.getElementById(id).appendChild(b); return b; }};
const spanD = (new Date(P.d.c[P.d.c.length-1].time) - new Date(P.d.c[0].time)) / 864e5;
let more = false; Object.keys(R).forEach(k => {{ if (R[k][0] > spanD * 1.05) {{ if (more) {{ delete R[k]; return; }} more = true; }} }});
Object.keys(R).forEach(k => mk('rg', k, () => {{ if (rng !== k) {{ rng = k; draw(); }} }}));
chart.timeScale().subscribeVisibleLogicalRangeChange(() => {{}});
let _w = 0; new ResizeObserver(e => {{ const w = Math.round(e[0].contentRect.width); if (w !== _w) {{ _w = w; draw(); }} }}).observe(document.getElementById('c'));
const chip = (lab, col, on, fn) => {{ const b = mk('chips', (col ? `<i style="background:${{col}}"></i>` : '') + lab, () => {{ on = !on; b.classList.toggle('on', on); fn(on); }}, 'chip' + (on ? ' on' : '')); }};
chip('<i style="background:rgba(52,64,84,.3);height:9px;width:9px"></i>Unterstützung <i style="background:rgba(192,50,43,.3);height:9px;width:9px;margin-left:4px"></i>Widerstand', null, true, o => {{ showZ = o; draw(); }});
chip('<i style="background:#1e7b45;height:7px;width:7px;border-radius:50%"></i>Wendepunkte', null, false, o => {{ showP = o; draw(); }});
Object.keys(MA).forEach(k => chip(MA[k][0], MA[k][1], MA[k][2], o => {{ maOn[k] = o; maS[k].applyOptions({{visible: DET() ? k !== '100' : o}}); }}));
chart.subscribeCrosshairMove(p => {{ if (!p || !p.time) return legend(); const d = p.seriesData.get(cs); if (d) legend(Object.assign({{time: ts_(p.time)}}, d)); }});
draw();
const FE = window.frameElement, H0 = {height}; let full = false, saved = '';
function setFull(on) {{ full = on; document.body.classList.toggle('full', on);
  if (FE) {{ if (on) {{ saved = FE.getAttribute('style') || ''; FE.style.cssText = saved + ';position:fixed;inset:0;width:100vw;height:100vh;z-index:999999;background:#fff'; window.parent.document.body.style.overflow = 'hidden'; }}
             else {{ FE.setAttribute('style', saved); window.parent.document.body.style.overflow = ''; }} }}
  document.getElementById('c').style.height = (on ? window.parent.innerHeight - 110 : H0) + 'px'; document.getElementById('fs').textContent = on ? 'Vollbild schließen' : 'Vollbild'; setTimeout(draw, 60); }}
document.getElementById('fs').onclick = () => setFull(!full);
const esc = e => {{ if (e.key === 'Escape' && full) setFull(false); }};
document.addEventListener('keydown', esc); try {{ window.parent.document.addEventListener('keydown', esc); }} catch (e) {{}}
</script></body></html>"""
    components.html(html, height=height + 92)
