"""Static HTML procedure cards + index. Dependency-free, printable, works offline.

Design intent (per the repo's demo-surface doctrine): these are documents, not
dashboards — recessive support ink, one accent, the reserved warning/serious
colors only for the draft banner and CRITICAL markers, and every marker
carries a text label so nothing is color-alone. The draft/review state and the
content-addressed version are rendered on every card; the card is honest about
what it is.
"""

from __future__ import annotations

import html
from pathlib import Path

from halo.edu.corpus import load_corpus, module_version
from halo.edu.diagrams import get_diagram
from halo.edu.models import Med, ProcedureModule, ReviewStatus, Step

_CSS = """
:root { --ink:#1f2429; --muted:#5b6570; --line:#d7dde2; --panel:#f6f8fa;
  --accent:#0b57d0; --warn-bg:#fdf3e1; --warn-line:#b26a00; --serious:#b3261e; }
* { box-sizing:border-box; }
body { font:15px/1.55 system-ui,-apple-system,sans-serif; color:var(--ink);
  max-width:880px; margin:0 auto; padding:24px; background:#fff; }
h1 { font-size:26px; line-height:1.2; margin:4px 0 2px; }
h2 { font-size:15px; text-transform:uppercase; letter-spacing:.06em;
  color:var(--muted); border-bottom:1px solid var(--line); padding-bottom:4px;
  margin:26px 0 10px; }
a { color:var(--accent); }
.chip { display:inline-block; font-size:12px; color:var(--muted);
  border:1px solid var(--line); border-radius:999px; padding:1px 10px; margin-right:6px; }
.banner { background:var(--warn-bg); border:1px solid var(--warn-line);
  border-radius:8px; padding:10px 14px; font-size:13.5px; margin:14px 0; }
.banner strong { color:var(--warn-line); }
.tile { display:flex; gap:14px; align-items:baseline; background:var(--panel);
  border:1px solid var(--line); border-radius:10px; padding:12px 16px; margin:14px 0; }
.tile .n { font-size:34px; font-weight:700; letter-spacing:-.02em; }
.tile .l { color:var(--muted); font-size:13.5px; }
ol.steps { padding-left:0; counter-reset:step; list-style:none; }
ol.steps > li { border:1px solid var(--line); border-radius:10px; padding:12px 14px 12px 52px;
  margin:10px 0; position:relative; counter-increment:step; }
ol.steps > li::before { content:counter(step); position:absolute; left:14px; top:12px;
  width:26px; height:26px; border-radius:50%; background:var(--panel);
  border:1px solid var(--line); display:flex; align-items:center; justify-content:center;
  font-weight:700; font-size:13px; }
ol.steps > li.critical { border-color:var(--serious); }
.crit { color:var(--serious); font-weight:700; font-size:11.5px;
  text-transform:uppercase; letter-spacing:.08em; }
.step-title { font-weight:650; }
.detail { color:var(--muted); font-size:14px; margin-top:2px; }
figure { margin:12px 0 2px; }
figure svg { width:100%; max-width:420px; height:auto; background:var(--panel);
  border:1px solid var(--line); border-radius:8px; }
table { border-collapse:collapse; width:100%; font-size:13.5px; }
th, td { border:1px solid var(--line); padding:7px 9px; text-align:left;
  vertical-align:top; }
th { background:var(--panel); font-size:12px; text-transform:uppercase;
  letter-spacing:.05em; color:var(--muted); }
ul.tight { margin:6px 0; padding-left:20px; } ul.tight li { margin:4px 0; }
ul.check { list-style:none; padding-left:2px; }
ul.check li::before { content:"\\2610\\00a0\\00a0"; color:var(--muted); }
.cols { display:grid; grid-template-columns:1fr 1fr; gap:0 26px; }
.muted { color:var(--muted); } .small { font-size:12.5px; }
footer { margin-top:30px; border-top:1px solid var(--line); padding-top:10px;
  color:var(--muted); font-size:12px; }
.flow { margin:16px 0 4px; } .flow svg { width:100%; height:auto; }
@media print { body { padding:0; font-size:12.5px; }
  ol.steps > li, .tile, figure { break-inside:avoid; } a { color:inherit; } }
@media (max-width:640px) { .cols { grid-template-columns:1fr; } }
"""

_DISCLAIMER = (
    "HALO readiness &amp; CME — research demo, not a medical device and not accredited CME. "
    "Synthetic data only. Verify all doses against local protocol and pharmacy."
)


