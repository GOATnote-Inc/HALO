"""Hand-authored 2D schematic SVGs for procedure steps.

These are labeled schematics — memory aids for landmarks and hand positions,
not an anatomy atlas, and every one says so in its caption. Steps reference
them by id via ``Step.media``; the renderer inlines them. A ``model3d:``
media prefix is reserved for future 3D assets (none ship today — no
placeholders pretending otherwise).

Layout contract (learned from a Chrome red-team pass): labels live in clear
margin columns and never overlap the figure; every label fits inside the
viewBox; leader lines are short. The reserved 'serious' red is used ONLY for
cut/action marks and always travels with a text label.
"""

from __future__ import annotations

_INK = "#3a4045"
_MUTED = "#8a939b"
_ACTION = "#b3261e"  # reserved serious color: cuts and needle/injector actions
_SKIN = "#f3e2d3"

_STYLE = f'font-family="system-ui, sans-serif" font-size="11" fill="{_INK}"'


def _svg(view: str, title: str, body: str, caption: str) -> str:
    return (
        f'<svg viewBox="{view}" role="img" aria-label="{title}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f"<title>{title}</title>"
        f"<g {_STYLE}>{body}"
        f'<text x="8" y="98%" font-size="10" fill="{_MUTED}">{caption}</text>'
        "</g></svg>"
    )


CANTHOTOMY = _svg(
    "0 0 460 250",
    "Lateral canthotomy and inferior cantholysis — schematic",
    f"""
    <ellipse cx="150" cy="120" rx="95" ry="48" fill="none" stroke="{_INK}" stroke-width="2"/>
    <circle cx="150" cy="120" r="26" fill="none" stroke="{_INK}" stroke-width="2"/>
    <circle cx="150" cy="120" r="10" fill="{_INK}"/>
    <path d="M 272 84 A 100 100 0 0 1 276 160" fill="none" stroke="{_MUTED}"
      stroke-width="3" stroke-linecap="round"/>
    <text x="306" y="62" fill="{_MUTED}">orbital rim</text>
    <line x1="304" y1="66" x2="280" y2="88" stroke="{_MUTED}" stroke-width="1"/>
    <text x="10" y="26">lateral canthus at the</text>
    <text x="10" y="40">right corner of the eye</text>
    <line x1="120" y1="46" x2="238" y2="114" stroke="{_MUTED}" stroke-width="1"/>
    <line x1="245" y1="120" x2="285" y2="120" stroke="{_ACTION}" stroke-width="3"
      stroke-dasharray="6 4"/>
    <text x="306" y="112" fill="{_ACTION}">1. canthotomy</text>
    <text x="306" y="126" font-size="10" fill="{_ACTION}">~1 cm, canthus to rim</text>
    <line x1="302" y1="116" x2="288" y2="120" stroke="{_MUTED}" stroke-width="1"/>
    <line x1="258" y1="130" x2="282" y2="174" stroke="{_ACTION}" stroke-width="3"
      stroke-dasharray="6 4"/>
    <text x="306" y="168" fill="{_ACTION}">2. INFERIOR CRUS</text>
    <text x="306" y="182" font-size="10" fill="{_ACTION}">strum, then cut —</text>
    <text x="306" y="196" font-size="10" fill="{_ACTION}">the lid must swing free</text>
    <line x1="302" y1="172" x2="284" y2="168" stroke="{_MUTED}" stroke-width="1"/>
    """,
    "Schematic, right eye. Aim inferoposteriorly toward the rim — away from the globe.",
)

PMCS_INCISION = _svg(
    "0 0 360 340",
    "Perimortem cesarean incision — schematic",
    f"""
    <path d="M 130 30 Q 180 12 230 30 L 238 96 Q 268 170 246 250 L 232 292 L 128 292 L 114 250
      Q 92 170 122 96 Z" fill="{_SKIN}" stroke="{_INK}" stroke-width="2"/>
    <circle cx="180" cy="185" r="66" fill="none" stroke="{_INK}" stroke-width="2"/>
    <circle cx="180" cy="178" r="4" fill="{_INK}"/>
    <text x="192" y="176">umbilicus</text>
    <line x1="118" y1="150" x2="242" y2="150" stroke="{_MUTED}" stroke-width="2"
      stroke-dasharray="3 5"/>
    <text x="8" y="196" fill="{_MUTED}">fundus at/above</text>
    <text x="8" y="210" fill="{_MUTED}">umbilicus: GO</text>
    <line x1="84" y1="198" x2="120" y2="154" stroke="{_MUTED}" stroke-width="1"/>
    <line x1="180" y1="96" x2="180" y2="268" stroke="{_ACTION}" stroke-width="3"
      stroke-dasharray="8 5"/>
    <text x="8" y="116" fill="{_ACTION}">vertical midline,</text>
    <text x="8" y="130" fill="{_ACTION}">xiphoid to pubis</text>
    <line x1="96" y1="124" x2="176" y2="140" stroke="{_MUTED}" stroke-width="1"/>
    <text x="154" y="90">xiphoid</text>
    <text x="158" y="286">pubis</text>
    """,
    "Schematic. Uterine incision follows: vertical, finger-guarded.",
)

