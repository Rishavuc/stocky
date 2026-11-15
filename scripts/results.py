"""Write a portable summary from measured reports, never hand-entered scores."""

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
reports = [
    json.loads(p.read_text()) for p in sorted((ROOT / "models").glob("*_report.json"))
]
lines = [
    "# Measured experiment results",
    "",
    "Generated from the saved reports. Model selection uses validation error. The final test is not used to choose a winner.",
    "",
    "| Instrument | Currency | Horizon | Selected model | Test MAE | Baseline MAE | Lower error than baseline |",
    "| --- | --- | --- | --- | ---: | ---: | --- |",
]
for r in reports:
    lines.append(
        f"| {r['symbol']} | {r.get('currency', 'INR')} | {r['horizon_sessions']} observations | {r['selected_model']} | {r['test'][r['selected_model']]['mae']:.4f} | {r['test']['Last-price baseline']['mae']:.4f} | {'Yes' if r['beats_baseline'] else 'No'} |"
    )
lines += [
    "",
    "MAE is mean absolute price error. The baseline predicts that the future close equals the latest visible close. These experiments do not establish profitable future trading. Full provenance, test plots, and strategy assumptions are available in Model lab.",
    "",
    "The source data excludes unfinished daily bars. Each report contains its dataset checksum, seed, library versions, and dated partitions.",
]
(ROOT / "docs/RESULTS.md").write_text("\n".join(lines) + "\n")
print(f"Wrote measured summary for {len(reports)} experiments.")
