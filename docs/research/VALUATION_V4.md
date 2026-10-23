# Bewertung v4 – nach Archetyp

Stand: 21.10.2026. Code: `valuation/archetype.py` (Einordnung), `valuation/engine_v4.py` (Modelle und Leitplanken),
`scripts/export_valuation_v4.py` (Export, `data/valuation_v4.json`, Einordnungsliste `data/archetypes_v4.csv`),
`valuation/backtest_v4.py`, UI: `v4_overlay.py` und `fairvalue.py`.

Feste Regeln. Keine Einstellung je Ticker, kein ML, keine Parametersuche. Die Schwellen sind a priori ökonomisch gesetzt
und nur auf 2012–19 geprüft. 2020–21 dient zur Validierung, 2023+ ist versiegelt.

Ausnahme: Die Zyklikerregel wurde auf 2012–19 gegen eine verworfene Alternative verglichen (siehe unten). Das ist die
einzige Regel, die gegen Daten gewählt wurde, und dafür wurden nur Trainingsdaten verwendet.

## 1. Merkmale (alle zum Bewertungstag, nur bis dahin veröffentlichte Abschlüsse)
| Merkmal | Definition |
|---|---|
| Umsatz | TTM, USD (EDGAR; FX zum Verfügbarkeitsdatum) |
| Investitionen/Umsatz | abs(Capex TTM) ÷ Umsatz |
| Wachstum | Konsens FY+2 ggü. FY+1 (live), sonst 3-Jahres-CAGR (Backtest) |
| Marge, 3J-Marge, Trend | op. Marge TTM, Median der letzten 12 Quartale, Differenz |
| Zyklus | über ≤ 40 Quartale: stärkster Umsatzrückgang J/J, p10 und Median der Marge |
| FCF, FCF-Rendite | OCF − Capex; ÷ Börsenwert (Kurs × Aktien) |
| Verwässerung | Aktienzahl-CAGR über 3 Jahre |
| Aktienvergütung/Umsatz | SBC ÷ Umsatz |
| Bilanztyp | Scanner-Typ nur für Bank/Versicherung, REIT, Versorger |
| Strukturbruch | Umsatz vor 3 Jahren > 3× heute (Verkauf/Abspaltung/Währungswechsel, z. B. NBIS nach Yandex) |

