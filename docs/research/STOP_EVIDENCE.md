# Stop-/KO-Evidenz für Swing-Tool und Investment-Bereich (Stand 22.10.2026)

Live-Code ist unverändert. Skripte: `backtest/studies/stop_setups.py`, `backtest/studies/stop_eval.py`, `backtest/studies/stop_tables.py`, `backtest/studies/invest_eval.py`. Daten: `backtest/studies/*.parquet`, `backtest/studies/stop_params.json`.

## Aufbau
- **Universum:** Point-in-time-Mitglieder von S&P 500/400, NDX und DAX (`universe/intervals.parquet`), einschließlich der in `prices_hist` gelisteten ausgeschiedenen Werte.
- **Kurse:** Die Kursdaten beginnen 2015. Weil 252 Handelstage Vorlauf nötig sind, gibt es Setups erst ab 2016.
- **Perioden:** Test 2016–19 (24.108 Setups), Validierung 2020–21 (12.966 Setups). Kursverläufe werden nur bis 31.12.2022 benutzt; 2023+ ist versiegelt und wurde nicht angefasst.
- **Setups:** monatlich am letzten Handelstag, mit der unveränderten Live-Funktion `swing_levels._analyse` auf dem bis zum Stichtag gekürzten Kursverlauf. Daraus kommen Einstiegszone, Einstieg, Stopp, Ziel 1 und KO.
- **Ausführung:**
  - Liegt der Kurs in der Zone, wird zum Schlusskurs gekauft, sonst per Limit an der Oberkante. Das Limit gilt 21 Handelstage; öffnet der Kurs darunter, wird zum Eröffnungskurs gekauft.
  - Ausstieg bei Stopp (bei einer Kurslücke zum Eröffnungskurs) oder bei Ziel 1. Berühren beide am selben Tag, zählt der Stopp.
  - Spätestens nach 126 Handelstagen wird zum Schlusskurs verkauft.
- **Turbo:**
  - KO = Stopp − 1 ATR, Hebel L = Einstieg / (Einstieg − KO).
  - Finanzierung 5 % p. a. auf den Basispreis; als Kostenanteil am Turbowert ergibt das 5 % × (L − 1) × Tage / 365.
  - Ausstieg am Stopp des Basiswerts. Springt der Kurs per Lücke unter den KO, ist der Turbo wertlos (−100 %).
- **Regelfamilien:** vorab festgelegt, keine Suche über Parameter.

| Regel | Stopp |
|---|---|
| R0 live | min(Zone, Wendetief) − 1 ATR; liegt er in einer tieferen Zone, wandert er unter deren Unterkante − 0,5 ATR |
| K1 / K1.5 / K2 / K3 | min(Zone, Wendetief) − k·ATR |
| Q80 / Q90 | Einstieg − p80/p90 der MAE (vor Ziel 1, in ATR) der erfolgreichen **Test**-Setups je Zelle (Volatilitätsterzil × SMA200) |
| S struktur | Unterkante der nächsten tieferen Unterstützung − 0,5 ATR (ohne tiefere Zone: k = 2) |

- **Gruppen:**
  - ATR%-Terzile mit Grenzen aus dem Test: ruhig, mittel, volatil.
  - Beta-Terzile (252 Tage gegen SPY).
  - Lage zur SMA200 (über/unter und Abstand).
  - Trend: Aufwärts = SMA50 > SMA200 und SMA200 steigend; Abwärts = beides umgekehrt; sonst Übergang.
  - Zonenstärke: 50-Tage-Linie, 2 Berührungen oder 3+ Berührungen.

## 1. Aktuelle Regel R0: Trefferquoten
Spalten: stop = Stopp erreicht; ko = KO vor Ziel 1 berührt; ziel = Ziel 1 erreicht; E[R] = mittleres R, winsorisiert auf −3 bis 5; E% = mittlere Rendite des Basiswerts je Trade; Turbo = Turbo-Rendite je Trade; L = Median-Hebel.

