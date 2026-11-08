# Swing System (öffentlich)

Öffentliches Portfolio (MIT) von Lennart Merschel. Konzept, Anforderungen und Prüfung liegen bei ihm; ein großer Teil der Umsetzung ist mit Coding-Assistenten entstanden. Das Programm ist eine Entscheidungshilfe und erteilt keine Aufträge.

Dieses Repository ist der öffentliche Codestand: Streamlit-App unter `app/`, Bewertung unter `valuation/`, Swing unter `swing/`, Backtests, Export-Skripte, Tests und die Notizen in `docs/`. Die spätere private Prüfversion (fv18), ihr Quelltext und ihr Daten-Snapshot liegen nicht hier und werden hier nicht hochgeladen. Aus diesem Baum ist keine Website deployed.

Kurs- und Fundamentaldaten fehlen aus Lizenzgründen. Ohne lokalen Snapshot unter `data/` ist `./run.sh` keine vollständige Demo.

Die alten Bildlinks (`docs/screenshots/`) zeigten Dateien, die nie committed waren, weil `.gitignore` jedes Verzeichnis `screenshots/` ausgeschlossen hat. Die Links sind entfernt. Geprüfte Aufnahmen können später nach `docs/screenshots/` gelegt werden.

GitHub Actions führt `tests/test_valuation_v2.py` und `tests/test_valuation_v3.py` ohne die beiden ERP-Tests aus. Die ERP-Tests brauchen `valuation/data/damodaran_erp_monthly.csv`, und die Datei ist nicht im Repository. Drei weitere Tests in denselben Dateien werden übersprungen, solange die Export-JSONs fehlen. Klicktests und `tests/test_v4_price_invariance.py` laufen nicht in CI. Es gibt kein Status-Badge.

Die Kennzahlen in [README.md](README.md) und in `docs/research/` sind historische Auswertungen in diesem Repository, kein Live-Track-Record und keine Prognose. DuckDB (nur `scripts/export_market_hist.py`) und Playwright (nur Klicktests) stehen nicht in `requirements.txt`.

Ausführliche Fassung: [README.md](README.md).
