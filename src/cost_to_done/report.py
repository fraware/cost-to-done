"""Offline HTML report with explicit provenance and no third-party assets."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any


def _money(value: str | float | None) -> str:
    if value is None:
        return "Not established"
    amount = float(value)
    if amount == float("inf"):
        return "Unbounded"
    return f"${amount:,.4f}" if amount < 1 else f"${amount:,.2f}"


def render_html(report: dict[str, Any], *, title: str, demo: bool = False) -> str:
    """Generate an HTML file fully usable offline, without code execution."""
    safe_title = escape(title, quote=True)
    rows = report["rows"]
    finite = [float(r["cost_per_success_usd"]) for r in rows if r["cost_per_success_usd"] is not None]
    largest = max(finite, default=1)
    table_rows = []
    for i, row in enumerate(rows, 1):
        cost = row["cost_per_success_usd"]
        ratio = max(2, round(100 * float(cost) / largest)) if cost is not None and largest > 0 else 100
        ci = row.get("bootstrap_95_usd")
        ci_text = (f"95% task bootstrap [{_money(ci[0])}, " + f"{'Unbounded' if ci[1] is None else _money(ci[1])}]") if ci else "No interval"
        table_rows.append(f'''
          <tr>
            <td class="position">{i if report["eligible_for_ranking"] else "—"}</td>
            <td><strong>{escape(row["configuration"])}</strong><span class="sub">{escape(row["cost_basis"])} · {escape(row["retry_policy"])}</span></td>
            <td class="number">{row["passed"]}/{row["trials"]}<span class="sub">{100*row["pass_rate"]:.1f}% verified</span></td>
            <td class="number">{_money(row["total_cost_usd"])}<span class="sub">{row["attempts"]} charged attempts</span></td>
            <td><div class="cost"><span>{_money(cost)}</span><div class="track" aria-hidden="true"><div class="fill" style="width:{ratio}%"></div></div></div><span class="sub">{ci_text}</span></td>
            <td class="number">{row["median_seconds"]:.1f}s<span class="sub">median trial</span></td>
          </tr>
        ''')
    warns = "".join(f"<li>{escape(w)}</li>" for w in report["warnings"])
    warning_markup = f'<section class="notes"><h2>Interpretation limits</h2><ul>{warns}</ul></section>' if warns else ""
    badge = '<span class="notice">SYNTHETIC DATA · DESIGN DEMONSTRATION</span>' if demo else '<span class="notice">LOCAL EVALUATION DATA · VERIFY PROVENANCE BEFORE SHARING</span>'
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title} — Cost to Done</title>
<style>
:root {{ font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; color:#161616; background:#f5f3ec; }}
*{{box-sizing:border-box}}body{{margin:0}}a{{color:inherit}}.shell{{max-width:1280px;margin:0 auto;padding:0 42px}}
nav{{border-bottom:1px solid #c9c6bd;}}nav .shell{{display:flex;align-items:center;justify-content:space-between;min-height:72px;gap:20px}}
.wordmark{{font-size:13px;font-weight:800;letter-spacing:-.03em}}.wordmark b{{background:#c6382d;color:white;padding:8px 10px;margin-right:10px}}
nav small, .muted{{color:#67645e}}nav small{{font-size:12px;letter-spacing:.07em;text-transform:uppercase}}
.hero{{padding:90px 0 65px;display:grid;grid-template-columns:1.3fr .7fr;gap:45px;border-bottom:1px solid #c9c6bd}}
.kicker{{color:#b22d25;text-transform:uppercase;letter-spacing:.16em;font-weight:800;font-size:12px}}
h1{{font-family:Georgia,"Times New Roman",serif;font-weight:400;letter-spacing:-.065em;font-size:clamp(52px,6.3vw,104px);line-height:.99;margin:24px 0}}
.hero p{{font-size:18px;line-height:1.55;max-width:700px;color:#52504c}}
.hero aside{{border-top:4px solid #c6382d;padding:22px 0}}.hero aside h2{{font:normal 32px/1.13 Georgia,serif;letter-spacing:-.04em;margin:10px 0 18px}}
.hero aside p{{font-size:14px;line-height:1.55;color:#66635d}}.notice{{display:inline-block;font:700 11px/1.35 monospace;background:#e3ded2;padding:11px 13px;letter-spacing:.04em}}
.stats{{display:flex;gap:0;border-bottom:1px solid #c9c6bd}}.stat{{padding:33px 0;flex:1}}.stat+.stat{{padding-left:35px;border-left:1px solid #c9c6bd}}
.stat label{{font:700 11px monospace;text-transform:uppercase;color:#77716b;letter-spacing:.08em;display:block;margin-bottom:15px}}
.stat strong{{font:normal 42px Georgia,serif;letter-spacing:-.06em}}
.section-head{{display:flex;justify-content:space-between;align-items:end;gap:25px;margin:70px 0 22px}}
.section-head h2{{font:normal 40px Georgia,serif;letter-spacing:-.05em;margin:0}}.section-head span{{font:12px monospace;color:#706b65}}
.table-wrap{{overflow:auto;border-top:2px solid #171717}}table{{border-collapse:collapse;width:100%;min-width:920px}}th{{font:700 11px monospace;text-transform:uppercase;letter-spacing:.04em;text-align:left;padding:18px 14px;color:#66635d;border-bottom:1px solid #bdb8af}}
td{{padding:22px 14px;border-bottom:1px solid #d4d0c8;font-size:15px;vertical-align:middle}}td.position{{font:16px monospace;color:#a6a098}}td.number{{font:600 17px monospace;white-space:nowrap}}
.sub{{display:block;color:#79756d;font-size:11px;font-weight:400;margin-top:7px;line-height:1.4}}.cost>span{{font:700 19px monospace}}.track{{width:200px;max-width:100%;height:7px;background:#ded8d0;margin-top:10px}}.fill{{height:100%;background:#c6382d}}
.notes{{border-top:1px solid #beb9b1;margin:70px 0 40px;padding:25px 0}}.notes h2{{font:normal 29px Georgia,serif}}.notes li{{max-width:880px;margin-bottom:12px;line-height:1.5;color:#595650}}
.method{{display:grid;grid-template-columns:1fr 1fr;gap:50px;margin:65px 0 90px;border-top:2px solid #161616;padding-top:30px}}
.method h3{{font-size:12px;letter-spacing:.07em;text-transform:uppercase}}.method p{{font-size:14px;color:#55514b;line-height:1.6}}
footer{{border-top:1px solid #c9c6bd;padding:30px 0 48px;font-size:12px;color:#66635d;display:flex;justify-content:space-between;gap:20px}}
@media(max-width:760px){{.shell{{padding:0 21px}}.hero{{grid-template-columns:1fr;padding:52px 0}}.stats{{display:grid;grid-template-columns:1fr 1fr}}.stat+.stat{{padding-left:0;border:0}}.stat strong{{font-size:32px}}.method{{grid-template-columns:1fr}}.section-head{{display:block}}.section-head h2{{font-size:34px}}nav small{{display:none}}}}
</style></head><body>
<nav><div class="shell"><div class="wordmark"><b>1</b> COST TO DONE</div><small>Open methodology · local evidence</small></div></nav>
<main class="shell">
<section class="hero"><div><div class="kicker">The receipt for completed work</div><h1>Price a result.<br>Not a token.</h1><p>Which agent configuration actually finishes the job? Every failed attempt, every verified pass, and every dollar counted against the same task contract.</p></div>
<aside>{badge}<h2>{safe_title}</h2><p>Trial-level accounting. Each recorded success must terminate with a verifier pass. Price source, retry policy, and artifact digests travel with the result.</p></aside></section>
<div class="stats"><div class="stat"><label>Distinct tasks</label><strong>{report["tasks"]}</strong></div><div class="stat"><label>Recorded trials</label><strong>{report["trials"]}</strong></div><div class="stat"><label>Configurations</label><strong>{len(rows)}</strong></div><div class="stat"><label>Comparable ranking</label><strong>{"YES" if report["eligible_for_ranking"] else "NO"}</strong></div></div>
<section class="section-head"><h2>Cost per verified completion</h2><span>Lower is better · failures included in spend</span></section>
<div class="table-wrap"><table><thead><tr><th>#</th><th>Configuration</th><th>Verified</th><th>Total spend</th><th>Cost / success</th><th>Time</th></tr></thead><tbody>{''.join(table_rows)}</tbody></table></div>
{warning_markup}
<section class="method"><div><h3>Accounting contract</h3><p>Cost per success equals the full spend across completed trials divided by their verified successes. Expenses from unsuccessful trials are retained. The ratio is undefined if no trial passes. Exact decimal strings avoid floating-point drift in summed charges.</p></div><div><h3>Comparability contract</h3><p>Rankings are withheld if task sets or per-task replication differ, or billing and rate-card estimates are mixed. A common task verifier and pinned task digest are mandatory. Five or more distinct tasks unlock descriptive task-cluster bootstrap intervals.</p></div></section>
</main><footer class="shell"><span>COST TO DONE · Local-first report format v0.1</span><span>No external scripts, analytics, or network requests.</span></footer>
</body></html>'''


def write_report(report: dict[str, Any], output: str | Path, *, title: str, demo: bool = False) -> None:
    """Write HTML in UTF-8 with deterministic content for the same inputs."""
    Path(output).write_text(render_html(report, title=title, demo=demo), encoding="utf-8")