| Periode | n | Stopp | KO | Ziel 1 | E[R] | E% | KO-Lücke (Turbo −100 %) | L | Turbo | Tage |
|---|---|---|---|---|---|---|---|---|---|---|
| Test | 24.108 | 39,6 % | 29,9 % | 60,3 % | 0,144 | 0,7 % | 1,1 % | 15,6 | 8,9 % | 8,9 |
| Validierung | 12.966 | 34,0 % | 25,4 % | 65,8 % | 0,247 | 2,0 % | 0,9 % | 11,5 | 15,6 % | 9,2 |

**R0 je Gruppe (Test).** E[R] ist hier unwinsorisiert.

| Gruppe | n | Stopp | KO | Ziel 1 | E[R] | Risiko % | L |
|---|---|---|---|---|---|---|---|
| ruhig | 8.036 | 41,3 % | 31,4 % | 58,7 % | 0,18 | 3,0 % | 22,3 |
| mittel | 8.036 | 38,9 % | 29,3 % | 61,1 % | 0,16 | 4,4 % | 15,6 |
| volatil | 8.036 | 38,7 % | 28,8 % | 61,2 % | 0,14 | 6,4 % | 10,6 |
| Beta niedrig | 8.036 | 39,0 % | 29,5 % | 61,0 % | 0,20 | 3,8 % | 17,8 |
| Beta mittel | 8.036 | 38,7 % | 29,6 % | 61,2 % | 0,16 | 4,3 % | 15,7 |
| Beta hoch | 8.036 | 41,2 % | 30,5 % | 58,8 % | 0,11 | 5,0 % | 13,5 |
| unter SMA200 | 8.196 | 38,2 % | 28,7 % | 61,8 % | 0,18 | 5,0 % | 13,3 |
| über SMA200 0–10 % | 9.717 | 37,6 % | 28,3 % | 62,3 % | 0,16 | 4,0 % | 16,9 |
| über SMA200 10–25 % | 5.568 | 44,5 % | 33,6 % | 55,5 % | 0,14 | 3,8 % | 17,3 |
| über SMA200 >25 % | 627 | 46,6 % | 34,9 % | 53,1 % | 0,15 | 5,2 % | 12,3 |
| Trend Aufwärts | 13.648 | 39,9 % | 30,1 % | 60,1 % | 0,17 | 3,9 % | 17,0 |
| Trend Übergang | 4.327 | 35,9 % | 26,3 % | 64,1 % | 0,16 | 4,6 % | 14,7 |
| Trend Abwärts | 6.133 | 41,6 % | 31,8 % | 58,4 % | 0,14 | 4,9 % | 13,6 |
| 50-Tage-Linie | 326 | 50,0 % | 40,2 % | 50,0 % | 0,29 | 2,5 % | 23,6 |
| Zone 2 Berührungen | 7.820 | 43,0 % | 32,2 % | 57,0 % | 0,16 | 3,7 % | 17,3 |
| Zone 3+ Berührungen | 15.962 | 37,7 % | 28,5 % | 62,2 % | 0,16 | 4,6 % | 14,8 |

**Zelle Volatilität × SMA200**

| Zelle | Stopp Test | Stopp Val | E[R] Test | E[R] Val (winsorisiert) |
|---|---|---|---|---|
| ruhig / über SMA200 | 41,8 % | 46,9 % | 0,15 | 0,06 |
| ruhig / unter SMA200 | 38,8 % | 35,3 % | 0,13 | 0,17 |
| mittel / über SMA200 | 39,7 % | 40,2 % | 0,14 | 0,14 |
| mittel / unter SMA200 | 37,3 % | 32,1 % | 0,15 | 0,23 |
| **volatil / über SMA200** | **39,0 %** | **32,2 %** | 0,14 | 0,28 |
| volatil / unter SMA200 | 38,5 % | 28,3 % | 0,15 | 0,35 |

## 2. MAE (Test, in ATR ab Einstieg)
"Vor Ziel 1" betrachtet nur Setups, die Ziel 1 innerhalb von 6 Monaten erreicht haben. Die 1-, 3- und 6-Monats-MAE gilt für alle Setups.