def _e(text: str) -> str:
    return html.escape(text, quote=True)


def _draft_banner(module: ProcedureModule) -> str:
    if module.review.status is ReviewStatus.REVIEWED and module.review.reviewed_by:
        return (
            f'<div class="banner"><strong>REVIEWED</strong> by '
            f"{_e(module.review.reviewed_by)} ({_e(module.review.date)}), "
            f"v{module.review.version}.</div>"
        )
    return (
        f'<div class="banner"><strong>DRAFT — PENDING PHYSICIAN REVIEW.</strong> '
        f"Authored {_e(module.review.date)} by {_e(module.review.author)}. "
        f"Do not treat as validated clinical guidance.</div>"
    )


def _step_flow(module: ProcedureModule) -> str:
    """One-row schematic of the step sequence; critical steps carry a labeled marker."""
    n = len(module.steps)
    w, h, gap = 760, 74, 8
    box_w = (w - gap * (n - 1)) / n
    parts = []
    for i, step in enumerate(module.steps):
        x = i * (box_w + gap)
        color = "#b3261e" if step.critical else "#d7dde2"
        parts.append(
            f'<rect x="{x:.1f}" y="18" width="{box_w:.1f}" height="34" rx="4" '
            f'fill="#f6f8fa" stroke="{color}" stroke-width="{2 if step.critical else 1}"/>'
            f'<text x="{x + box_w / 2:.1f}" y="40" text-anchor="middle" font-size="14" '
            f'font-weight="700" fill="#1f2429">{step.n}</text>'
        )
        if step.critical:
            parts.append(
                f'<text x="{x + box_w / 2:.1f}" y="12" text-anchor="middle" font-size="8.5" '
                f'fill="#b3261e" letter-spacing=".08em">CRIT</text>'
            )
        if i < n - 1:
            parts.append(
                f'<line x1="{x + box_w:.1f}" y1="35" x2="{x + box_w + gap:.1f}" y2="35" '
                f'stroke="#8a939b" stroke-width="1.5"/>'
            )
    body = "".join(parts)
    return (
        f'<div class="flow"><svg viewBox="0 0 {w} {h}" role="img" '
        f'aria-label="step sequence" xmlns="http://www.w3.org/2000/svg" '
        f'font-family="system-ui, sans-serif">{body}'
        f'<text x="0" y="{h - 4}" font-size="10" fill="#8a939b">'
        f"{n} steps &#183; red outline + CRIT = critical step</text></svg></div>"
    )


def _dose_cell(spec_text: str | None) -> str:
    return _e(spec_text) if spec_text else '<span class="muted">&mdash;</span>'


def _med_rows(meds: tuple[Med, ...]) -> str:
    rows = []
    for med in meds:
        cautions = "".join(f'<div class="small muted">&#9888; {_e(c)}</div>' for c in med.cautions)
        notes = "".join(f'<div class="small muted">{_e(n)}</div>' for n in med.notes)
        rows.append(
            "<tr>"
            f"<td><strong>{_e(med.name)}</strong>"
            f'<div class="small muted">{_e(med.role)}</div></td>'
            f"<td>{_dose_cell(med.adult.text if med.adult else None)}</td>"
            f"<td>{_dose_cell(med.peds.text if med.peds else None)}</td>"
            f"<td>{_e(med.route)}{cautions}{notes}</td>"
            "</tr>"
        )
    return "".join(rows)


def _step_item(step: Step) -> str:
    critical = '<span class="crit">Critical &#8212; </span>' if step.critical else ""
    figure = ""
    if step.media:
        svg = get_diagram(step.media)
        if svg:
            figure = f"<figure>{svg}</figure>"
    detail = f'<div class="detail">{_e(step.detail)}</div>' if step.detail else ""
    return (
        f'<li class="{"critical" if step.critical else ""}">'
        f'<div class="step-title">{critical}{_e(step.action)}</div>{detail}{figure}</li>'
    )


def _list(items: tuple[str, ...], cls: str = "tight") -> str:
    return f'<ul class="{cls}">' + "".join(f"<li>{_e(i)}</li>" for i in items) + "</ul>"