BREECH_GRIP = _svg(
    "0 0 400 260",
    "Breech grip — bony pelvis only, schematic (view from behind)",
    f"""
    <circle cx="150" cy="46" r="26" fill="{_SKIN}" stroke="{_INK}" stroke-width="2"/>
    <path d="M 124 66 Q 150 78 176 66 L 184 130 Q 186 158 174 168 L 126 168 Q 114 158 116 130 Z"
      fill="{_SKIN}" stroke="{_INK}" stroke-width="2"/>
    <path d="M 126 168 L 116 216 M 174 168 L 184 216" stroke="{_INK}" stroke-width="8"
      stroke-linecap="round" fill="none"/>
    <line x1="150" y1="86" x2="150" y2="146" stroke="{_MUTED}" stroke-width="2"/>
    <ellipse cx="150" cy="152" rx="9" ry="13" fill="none" stroke="{_INK}" stroke-width="2"/>
    <ellipse cx="112" cy="146" rx="14" ry="26" fill="none" stroke="{_INK}" stroke-width="2"
      transform="rotate(-18 112 146)"/>
    <ellipse cx="188" cy="146" rx="14" ry="26" fill="none" stroke="{_INK}" stroke-width="2"
      transform="rotate(18 188 146)"/>
    <path d="M 126 156 Q 140 163 147 154" stroke="{_ACTION}" stroke-width="6" fill="none"
      stroke-linecap="round"/>
    <path d="M 174 156 Q 160 163 153 154" stroke="{_ACTION}" stroke-width="6" fill="none"
      stroke-linecap="round"/>
    <text x="252" y="120" fill="{_ACTION}">BOTH THUMBS</text>
    <text x="252" y="134" fill="{_ACTION}">ON THE SACRUM;</text>
    <text x="252" y="148" fill="{_ACTION}">fingers on the iliac crests</text>
    <line x1="248" y1="130" x2="162" y2="152" stroke="{_MUTED}" stroke-width="1"/>
    <text x="252" y="188" fill="{_MUTED}">never the abdomen</text>
    <text x="252" y="202" fill="{_MUTED}">or flanks (viscera)</text>
    """,
    "Schematic, infant from behind. Bone-on-bone grip; never squeeze soft tissue.",
)

MAURICEAU = _svg(
    "0 0 420 240",
    "Mauriceau-Smellie-Veit — schematic",
    f"""
    <text x="10" y="26" fill="{_MUTED}">body stays HORIZONTAL, straddling the forearm —</text>
    <text x="10" y="40" fill="{_MUTED}">raise it only as the face clears</text>
    <text x="10" y="66">other hand on shoulders/occiput,</text>
    <text x="10" y="80">assistant gives suprapubic pressure</text>
    <line x1="178" y1="84" x2="152" y2="94" stroke="{_MUTED}" stroke-width="1"/>
    <path d="M 20 150 L 210 150 Q 236 150 250 160 L 292 186" stroke="{_SKIN}"
      stroke-width="26" fill="none" stroke-linecap="round"/>
    <path d="M 20 150 L 210 150" stroke="{_INK}" stroke-width="2" fill="none"
      stroke-dasharray="2 6"/>
    <ellipse cx="150" cy="132" rx="62" ry="20" fill="{_SKIN}" stroke="{_INK}" stroke-width="2"/>
    <circle cx="230" cy="140" r="24" fill="{_SKIN}" stroke="{_INK}" stroke-width="2"/>
    <path d="M 96 128 L 74 168 M 116 124 L 102 170" stroke="{_INK}" stroke-width="7"
      stroke-linecap="round"/>
    <path d="M 128 100 Q 150 88 176 96" stroke="{_INK}" stroke-width="4" fill="none"
      stroke-linecap="round"/>
    <path d="M 238 156 Q 248 148 246 136" stroke="{_ACTION}" stroke-width="5" fill="none"
      stroke-linecap="round"/>
    <text x="10" y="216" fill="{_ACTION}">index + middle fingers on the MAXILLA — flex, never pull</text>
    <line x1="252" y1="210" x2="244" y2="160" stroke="{_MUTED}" stroke-width="1"/>
    """,
    "Schematic. Flexion comes from the maxilla and suprapubic pressure — never traction.",
)

AUTOINJECTOR = _svg(
    "0 0 410 300",
    "Nerve-agent autoinjector site — schematic",
    f"""
    <path d="M 96 24 L 148 24 Q 160 120 154 190 L 148 252 L 104 252 Q 92 160 96 110 Z"
      fill="{_SKIN}" stroke="{_INK}" stroke-width="2"/>
    <text x="112" y="272" fill="{_MUTED}">thigh (lateral aspect)</text>
    <rect x="200" y="118" width="16" height="66" rx="4" fill="none" stroke="{_ACTION}"
      stroke-width="3"/>
    <line x1="200" y1="150" x2="162" y2="150" stroke="{_ACTION}" stroke-width="4"/>
    <path d="M 172 144 L 160 150 L 172 156" fill="none" stroke="{_ACTION}" stroke-width="3"/>
    <text x="232" y="112" fill="{_ACTION}">LATERAL thigh,</text>
    <text x="232" y="126" fill="{_ACTION}">firm push, hold 10 s</text>
    <line x1="228" y1="118" x2="218" y2="128" stroke="{_MUTED}" stroke-width="1"/>
    <text x="232" y="220" fill="{_MUTED}">through clothing if needed;</text>
    <text x="232" y="234" fill="{_MUTED}">mild 1 / moderate 2 / severe 3</text>
    """,
    "Schematic. DuoDote = atropine 2.1 mg + pralidoxime 600 mg per injector.",
)

DIAGRAMS: dict[str, str] = {
    "canthotomy": CANTHOTOMY,
    "pmcs_incision": PMCS_INCISION,
    "breech_grip": BREECH_GRIP,
    "mauriceau": MAURICEAU,
    "autoinjector": AUTOINJECTOR,
}


def get_diagram(media_id: str) -> str | None:
    """SVG string for a Step.media id; None when the id names no shipped diagram."""
    return DIAGRAMS.get(media_id)