| Zelle | Ziel 1 erreicht | MAE p50 | p80 | p90 | p80 in % | MAE 1M p80 | 3M p80 | 6M p80 | Live-Stopp (ATR ab Einstieg) |
|---|---|---|---|---|---|---|---|---|---|
| ruhig / über | 90,1 % | 1,17 | 3,44 | 5,37 | 5,1 % | 4,4 | 8,1 | 12,2 | 1,99 |
| ruhig / unter | 90,3 % | 1,05 | 3,43 | 5,37 | 5,4 % | 4,6 | 8,3 | 12,2 | 2,13 |
| mittel / über | 89,0 % | 1,12 | 3,22 | 4,94 | 6,7 % | 4,0 | 6,4 | 9,9 | 2,09 |
| mittel / unter | 90,0 % | 1,09 | 2,92 | 4,76 | 6,2 % | 3,9 | 6,7 | 10,1 | 2,09 |
| volatil / über | 86,2 % | 1,05 | 2,79 | 4,36 | 8,7 % | 3,5 | 5,6 | 8,6 | 2,12 |
| volatil / unter | 88,5 % | 1,00 | 2,96 | 4,67 | 10,0 % | 3,7 | 5,8 | 8,2 | 2,04 |

Lesart:
- Etwa 89 % aller Setups erreichen Ziel 1 irgendwann innerhalb von 6 Monaten, ein Teil davon erst nach einem Stopp-Durchlauf.
- Der Live-Stopp liegt bei etwa 2 ATR. Das ist knapp unter dem MAE-Median der erfolgreichen Setups (etwa 1,1 ATR) und deutlich unter deren p80 (etwa 3 ATR).
- Volatile Aktien schwanken, in ATR gemessen, **weniger** gegen den Einstieg als ruhige, nicht mehr.

## 3. Regelvergleich (fest aus dem Test, geprüft auf der Validierung)
E[R] ist auf −3 bis 5 winsorisiert; Turbo/Tag = mittlere Turbo-Rendite je Trade geteilt durch die mittlere Haltedauer.

| Regel | Stopp Test | Stopp Val | KO Val | Gewinnquote Val | E[R] Test | **E[R] Val** | E% Val | L Val | Turbo/Trade Val | Turbo/Tag Val |
|---|---|---|---|---|---|---|---|---|---|---|
| K1 | 46,1 % | 39,3 % | 28,6 % | 60,6 % | 0,156 | **0,301** | 1,8 % | 13,8 | 17,5 % | 2,3 % |
| K1.5 | 38,8 % | 33,0 % | 25,2 % | 66,8 % | 0,150 | 0,257 | 2,1 % | 11,6 | 16,4 % | 1,7 % |
| **R0 live** | 39,6 % | 34,0 % | 25,4 % | 65,8 % | 0,144 | 0,247 | 2,0 % | 11,5 | 15,6 % | 1,7 % |
| S struktur | 34,0 % | 28,8 % | 22,2 % | 70,8 % | 0,138 | 0,226 | 2,3 % | 10,0 | 15,1 % | 1,3 % |
| K2 | 33,8 % | 28,7 % | 22,4 % | 71,0 % | 0,135 | 0,219 | 2,2 % | 10,0 | 14,9 % | 1,4 % |
| Q80 | 28,8 % | 25,6 % | 20,3 % | 74,0 % | 0,129 | 0,198 | 2,3 % | 9,2 | 13,7 % | 1,1 % |
| K3 | 26,2 % | 22,4 % | 18,4 % | 77,0 % | 0,123 | 0,174 | 2,5 % | 7,8 | 12,6 % | 0,9 % |
| Q90 | 19,4 % | 17,7 % | 14,8 % | 81,3 % | 0,110 | 0,145 | 2,6 % | 6,5 | 10,9 % | 0,6 % |

Die Reihenfolge ist in allen Jahren von 2016 bis 2021 gleich: engere Stopps haben das höhere E[R] und die höhere Turbo-Rendite pro Tag. 2018 war für alle Regeln das schwächste Jahr (E[R] 0,01 bis 0,11).