## 2. Regeltabelle (erste zutreffende Regel gilt)
| # | Archetyp | Regel | Ökonomische Begründung | Modell | Wo das Modell versagt |
|---|---|---|---|---|---|
| 1 | Bank/Versicherer | Typ Bank/Finanzen/Versicherung und Investitionen < 15 % vom Umsatz | Bilanz ist das Produkt; Schulden sind Rohstoff, nicht Finanzierung | Übergewinnmodell auf Eigenkapital (Damodaran Kap. 21) | Kreditzyklus nicht modelliert; falsch typisierte Nicht-Banken nur über die Capex-Ausnahme abgefangen |
| 2 | REIT | Typ REIT | Ausschüttungspflicht, Wert aus FFO | AFFO≈FFO-DCF | Erhaltungscapex nicht trennbar → AFFO überschätzt |
| 3 | Versorger | Typ Versorger | regulierte Eigenkapitalrendite | Übergewinnmodell | Regulierungsrisiko, Großprojekte |
| 4 | Frühphase | Umsatz < 50 Mio. USD | Wert ist eine Option auf ein künftiges Geschäft | Szenarien fest gewichtet: Scheitern 40 % (Wert 0), Basis 40 %, optimistisch 20 %; Reverse-DCF als Hauptaussage | Gewichte sind Setzung (nicht optimiert); binäre Ereignisse (Zulassung, Start) nicht modelliert |
| 5 | Kapazitätsaufbau | Investitionen ≥ 40 % vom Umsatz, Wachstum ≥ 20 %, FCF < 0 | Anlagen werden vor dem Umsatz gebaut (Neocloud, Rechenzentren, Satelliten); heutige Marge sagt nichts | DCF mit Konsens Jahr 1–2 ungekappt, Zielmarge und Kapitaleffizienz von reifen kapitalintensiven Firmen (Investitionen ≥ 15 %, profitabel), Finanzierungslücke (kumulierter negativer FCFF über Cash) als neue Aktien zum heutigen Kurs | Wandelanleihen nicht als Eigenkapital erkannt (companyfacts ohne Wandelpreis); Auslastungs- und Preisrisiko der Kapazität nur über die Zielmarge |
| 6 | Hyperwachstum | Wachstum ≥ 25 % | Konsens beschreibt die nächsten zwei Jahre besser als jede Historie | DCF, Konsens Jahr 1–2 ungekappt (nur Datenfehler-Grenzen −50 %/+300 %), Zielmarge = profitable Firmen desselben Sektors (reifer Zustand); bei Zyklusmerkmal pessimistisch die Zyklusmarge | lineares Abklingen des Wachstums über 8 Jahre überschätzt Ausnahmefälle (NVDA 3,4×); Margenumkehr ohne Burggraben drückt Firmen mit hoher Marge (PLTR) |
| 7 | Zykliker | Zyklusbranche (Halbleiter, Rohstoffe, Energie, Speicher, Solar, Hausbau) oder: Umsatz fiel ≥ 10 % J/J und Marge zeitweise ≤ 50 % des Medians (≥ 20 Quartale) | Nachfrage und operativer Hebel schwanken gemeinsam; aktuelle Marge ist Zufall des Zykluszeitpunkts | DCF mit Zyklusmitte-Marge (Median bis 10 Jahre) als Start- und Zielwert | Strukturwandel (Branche dauerhaft besser/schlechter) wird als Zyklus gelesen; Einzelereignisse (Pandemie) lösen die Regel aus |
| 8 | Verlust/Turnaround | operative Marge < 0 | Wert hängt an der Rückkehr zur Branchenmarge | DCF mit Zielmarge profitabler Sektorfirmen, Sicherheitsmarge mindestens 50 %, Wertuntergrenze 0 | Liquiditäts-/Refinanzierungsrisiko nur indirekt |
| 9 | Mega-Cap-Compounder | Börsenwert ≥ 500 Mrd. USD, Marge ≥ 20 %, FCF > 0 | Skalen- und Preissetzungsmacht; Überrendite fällt langsam | DCF mit Burggraben-Regeln v3, Vergleichsgruppe Archetyp | Segmente nicht getrennt (z. B. Cloud vs. Werbung); AMZN fällt wegen Marge < 20 % in „Wachstum mit Marge im Aufbau“ |
| 10 | Qualitätswachstum | Wachstum ≥ 8 %, 3J-Marge ≥ 15 %, FCF > 0 (unbekannter FCF zählt nicht dagegen) | nachweislich profitables Wachstum | DCF + KGV-Block nach Phase | – |
| 11 | Wachstum mit Marge im Aufbau | Wachstum ≥ 8 %, sonst nicht Qualität | Wert hängt an der Margenausweitung | DCF, Zielmarge = profitable Firmen desselben Sektors | Konglomerate wie SE (Handel + Spiele + Kredit) bekommen eine Mischmarge |
| 12 | Reif/Value | Wachstum < 8 % | Wert aus aktuellem Cashflow | DCF 50 % + KGV 50 % | Wertfallen (strukturell schrumpfend) |
| – | Mischkonzern | nicht erkennbar | companyfacts liefert keine Segmentdimensionen | – | Erkennung braucht Segmentdaten aus den Anhängen (offen) |

Für Neoclouds und Mag7 trennen die Regeln 5 und 9: Investitionen ≥ 40 % vom Umsatz bei negativem FCF gegenüber
positivem FCF bei ≥ 20 % Marge. META und MSFT investieren viel, verdienen es aber im laufenden Cashflow.

Verworfene Zyklikerregel: Margenspanne p10–p90 ≥ 10 Pp. markierte 2012–19 255 von 638 Nicht-Zyklikern und trennte nicht.
Die Regel „Umsatzrückgang plus Margenhalbierung“ markierte 153 von 691.

