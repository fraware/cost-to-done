"""Offline descriptive panel report, recomputed from raw redacted records."""
from __future__ import annotations

from html import escape
from pathlib import Path

from .panel_results import read_panel_directory, summarize_panel
from .private_files import publish_private_texts
from .report import _money


def render_panel(plan: dict, records: list[dict]) -> str:
    """Expose all planned episodes and withhold ratios on incomplete support."""
    summary = summarize_panel(plan, records)
    rows = summary["rows"]
    complete = summary["complete_matched_accounting"]
    status = "Complete matched accounting" if complete else "Incomplete accounting — ratios withheld"
    observed = sum(r["observed"] for r in rows)
    passed = sum(r["passed"] for r in rows)
    unresolved = sum(r["unresolved"] + r["missing"] for r in rows)
    table = []
    for row in rows:
        name = escape(row["configuration"])
        model = escape(plan["configurations"][row["configuration"]]["model"])
        cost = _money(row["known_rate_card_estimate_usd"])
        ratio = _money(row["cost_per_verified_completion_usd"])
        table.append(f"<tr><th scope='row'>{model}<small>{name}</small></th>"
                     f"<td>{row['passed']} / {row['planned']}</td>"
                     f"<td>{row['failed']}</td><td>{row['unresolved']}</td>"
                     f"<td>{row['missing']}</td><td>{cost}<small>"
                     f"{row['known_cost_records']} / {row['planned']} cost records</small></td>"
                     f"<td>{ratio}</td></tr>")
    detail = []
    for trial, result in zip(plan["trials"], summary["trials"]):
        detail.append(f"<tr><th scope='row'>{escape(trial['task'])}</th>"
                      f"<td>{escape(trial['configuration'])}</td><td>{trial['repetition']}</td>"
                      f"<td>{escape(result['state'])}</td>"
                      f"<td>{_money(result.get('known_rate_card_estimate_usd'))}</td></tr>")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Development panel — Cost to Done</title><style>
:root{{font-family:system-ui,sans-serif;color:#161616;background:#f5f3ec;line-height:1.5}}
*{{box-sizing:border-box}}body{{margin:0}}main{{max-width:1180px;margin:auto;padding:36px 24px 60px}}
header{{border-bottom:1px solid #beb9b1;padding-bottom:20px}}h1{{font:normal clamp(36px,6vw,72px)/1.05 Georgia,serif;letter-spacing:-.04em;margin:20px 0}}
h2{{font:normal 30px Georgia,serif;margin-top:45px}}.eyebrow{{font:700 12px monospace;letter-spacing:.09em;text-transform:uppercase;color:#b22d25}}
.status{{border-left:4px solid #b22d25;padding:12px 16px;background:#ebe6db}}
.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:20px;margin:28px 0}}
.metrics div{{border-top:1px solid #aaa49b;padding:12px 0}}.metrics strong{{font:normal 36px Georgia,serif;display:block}}small{{display:block;color:#68645d}}
.scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;min-width:690px;font-variant-numeric:tabular-nums}}
th,td{{padding:14px 10px;text-align:left;border-bottom:1px solid #d4d0c8;white-space:nowrap}}thead th{{font-size:11px;text-transform:uppercase}}
code{{overflow-wrap:anywhere}}footer{{margin-top:50px;border-top:1px solid #aaa49b;padding-top:20px;color:#555}}
@media(max-width:640px){{.metrics{{grid-template-columns:1fr 1fr}}main{{padding:22px 16px}}}}
</style></head><body><main>
<header><div class="eyebrow">Cost to Done · Public development fixtures</div>
<h1>Cost per completed task.</h1><p>Descriptive observations only. No model ranking, invoice reconciliation, or independent verifier replay.</p></header>
<p class="status"><strong>{status}</strong><br>Known expenditure excludes unresolved liabilities. Missing trials are not zero-cost trials.</p>
<section class="metrics" aria-label="Trial counts"><div><small>Planned</small><strong>{plan['planned_trial_count']}</strong></div>
<div><small>Observed records</small><strong>{observed}</strong></div><div><small>Settled verifier passes</small><strong>{passed}</strong></div>
<div><small>Unresolved or missing</small><strong>{unresolved}</strong></div></section>
<h2>Configuration observations</h2><div class="scroll"><table><thead><tr><th>Configuration</th><th>Pass / planned</th><th>Fail</th><th>Unresolved</th><th>Missing</th><th>Known estimate</th><th>Cost / completion</th></tr></thead>
<tbody>{''.join(table)}</tbody></table></div>
<h2>Every planned episode</h2><div class="scroll"><table><thead><tr><th>Task</th><th>Configuration</th><th>Repetition</th><th>Accounting state</th><th>Known estimate</th></tr></thead><tbody>{''.join(detail)}</tbody></table></div>
<h2>Evidence identity and scope</h2><p>Plan SHA-256: <code>{escape(plan['plan_sha256'])}</code></p>
<p>Declared total admission allowance: {_money(plan['estimated_admission_total_usd'])}. This is not a provider-side hard cap. Costs are rate-card estimates; these public tasks do not support claims about unseen repositories. Results are reconstructed from redacted status and hash records, not independently authenticated execution artifacts.</p>
<footer>Standalone offline report · No scripts, trackers, or external assets.</footer>
</main></body></html>"""


def write_panel_report(directory: Path, output: Path) -> None:
    """Read source observations; never trust a saved derived summary."""
    plan, records = read_panel_directory(directory)
    publish_private_texts([(output, render_panel(plan, records))])