**Zelle volatil / über SMA200, Validierung (E[R] unwinsorisiert)**

| Regel | Stopp | E[R] |
|---|---|---|
| K1 | 38,0 % | 0,35 |
| R0 | 32,2 % | 0,28 |
| S | 27,0 % | 0,27 |
| K2 | 27,0 % | 0,26 |
| Q80 | 25,2 % | 0,24 |
| K3 | 20,3 % | 0,21 |
| Q90 | 16,4 % | 0,19 |

## 4. Befund Swing
1. **Die These "zu eng, besonders bei volatilen Aktien über der SMA200" bestätigt sich nicht.**
   - In dieser Zelle trifft der Live-Stopp in 39 % (Test) bzw. 32 % (Validierung) der Fälle, also nicht häufiger als im Rest.
   - Gemessen in ATR schwanken volatile Aktien weniger gegen den Einstieg als ruhige.
   - Am häufigsten ausgestoppt wird **ruhig / über SMA200**: 42 % bzw. 47 %, in der Validierung mit dem schwächsten E[R] (0,06).
2. **Weitere Stopps erhöhen die Trefferquote, senken aber den Ertrag je eingesetztem Risiko.**
   - Von K1 bis Q90 steigt die Gewinnquote von 61 auf 81 %, das E[R] fällt aber von 0,30 auf 0,15.
   - Das gilt in Test und Validierung, in allen Zellen und in jedem Jahr.
   - Die Rendite je Trade auf den Basiswert (E%) steigt leicht (von 1,8 auf 2,6 %), weil mehr Kapital länger gebunden ist.
3. **Turbo:**
   - Ein weiterer KO bedeutet weniger Hebel (R0: L ≈ 11,5; K3: 7,8; Q90: 6,5) und längere Haltedauer, also mehr Finanzierungskosten.
   - Die Turbo-Rendite je Trade sinkt von 17,5 % (K1) auf 10,9 % (Q90), pro Tag von 2,3 % auf 0,6 %.
   - Der KO-Puffer von 1 ATR unter dem Stopp reicht: Ein Totalverlust durch eine Kurslücke unter den KO kommt bei 0,9–1,1 % der Trades vor.
4. **Schwache Gruppen:** Zonen mit nur 2 Berührungen (43 % Stopp gegenüber 38 % bei 3+) und Einstiege mehr als 10 % über der SMA200 (45–47 % Stopp, nur 53–56 % Ziel).

## 5. Vorschlag Swing (noch nicht umgesetzt)
- **Stoppregel R0 beibehalten, nicht verbreitern.**
  - Keine der weiteren Regelfamilien (K2, K3, Q80, Q90, S) schlägt R0 bei E[R] oder bei der Turbo-Rendite pro Tag, weder im Test noch in der Validierung.
  - K1 (Zone − 1 ATR ohne strukturelles Verschieben) ist etwas besser (Validierung 0,30 gegenüber 0,25 R), aber nur mit 39 % Stopp-Quote. Das ist keine klare Verbesserung, nur ein Grenzfall, den LM entscheiden sollte.
- **KO = Stopp − 1 ATR beibehalten.**
- **Jede Stopp-Distanz mit Evidenz anzeigen:** Für die Zelle des Setups (Volatilität × SMA200) aus dem Test die Wahrscheinlichkeiten für Stopp, Ziel 1 und KO, dazu E[R]. Die Validierung zeigt, wie gut das trägt: Abweichungen bis etwa 10 Prozentpunkte, in der Hausse 2020–21 meist günstiger.
- **Wahlweise eine "weite Variante"** mit K2 (Stopp-Quote 29 %, Gewinnquote 71 %, E[R] 0,22, Hebel ~10) für LM, wenn ihm Trefferquote wichtiger ist als Ertrag je Risiko. Mit dem Hinweis, dass dabei rund 11 % weniger Ertrag je Risiko zu erwarten sind.
- **Optionale Filter**, beide nur aus dem Test abgeleitet, Validierung noch offen: Warnhinweis bei Einstieg mehr als 10 % über der SMA200 und bei Zonen mit nur 2 Berührungen.