## 3. Universelle Leitplanken
- **Eigenkapitalwert ≥ 0** (beschränkte Haftung). Der Verlust im Stressszenario ist auf 100 % des Einsatzes begrenzt.
- **Optimistisch > Basis.**
  - Optimistische Zielmarge = max(Basis, p75 der Vergleichsgruppe, TTM).
  - Pessimistisch = min(Basis, eigene) und p25 nur ohne Burggraben.
  - Wenn optimistisch trotzdem nicht über der Basis liegt, wird das ausgewiesen.
- **Vergleichsgruppe nach Archetyp** für Beta, Marge und Kapitaleffizienz: Archetyp × Sektor ab 6 Firmen, sonst nur Archetyp.
- **Kapitaleffizienz** (Umsatz je investiertem Kapital) = Median aus eigenem Zykluswert, eigenem 3-Jahres-Wert und Vergleichsgruppe.
- **Fremdkapitalkosten aus dem Kupon** (Zinsaufwand ÷ Schulden, rf bis rf + 15 Pp.), wenn die Zinsdeckung ≤ 0 ist.
- **Länderrisikoprämie**: Damodaran-Tabelle (abgerufen 21.10.2026, `valuation/data/damodaran_crp_fetched_2026-10-21.csv`).
  - Umsatzregionen sind nicht verfügbar, daher gilt das Sitzland. Bekannte Schwäche: SE (Sitz Singapur) bekommt 0.
- **ADR-Regel** (Börsenwert ÷ Kurs ersetzt die EDGAR-Aktienzahl) nur für 20-F/40-F-Filer.
  - Bei US-Emittenten mit Abweichung außerhalb 0,5–2× gilt die Aktienzahl als unklar, und die Bewertung ist nicht belastbar (Up-C/Mehrklassen oder Split).
- **Strukturbruch**: Margenmediane, 3J-CAGR, Kapitaleffizienz und Langfrist-ROIC vor dem Bruch werden verworfen.
- **Konsensbasis**:
  - Passen die Niveaus (Konsens-Vorjahresumsatz 0,67–1,5× EDGAR), verankert der FY+1-Umsatz das Jahr 1.
  - Sonst werden nur die Wachstumsraten auf die EDGAR-Basis gelegt.
- **NTM-Gewinn zeitgewichtet**: Gewicht FY0 = verbleibende Monate ÷ 12.
- **„Bewertung nicht belastbar“** bei Basis ≤ 0, fairem Wert außerhalb 0,25–3× Kurs, veralteten Zahlen oder unklarer Aktienzahl.
  - Folge: kein Kaufen-unter, keine Tranchen, kein Stress aus der Bewertung. Die Rechnung bleibt sichtbar.

## 4. Eine Quelle in der App
- `v4_overlay.py` setzt Szenarien-Reiter, Bewertungskennzahlen, Investment und die Swing-Langfristtabelle aus v4.
- 5-Jahres-Kurs = Szenariowert × (1 + Eigenkapitalkosten)⁵.
- Kursabhängige Felder (Börsenwert, KGV, KUV, Kursziel-Abstand, Rohdaten-Kurs) werden auf den Snapshot-Kurs gerechnet.
- Veraltete Scanner-Bewertungsfelder (fv2030, Szenarien, SOTP-Platzhalter, Limits, Detailanalyse) erscheinen nicht mehr in der Rohdatentabelle und im CSV.
- Aktien ohne v4-Bewertung: Szenarien „k. A.“.

## 5. Swing-Regeln v4
- **Stopp**: mindestens 1 × Ø Tagesspanne (20 Tage, als ATR-Näherung) unter dem Ø Einstieg.
- **Ziel**: nächster Widerstand über dem Ø Einstieg aus Swing-Hochs, 50-, 100- und 200-Tage-Linie, 30-Wochen-Linie und 52-Wochen-Hoch.
- **Phasen** (Weinstein, 30-Wochen-Linie):
  - 2 = Kurs über steigender Linie
  - 3 = Kurs unter steigender Linie
  - 4 = unter fallender Linie
  - 1 = über fallender Linie
- Phase 3 und 4 sind eine harte Sperre: Schritt 1 „nicht erfüllt“, Chance/Risiko „gesperrt“.