def card_html(module: ProcedureModule) -> str:
    """One self-contained, printable procedure card."""
    version = module_version(module.id)
    minutes = module.time_target.minutes
    tile_number = f"{minutes} min" if minutes is not None else "NOW"
    references = "".join(
        f"<li><strong>{_e(r.label)}.</strong> {_e(r.cite)}</li>" for r in module.references
    )
    drill_note = ""
    if module.drill:
        drill_note = (
            f'<p class="small muted">Drill available: {len(module.drill.decision_points)} '
            f"decision points &#183; run <code>python -m halo.edu.demo drill "
            f"{_e(module.id)} --interactive</code></p>"
        )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(module.name)} — HALO</title><style>{_CSS}</style></head><body>
<header>
  <span class="chip">{_e(module.category)}</span>
  <span class="chip">HALO &#183; high acuity, low occurrence</span>
  <h1>{_e(module.name)}</h1>
  <p class="muted">{_e(module.one_liner)}</p>
</header>
{_draft_banner(module)}
<div class="tile"><span class="n">{_e(tile_number)}</span>
  <span class="l">{_e(module.time_target.label)}</span></div>
{_step_flow(module)}
<div class="cols">
  <section><h2>Indications</h2>{_list(module.indications)}</section>
  <section><h2>Cautions / contraindications</h2>{_list(module.contraindications)}</section>
</div>
<div class="cols">
  <section><h2>Call in parallel</h2>{_list(module.team_calls)}</section>
  <section><h2>Equipment</h2>{_list(module.equipment, cls="check")}</section>
</div>
<section><h2>Steps</h2><ol class="steps">{"".join(_step_item(s) for s in module.steps)}</ol></section>
<section><h2>Medications</h2>
<table><thead><tr><th>Drug</th><th>Adult</th><th>Pediatric</th><th>Route / cautions</th></tr></thead>
<tbody>{_med_rows(module.meds)}</tbody></table>
<p class="small muted">Weight-based doses compute from patient context (CLI/API/FHIR);
missing weight or age is refused, never guessed.</p></section>
<div class="cols">
  <section><h2>Pitfalls</h2>{_list(module.pitfalls)}</section>
  <section><h2>Success looks like</h2>{_list(module.success_criteria)}</section>
</div>
<section><h2>Aftercare</h2>{_list(module.aftercare)}</section>
<section><h2>References</h2><ul class="tight">{references}</ul>{drill_note}</section>
<footer>{_DISCLAIMER}<br>Content {_e(version)} &#183; review status:
{_e(module.review.status.value)} &#183; diagrams are labeled schematics, not anatomy plates.</footer>
</body></html>"""


def index_html(modules: tuple[ProcedureModule, ...]) -> str:
    """Findability index: every card, its aliases, and how to search."""
    rows = []
    for m in modules:
        minutes = m.time_target.minutes
        rows.append(
            "<tr>"
            f'<td><a href="{_e(m.id)}.html"><strong>{_e(m.name)}</strong></a>'
            f'<div class="small muted">{_e(m.one_liner)}</div></td>'
            f"<td>{_e(m.category)}</td>"
            f"<td>{_e(f'{minutes} min') if minutes is not None else 'now'}</td>"
            f'<td class="small muted">{_e(", ".join(m.aliases[:6]))}</td>'
            "</tr>"
        )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HALO — readiness &amp; CME cards</title><style>{_CSS}</style></head><body>
<header><span class="chip">HALO &#183; module 3</span>
<h1>Readiness &amp; CME — procedure cards</h1>
<p class="muted">The procedures most likely to kill when fumbled are the ones performed least.
Find the card in seconds; drill it in minutes; the drill leaves a CME evidence record.</p></header>
<div class="banner"><strong>ALL CONTENT DRAFT — PENDING PHYSICIAN REVIEW.</strong>
Research demo, not clinical guidance.</div>
<table><thead><tr><th>Card</th><th>Category</th><th>Clock</th><th>Answers to (aliases)</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table>
<section><h2>Find a card from free text</h2>
<p class="small">CLI: <code>python -m halo.edu.demo find "chemical explosion 2pam"</code>
&nbsp;&#183;&nbsp; API: <code>GET /edu/find?q=...</code> &nbsp;&#183;&nbsp; no match returns
this list, never a guess.</p></section>
<footer>{_DISCLAIMER}</footer>
</body></html>"""


def write_cards(out_dir: Path) -> list[Path]:
    """Render index + all cards to ``out_dir``. Returns written paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    modules = load_corpus()
    written = [out_dir / "index.html"]
    written[0].write_text(index_html(modules))
    for module in modules:
        path = out_dir / f"{module.id}.html"
        path.write_text(card_html(module))
        written.append(path)
    return written