## 6. Investment-Bereich (Regeln aus invest_plan, nur verlässliche Bewertungen)
**Grundlage und Annahmen:**
- Point-in-time-Backtest-Panel v5.1 (`valuation_v4_backtest.parquet`, vierteljährlich).
- Das Panel enthält nur das Verhältnis Fair Value zu Kurs (`fv4`). Den pessimistischen Wert und die Kaufzone habe ich deshalb über archetypische Median-Verhältnisse aus dem v5.1-Export angenähert, z. B. mature pess/base 0,875, Kaufzone 0,8. Das ist eine Strukturannahme.
- Unterstützungen, Tranchen-Snapping und Stopp kommen aus der Live-Funktion `invest_plan.plan` mit den Kursen bis zum Stichtag.
- Erste Tranche T1 gilt als gekauft, sobald der Kurs T1 erreicht. Gemessen werden die tiefsten Kurse innerhalb von 1 bzw. 2 Jahren danach.

**T1-Füllquote:** 1 Jahr 59,5 % (Test) / 57,6 % (Validierung); 2 Jahre 63,7 % / 60,0 %. In 51 % (Test) bzw. 62 % (Validierung) der Fälle bleibt nur eine Tranche, weil die übrigen weniger als 5 % unter T1 lagen.

| Horizont / Periode | n | T2 erreicht | T3 erreicht | Stopp erreicht | Max. Drawdown p50 | p80 | p90 | Stopp-Abstand (Median) | Rendite am Ende nach Stopp (Median) |
|---|---|---|---|---|---|---|---|---|---|
| 1 Jahr Test | 3.307 | 20,7 % | 0,7 % | **50,3 %** | 14,6 % | 33,9 % | 46,0 % | 8,0 % | −2,7 % |
| 1 Jahr Val | 1.813 | 12,3 % | 0,6 % | **40,7 %** | 9,6 % | 20,4 % | 29,9 % | 8,0 % | −0,4 % |
| 2 Jahre Test | 3.539 | 25,7 % | 0,8 % | **58,4 %** | 20,7 % | 41,7 % | 53,3 % | 13,4 % | +14,9 % |
| 2 Jahre Val | 931 | 10,0 % | 0,3 % | 38,6 % | 8,8 % | 16,6 % | 23,0 % | 8,0 % | +23,1 % |

**Nach Archetyp (1 Jahr, Test)**

| Archetyp | n | T2 | T3 | Stopp | Max. DD p50 | p80 |
|---|---|---|---|---|---|---|
| mature | 1.561 | 23 % | 0 % | 50 % | 15 % | 35 % |
| scaler | 396 | 21 % | 3 % | 61 % | 20 % | 41 % |
| quality | 338 | 18 % | 0 % | 49 % | 15 % | 31 % |
| utility | 340 | 12 % | 0 % | 49 % | 9 % | 25 % |
| cyclical | 285 | 28 % | 0 % | 51 % | 24 % | 47 % |
| reit | 187 | 8 % | 0 % | 63 % | 13 % | 26 % |
| hyper | 101 | 27 % | 10 % | 24 % | 14 % | 30 % |
| bank | 33 | 18 % | 0 % | 27 % | 6 % | 33 % |
| defence | 28 | 43 % | 0 % | 29 % | 18 % | 31 % |

Nach Volatilität (1 Jahr, Test) liegt der maximale Drawdown p80 bei 31,7 % (ruhig), 34,2 % (mittel) und 37,4 % (volatil).

**Befund Investment:**
- **Der Stopp (8 % unter min(pessimistischer Wert, letzte Tranche)) ist zu eng.** Er wird in 40–58 % der Fälle erreicht. Die ausgestoppten Positionen standen am Horizontende im Median etwa bei null (1 Jahr) oder im Plus (2 Jahre: +15 % bzw. +23 %). Der Stopp schließt also überwiegend Positionen, deren These gar nicht gebrochen war.
- **T3 wird praktisch nie erreicht (unter 1 %),** T2 in 10–26 % der Fälle.