## v4.1 – konsolidierter Regelsatz nach den vier Audits (21.10.2026)
Die Quellen sind V4_AUDIT.md (A), V4_AUDIT_VALUATION_CYC.md (C), V4_AUDIT_VALUATION_GROWTH.md (G) und V4_AUDIT_VALUATION_MEGA.md (M). Doppelte Fixes wurden zu je einer Regel zusammengeführt. Alle Regeln sind fest, es gibt kein Ticker-Tuning.

### Klassifikator – Reihenfolge (A-F5/F7/F1, C6, M4)
1. Versicherer (Typ) → bank. Typ Bank/Finanzen → bank **nur** mit Bankbilanz (Kredite ≥ 10 % der Bilanzsumme). Sonst wird anhand der Zahlen weiter klassifiziert (IREN, HOOD).
2. REIT (Typ).
3. Versorger → utility nur ohne Zyklusmuster. Mit Zyklusmuster → cyclical (IPP: VST). Die Margenspanne allein reicht nicht (sonst NEE → cyclical mit Wert 0).
4. pre_revenue (< 50 Mio.) → buildout (Capex ≥ 40 %, g ≥ 20 %, FCF < 0).
5. **turnaround vor Zyklus** (3J-Median < 0 und TTM ≤ 2 %, oder TTM < 0 und 3J < 5 %).
6. **mega vor Hyper/Zyklus**: ≥ 500 Mrd., max(op. Marge, OCF-Marge) ≥ 20 %, FCF > 0 oder OCF > 0 (Capex-Welle AMZN). Beta und Margen kommen dann aus der Mega-Gruppe, der Konsens J1–2 bleibt ungekappt.
7. Zyklusbranche: Scanner-Typ oder **SIC** (Autos 3711/3713/3714, Airlines 4512/4522, Chemie 281/282/286/287/289, Metalle 331–334, Bau 152/153, Maschinen 3523/3531–3533, Reedereien 441/442/444) → cyclical (TSLA, AMD).
8. hyper (g ≥ 25 %) → Zyklusmuster → quality → scaler → mature.
- Zyklusmuster: Umsatz −10 % J/J **und** Marge ≤ 50 % des Medians. Rückgänge in 2020–21 zählen nur, wenn es ≥ 2 Episoden gibt. Jahre mit wesentlichen aufgegebenen Geschäftsbereichen (|disc_ops| ≥ 2 % Umsatz, Jahr und Folgejahr) zählen nicht (Abspaltung ≠ Zyklus: GE/MMM/RTX).
- Aktiensprung ≥ 1,9× bzw. ≤ 1/1,9 in einem Quartal = Split, keine Verwässerung (CRWD, NOW).
- Hysterese: Ein Wechsel muss im Vorquartal bestätigt sein. Die Klasse aus dem Vorquartal bleibt, solange ihre gelockerte Bedingung gilt (hyper 20 %, quality 6 %/12 %, mega 400 Mrd./16 %, scaler 6 %, mature < 10 %, turnaround < 0 %).

### Daten (C1/D2, M2, A-F8/C9, M16)
- Schulden: Die Fallback-Kette der XBRL-Tags (valuation/debt.py) wird genutzt, wenn der Scanner 0 meldet. Bei einer Finanzsparte (Finanzforderungen ≥ 20 % der Bilanz) werden 90 % der Forderungen als gedeckte Schulden herausgenommen, und das Finanzsparten-EK wird zum Buchwert addiert.
- **Schulden 0 bei wesentlichem Zinsaufwand (> max(50 Mio., 0,5 % Umsatz)) → nicht belastbar.**
- FCF exakt 0 = fehlt (None). Investiertes Kapital ≤ 0/fehlt, Pflichtfelder fehlen → nicht belastbar.
- CIK: BRK-B und CRWV sind jetzt über edgar_supp angebunden. XOM: Die SEC-companyfacts enthalten keine Umsatz-Historie (nur 4 Q-Werte 2025/26, eigene Tags) → dokumentierte Datenlücke.
- Jeder Export schreibt meta.input_hash (SHA-256 über Konsens/Kurse/Meta, Caches nach Name+Größe+mtime, Code).

