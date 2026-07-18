"""Hand-authored 2D schematic SVGs for procedure steps.

These are labeled schematics — memory aids for landmarks and hand positions,
not an anatomy atlas, and every one says so in its caption. Steps reference
them by id via ``Step.media``; the renderer inlines them. A ``model3d:``
media prefix is reserved for future 3D assets (none ship today — no
placeholders pretending otherwise).

Palette: ink strokes on the card surface; the reserved 'serious' red is used
ONLY for cut/action lines and always travels with a text label.
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
    "0 0 340 220",
    "Lateral canthotomy and inferior cantholysis — schematic",
    f"""
    <ellipse cx="140" cy="95" rx="95" ry="48" fill="none" stroke="{_INK}" stroke-width="2"/>
    <circle cx="140" cy="95" r="26" fill="none" stroke="{_INK}" stroke-width="2"/>
    <circle cx="140" cy="95" r="10" fill="{_INK}"/>
    <path d="M 258 60 A 95 95 0 0 1 262 140" fill="none" stroke="{_MUTED}"
      stroke-width="3" stroke-linecap="round"/>
    <text x="252" y="50" fill="{_MUTED}">orbital rim</text>
    <line x1="235" y1="95" x2="272" y2="95" stroke="{_ACTION}" stroke-width="3"
      stroke-dasharray="6 4"/>
    <text x="180" y="30" fill="{_ACTION}">1. canthotomy — ~1 cm cut, canthus to rim</text>
    <line x1="216" y1="36" x2="250" y2="88" stroke="{_MUTED}" stroke-width="1"/>
    <line x1="248" y1="102" x2="268" y2="146" stroke="{_ACTION}" stroke-width="3"
      stroke-dasharray="6 4"/>
    <text x="150" y="192" fill="{_ACTION}">2. INFERIOR CRUS — strum, then cut; lid must swing free</text>
    <line x1="262" y1="134" x2="240" y2="184" stroke="{_MUTED}" stroke-width="1"/>
    <text x="12" y="30">lateral canthus at the</text>
    <text x="12" y="44">right corner of the eye</text>
    <line x1="96" y1="48" x2="228" y2="90" stroke="{_MUTED}" stroke-width="1"/>
    """,
    "Schematic, right eye. Scissors aim inferoposteriorly toward the rim — away from the globe.",
)

PMCS_INCISION = _svg(
    "0 0 240 320",
    "Perimortem cesarean incision — schematic",
    f"""
    <path d="M 70 30 Q 120 12 170 30 L 178 96 Q 208 170 186 250 L 172 292 L 68 292 L 54 250
      Q 32 170 62 96 Z" fill="{_SKIN}" stroke="{_INK}" stroke-width="2"/>
    <circle cx="120" cy="185" r="66" fill="none" stroke="{_INK}" stroke-width="2"/>
    <circle cx="120" cy="178" r="4" fill="{_INK}"/>
    <text x="132" y="176">umbilicus</text>
    <line x1="58" y1="150" x2="182" y2="150" stroke="{_MUTED}" stroke-width="2"
      stroke-dasharray="3 5"/>
    <text x="12" y="142" fill="{_MUTED}">fundus at/above</text>
    <text x="12" y="156" fill="{_MUTED}">umbilicus: GO</text>
    <line x1="120" y1="96" x2="120" y2="268" stroke="{_ACTION}" stroke-width="3"
      stroke-dasharray="8 5"/>
    <text x="128" y="110" fill="{_ACTION}">vertical midline,</text>
    <text x="128" y="124" fill="{_ACTION}">xiphoid to pubis</text>
    <text x="94" y="90">xiphoid</text>
    <text x="98" y="286">pubis</text>
    """,
    "Schematic. Vertical midline through all layers; then vertical uterine incision from the fundus over a two-finger guard.",
)

BREECH_GRIP = _svg(
    "0 0 300 250",
    "Breech grip — bony pelvis only, schematic (view from behind)",
    f"""
    <circle cx="150" cy="46" r="26" fill="{_SKIN}" stroke="{_INK}" stroke-width="2"/>
    <path d="M 124 66 Q 150 78 176 66 L 184 130 Q 186 158 174 168 L 126 168 Q 114 158 116 130 Z"
      fill="{_SKIN}" stroke="{_INK}" stroke-width="2"/>
    <path d="M 126 168 L 116 216 M 174 168 L 184 216" stroke="{_INK}" stroke-width="8"
      stroke-linecap="round" fill="none"/>
    <line x1="150" y1="86" x2="150" y2="150" stroke="{_MUTED}" stroke-width="2"/>
    <ellipse cx="150" cy="150" rx="8" ry="12" fill="none" stroke="{_INK}" stroke-width="2"/>
    <text x="164" y="150">sacrum</text>
    <ellipse cx="112" cy="146" rx="14" ry="26" fill="none" stroke="{_INK}" stroke-width="2"
      transform="rotate(-18 112 146)"/>
    <ellipse cx="188" cy="146" rx="14" ry="26" fill="none" stroke="{_INK}" stroke-width="2"
      transform="rotate(18 188 146)"/>
    <path d="M 128 154 Q 142 160 148 152" stroke="{_ACTION}" stroke-width="4" fill="none"
      stroke-linecap="round"/>
    <path d="M 172 154 Q 158 160 152 152" stroke="{_ACTION}" stroke-width="4" fill="none"
      stroke-linecap="round"/>
    <text x="12" y="196" fill="{_ACTION}">BOTH THUMBS ON THE SACRUM,</text>
    <text x="12" y="210" fill="{_ACTION}">fingers on the iliac crests</text>
    <line x1="96" y1="188" x2="140" y2="158" stroke="{_MUTED}" stroke-width="1"/>
    <text x="196" y="110" fill="{_MUTED}">never the abdomen</text>
    <text x="196" y="124" fill="{_MUTED}">or flanks (viscera)</text>
    """,
    "Schematic, infant seen from behind. Grip is bone-on-bone; soft tissue is never squeezed.",
)

MAURICEAU = _svg(
    "0 0 340 230",
    "Mauriceau-Smellie-Veit — schematic",
    f"""
    <path d="M 20 150 L 210 150 Q 236 150 250 160 L 292 186" stroke="{_SKIN}"
      stroke-width="26" fill="none" stroke-linecap="round"/>
    <path d="M 20 150 L 210 150" stroke="{_INK}" stroke-width="2" fill="none"
      stroke-dasharray="2 6"/>
    <path d="M 90 132 Q 140 118 190 128 L 214 134" stroke="{_INK}" stroke-width="2"
      fill="none"/>
    <ellipse cx="150" cy="132" rx="62" ry="20" fill="{_SKIN}" stroke="{_INK}" stroke-width="2"/>
    <circle cx="230" cy="140" r="24" fill="{_SKIN}" stroke="{_INK}" stroke-width="2"/>
    <path d="M 96 128 L 74 168 M 116 124 L 102 170" stroke="{_INK}" stroke-width="7"
      stroke-linecap="round"/>
    <path d="M 238 156 Q 246 148 244 138" stroke="{_ACTION}" stroke-width="4" fill="none"
      stroke-linecap="round"/>
    <text x="150" y="200" fill="{_ACTION}">index + middle fingers on the MAXILLA — flex, never pull</text>
    <line x1="244" y1="152" x2="236" y2="192" stroke="{_MUTED}" stroke-width="1"/>
    <path d="M 128 96 Q 150 84 176 92" stroke="{_INK}" stroke-width="4" fill="none"
      stroke-linecap="round"/>
    <text x="60" y="72">other hand on shoulders/occiput,</text>
    <text x="60" y="86">assistant gives suprapubic pressure</text>
    <line x1="150" y1="90" x2="150" y2="96" stroke="{_MUTED}" stroke-width="1"/>
    <text x="18" y="30" fill="{_MUTED}">body stays HORIZONTAL, straddling the forearm —</text>
    <text x="18" y="44" fill="{_MUTED}">raise it only as the face clears</text>
    """,
    "Schematic. Flexion comes from the maxilla and suprapubic pressure — never traction or hyperextension.",
)

AUTOINJECTOR = _svg(
    "0 0 240 280",
    "Nerve-agent autoinjector site — schematic",
    f"""
    <path d="M 96 24 L 148 24 Q 160 120 154 190 L 148 252 L 104 252 Q 92 160 96 110 Z"
      fill="{_SKIN}" stroke="{_INK}" stroke-width="2"/>
    <text x="104" y="272">thigh</text>
    <rect x="176" y="118" width="16" height="66" rx="4" fill="none" stroke="{_ACTION}"
      stroke-width="3"/>
    <line x1="176" y1="150" x2="158" y2="150" stroke="{_ACTION}" stroke-width="4"/>
    <path d="M 166 144 L 156 150 L 166 156" fill="none" stroke="{_ACTION}" stroke-width="3"/>
    <text x="24" y="60" fill="{_ACTION}">LATERAL thigh, firm push,</text>
    <text x="24" y="74" fill="{_ACTION}">hold 10 seconds</text>
    <line x1="96" y1="68" x2="158" y2="140" stroke="{_MUTED}" stroke-width="1"/>
    <text x="24" y="228" fill="{_MUTED}">through clothing if needed;</text>
    <text x="24" y="242" fill="{_MUTED}">mild 1 / moderate 2 / severe 3</text>
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