**Vorschlag Investment (noch nicht umgesetzt):**
- **Stopp** = min(pessimistischer Wert, letzte Tranche) × (1 − max(8 %, p80 des maximalen 1-Jahres-Drawdowns der Volatilitätsgruppe aus dem Test)). Das sind 32 % (ruhig), 34 % (mittel) und 37 % (volatil).

| | Stopp-Quote alt → neu | Rendite am Ende, gestoppt | Rendite am Ende, nicht gestoppt |
|---|---|---|---|
| Validierung, 1 Jahr | 40,7 % → 6,2 % | −37,6 % | +15,6 % |
| Validierung, 2 Jahre | 38,6 % → 3,2 % | −35,1 % | +33,8 % |
| Test, 1 Jahr (in-sample, per Konstruktion ~20 %) | 50,3 % → 19,8 % | −16,5 % | +15,3 % |

  Mit der neuen Regel trennt der Stopp in der Validierung echte Thesenbrüche von normaler Schwankung.
- **T3 überdenken:** näher legen oder streichen und die Gewichte auf T1/T2 verteilen. Das ist eine Entscheidung für LM; ein Datensatz für eine genaue Kalibrierung fehlt.

## Einschränkungen
- Kurse erst ab 2015, daher Test nur 2016–19. Survivorship-Bias ist durch die PIT-Mitgliedschaft und `prices_hist` gemindert, aber nicht ausgeschlossen.
- Die Ausführung ist stilisiert: keine Spreads und keine Slippage außer bei Kurslücken. Die Turbo-Finanzierung von 5 % p. a. ist eine Annahme.
- Ziel 1 ist die Live-Logik und meist nah (Haltedauer ~9 Tage). Für Ziel 2 oder Trailing-Stopps wären andere Ergebnisse möglich; das ist nicht untersucht.
- Investment-Teil: pessimistischer Wert und Kaufzone nur angenähert (siehe oben). Die Validierung 2020–21 war eine Hausse.

## 7. Ergänzung v5.2: Ziel 2, Trailing-Stopp, Mindesthaltedauer (23.10.)

Rules fixed in advance (`backtest/studies/exit_study.py`; results in `backtest/studies/exit_results.parquet`, `exit_table.csv`, `exit_table_cells.csv`). Same PIT setups as in sections 1–6, but with target 2 (`stop_setups_t2.py`), horizon 126 trading days. Test 2016–19 (n ≈ 24.100 per rule), validation 2020–21 (n ≈ 12.970); 2023+ sealed.

- T1 = live (target 1) · T2 = second resistance (if none: end of horizon) · TRP = after target 1, stop to entry, then below the last higher 2/2 pivot low · TRA = after target 1, stop to entry, then highest high − 2 ATR · H21/H63/H126 = minimum hold of 1/3/6 months, exit only at the stop or at the close on that day.
- Stops: R0 live, K2 = zone − 2 ATR, Q80 = test quantile per cell. Turbo: KO = initial stop − 1 ATR, financing 5 % p. a. on (L − 1), gap below the KO = −100 %.
- E[R] winsorized (−3…5), before costs. "Per 21 d" = mean ÷ mean holding period × 21 (return per month of tied-up capital).