### Modell (G1–G5, G10, C2–C5, C7, C8, M1, M7, M14, A-F6)
- **g_T = rf** (konsistent mit Damodarans impliziter ERP). Abnahmetest: Der Median FV/Kurs 2012–19 muss in 0,85–1,15 liegen. Das ist nur ein Test, keine Kalibrierung.
- Jahr 1 = die 12 Monate nach dem letzten gemeldeten Quartal (zeitgewichtet FY0/FY1). Damit sind G4 und M6 als eine Regel umgesetzt: NTM ab Quartalsende statt Rest-FY0.
- Wachstum: Jahr 3 = min(g2, 40 %), danach linear auf g_T. Umsatz J10 ≤ Umsatz J2 × 1,2244⁸ (Top-Dezil 3J-CAGR 2012–19, n = 22.053). Diese Regel wurde statt der geometrischen Halbwertszeit (M10) gewählt, die Kappe wirkt gleichgerichtet.
- buildout: Wert = DCF-EK ÷ heutige Aktien. Die Finanzierungslücke und die zum Kurs nötigen Aktien sind nur Information. Test: tests/test_v4_price_invariance.py (Kurs ±30 % → FV ±5 %).
- Zielmarge: Bewiesene Marge (4 positive TTM-Quartale) über dem Peer-Median fällt nur bis zum Peer-p75 zurück. Ein nicht messbarer Burggraben bedeutet halbe Reversion. Die Peers für hyper/scaler/turnaround sind reife Firmen (g < 15 %, profitabel) desselben Sektors.
- Zykliker (≥ 20 Q): Ziel = eigene Zyklusmitte, Szenarien Zyklus-p25/p75, Start = TTM.
- Rüstung: Basis = Basisszenario, Ziel ≥ eigene 3J-Marge.
- Bank: Start-ROE = 10J-Median. Der Überrenditeanteil hängt an der Persistenz (≥ 80 % → 0,75, ≥ 50 % → 0,5, sonst 0). Szenarien über ROE p25/p75. Versorger: 5J-ROE ±1 Pp., Buchwachstum = 3J-EK-CAGR ±2 Pp. REIT: β ≤ 1, Wachstum = FFO/Aktie-3J-CAGR ±2 Pp., AFFO = 0,9 × FFO, kein KGV-Block.
- Szenarien: pess/opt-J2 = Basis-J2 ± Abstand J1, danach sortiert. S2C = Basis × 0,75/1,25. Die Spanne wird auf 1/3–3× Basis begrenzt (Hinweis „Spanne nicht belastbar“).
- Pess-Untergrenze = Netto-Cash/Aktie bei FCF > 0 oder Cash > 3 Jahre Burn. Hyper mit Verlust: pess = 0 (Scheitern).
- **Nicht belastbar zusätzlich**, wenn pess/Basis (vor Kappung) < 0,25, Pflichtdaten fehlen oder Schulden 0 bei Zinsaufwand.
- Nicht umgesetzt (dokumentiert): SOTP/Segmente (M15, A-F11), Regionen-CRP (G8/E), unabhängiger Branchen-KGV-Block (M13), Terminal-Beta (M9), Konsens-Hygiene FY0-Einmaleffekte (M12), Normalisierung Einmalkosten (M11), Doppellisting SAP/SAP.DE (A-F9).

## v4.2 (21.10.2026)
Rules added: terminal beta 50/50 own/industry; one-off charges normalised; consensus clean-up; industry P/E block; CRP by revenue region; spin-off rule; hysteresis chain; regulated vs cyclical utility; XBRL instance debt (finance arm excluded); predecessor CIK; v4 bank path (own ROE history, persistence, p25/p75); mega entry also on TTM EBITDA.
Level test 0.85–1.15 still FAIL (train 0.654, val 0.78). Diagnosed causes (not changed, to avoid fitting): terminal ROIC=WACC without a moat, reinvestment via sales-to-capital incl. goodwill, terminal tax at the pre-2018 statutory rate, margin reversion. Beta is not a driver.