| Exit | Stop | E[R] test | E[R] val | E[R]/21 d test | E[R]/21 d val | Turbo/21 d test | Turbo/21 d val | Stop rate test | Median days test |
|---|---|---|---|---|---|---|---|---|---|
| T1 | R0 | 0,144 | 0,247 | 0,340 | 0,561 | 0,212 | 0,355 | 0,40 | 6 |
| T1 | K2 | 0,135 | 0,219 | 0,270 | 0,420 | 0,174 | 0,285 | 0,34 | 7 |
| T1 | Q80 | 0,129 | 0,198 | 0,218 | 0,339 | 0,146 | 0,235 | 0,29 | 8 |
| T2 | R0 | 0,189 | 0,286 | 0,197 | 0,279 | 0,157 | 0,193 | 0,54 | 10 |
| T2 | K2 | 0,207 | 0,291 | 0,181 | 0,238 | 0,129 | 0,164 | 0,48 | 13 |
| T2 | Q80 | 0,215 | 0,280 | 0,160 | 0,207 | 0,107 | 0,140 | 0,43 | 16 |
| TRP | R0 | 0,180 | 0,232 | 0,218 | 0,270 | 0,144 | 0,184 | 0,40 | 13 |
| TRP | K2 | 0,186 | 0,223 | 0,197 | 0,228 | 0,123 | 0,153 | 0,34 | 16 |
| TRP | Q80 | 0,179 | 0,207 | 0,168 | 0,196 | 0,105 | 0,131 | 0,29 | 18 |
| TRA | R0 | 0,181 | 0,233 | 0,246 | 0,309 | 0,149 | 0,194 | 0,40 | 11 |
| TRA | K2 | 0,176 | 0,212 | 0,210 | 0,248 | 0,126 | 0,161 | 0,34 | 13 |
| TRA | Q80 | 0,167 | 0,194 | 0,175 | 0,209 | 0,109 | 0,137 | 0,29 | 15 |
| H21 | R0 | 0,199 | 0,168 | 0,281 | 0,228 | 0,177 | 0,140 | 0,45 | 21 |
| H21 | K2 | 0,181 | 0,147 | 0,230 | 0,183 | 0,145 | 0,113 | 0,37 | 21 |
| H21 | Q80 | 0,158 | 0,127 | 0,186 | 0,151 | 0,121 | 0,092 | 0,29 | 21 |
| H63 | R0 | 0,245 | 0,379 | 0,155 | 0,224 | 0,121 | 0,171 | 0,64 | 27 |
| H63 | K2 | 0,286 | 0,407 | 0,158 | 0,212 | 0,103 | 0,145 | 0,57 | 43 |
| H63 | Q80 | 0,284 | 0,399 | 0,139 | 0,193 | 0,087 | 0,130 | 0,50 | 63 |
| H126 | R0 | 0,170 | 0,494 | 0,067 | 0,173 | 0,101 | 0,179 | 0,73 | 27 |
| H126 | K2 | 0,279 | 0,595 | 0,095 | 0,182 | 0,084 | 0,153 | 0,68 | 43 |
| H126 | Q80 | 0,331 | 0,629 | 0,099 | 0,176 | 0,070 | 0,138 | 0,62 | 65 |

**Answer to the question:**
- **Per trade:** from a 3-month holding period onward, the wider stop wins. Test H63: Q80 0,284 / K2 0,286 vs. R0 0,245. Test H126: Q80 0,331 vs. R0 0,170. Validation confirms it (H126: Q80 0,629, K2 0,595, R0 0,494). With T2, R0 and the wider stops are about level (test Q80 0,215 vs. R0 0,189; val roughly equal).
- **Per unit of time:** T1 + R0 stays best in both periods, for the share and for the turbo after financing costs. Test: 0,340 R per 21 days vs. 0,067–0,099 for H126. Validation: 0,561 vs. about 0,18. The short trade frees capital roughly every 9 days. The long hold earns more per trade but not per month.
- **Trailing (TRP/TRA):** better than T1 per trade (test about 0,18 vs. 0,14) but worse per time; not better than T2 either.
- **Result:**
  - The tight stop belongs to the short exit (target 1).
  - Anyone deliberately holding 3–6 months should take the wider stop (Q80 or K2). R0 then gets stopped out too often (test H126 stop rate 0,73 vs. Q80 0,62).
  - A live change is not proposed; the swing rule stays T1 + R0.
- **Limitations:**
  - Validation 2020–21 is a strong bull market and flatters long holds.
  - The "ruhig / über SMA200" cell is weak for long holds in validation (H126 negative for all stops).
  - Overlapping setups are not independent.
