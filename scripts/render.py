#!/usr/bin/env python3
"""Render the profile's SVGs (dark + light) from data.json and sync README numbers.

    python3 scripts/render.py            # re-render from data.json
    python3 scripts/render.py --fetch    # pull the Codeforces rating first

Fails closed: if the Codeforces API errors or returns something odd, the old
rating stays and nothing is rewritten for it.
"""
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data.json"
ASSETS = ROOT / "assets"
README = ROOT / "README.md"

W = 880
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"

# GitHub's own palettes, so the panels sit naturally on github.com.
THEMES = {
    "dark": dict(
        bg="#0d1117", panel="#010409", bar="#161b22", border="#30363d",
        fg="#e6edf3", muted="#8b949e", faint="#6e7681",
        blue="#58a6ff", green="#7ee787", orange="#ffa657", purple="#d2a8ff", red="#ff7b72",
        seg=[("#1f6feb", "#ffffff"), ("#388bfd", "#0d1117"), ("#f0883e", "#0d1117"), ("#a5d6ff", "#0d1117")],
        hatch=("#161b22", "#262c36"),
    ),
    "light": dict(
        bg="#ffffff", panel="#f6f8fa", bar="#eaeef2", border="#d0d7de",
        fg="#1f2328", muted="#59636e", faint="#6e7781",
        blue="#0969da", green="#1a7f37", orange="#bc4c00", purple="#8250df", red="#cf222e",
        seg=[("#0969da", "#ffffff"), ("#54aeff", "#1f2328"), ("#fb8f44", "#1f2328"), ("#b6e3ff", "#1f2328")],
        hatch=("#f6f8fa", "#e1e6eb"),
    ),
}

STYLE = """<style>
  .m{font-family:%(mono)s} .s{font-family:%(sans)s}
  .cur{animation:blink 1.1s steps(1) infinite}
  .in{animation:fade .5s ease-out both}
  @keyframes blink{50%%{opacity:0}}
  @keyframes fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
  @media (prefers-reduced-motion: reduce){.cur,.in{animation:none}}
</style>""" % {"mono": MONO, "sans": SANS}


def t(x, y, s, fill, size=14, cls="m", weight=None, anchor=None, extra=""):
    w = f' font-weight="{weight}"' if weight else ""
    a = f' text-anchor="{anchor}"' if anchor else ""
    return f'<text x="{x}" y="{y}" class="{cls}" font-size="{size}" fill="{fill}"{w}{a}{extra}>{s}</text>'


def window(c, h, title, body, label):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" aria-label="{escape(label, {chr(34): '&quot;'})}">
<title>{escape(label)}</title>
{STYLE}
<rect x="0.5" y="0.5" width="{W-1}" height="{h-1}" rx="10" fill="{c['bg']}" stroke="{c['border']}"/>
<path d="M0.5 36 V10.5 a10 10 0 0 1 10 -10 H{W-10.5} a10 10 0 0 1 10 10 V36 Z" fill="{c['bar']}"/>
<line x1="0.5" y1="36" x2="{W-0.5}" y2="36" stroke="{c['border']}"/>
<circle cx="22" cy="18" r="6" fill="#ff5f57"/><circle cx="42" cy="18" r="6" fill="#febc2e"/><circle cx="62" cy="18" r="6" fill="#28c840"/>
{t(W/2, 23, escape(title), c['muted'], 12, anchor="middle")}
{body}
</svg>
"""


def prompt(c, y, cmd):
    return t(40, y, f'<tspan fill="{c["green"]}">❯</tspan> <tspan fill="{c["fg"]}">{escape(cmd)}</tspan>', c["fg"], 15)


def header(d, c):
    out = []
    out.append(prompt(c, 72, "whoami"))
    out.append(t(40, 120, escape(d["name"]), c["fg"], 36, cls="s", weight="700"))
    out.append(t(40, 150, f'<tspan fill="{c["blue"]}">{escape(d["login"])}</tspan>  ·  {escape(d["school"])}', c["muted"], 15, cls="s"))
    out.append(t(40, 180, escape(d["tagline"]), c["fg"], 16, cls="s"))

    out.append(prompt(c, 232, "pahole -C devillish404 ./me"))
    out.append(t(40, 262, f'<tspan fill="{c["red"]}">struct</tspan> <tspan fill="{c["purple"]}">alignas</tspan>(64) <tspan fill="{c["fg"]}" font-weight="700">devillish404</tspan> {{'
                 f'  <tspan fill="{c["faint"]}">/* size: 64, cachelines: 1 */</tspan>', c["muted"], 14))

    # one cache line, 64 bytes, 12.5 px per byte
    x0, bw, top, hgt = 40, 12.5, 296, 58
    for off in (0, 16, 32, 48, 64):
        anchor = "end" if off == 64 else ("start" if off == 0 else "middle")
        out.append(t(x0 + off * bw, top - 8, f"0x{off:02x}", c["faint"], 11, anchor=anchor))
    segs = [(0, 16, "identity", "char[16]"), (16, 32, "shipped", "project[4]"),
            (32, 36, "cf", "u32"), (36, 48, "learning", "topic[2]")]
    for i, (a, b, name, typ) in enumerate(segs):
        fill, ink = c["seg"][i]
        x, w = x0 + a * bw, (b - a) * bw
        out.append(f'<g class="in" style="animation-delay:{0.15 * i:.2f}s">'
                   f'<rect x="{x}" y="{top}" width="{w}" height="{hgt}" fill="{fill}"/>'
                   + t(x + 8, top + 22, name, ink, 12, weight="700")
                   + t(x + 8, top + 44, typ, ink, 11) + "</g>")
    px = x0 + 48 * bw
    out.append(f'<g class="in" style="animation-delay:0.6s"><rect x="{px}" y="{top}" width="{16 * bw}" height="{hgt}" fill="url(#hatch)"/>'
               + t(px + 10, top + 22, "__pad", c["fg"], 12, weight="700")
               + t(px + 10, top + 44, "404: not found yet", c["muted"], 11) + "</g>")
    out.append(f'<rect x="{x0}" y="{top}" width="{64 * bw}" height="{hgt}" fill="none" stroke="{c["border"]}" rx="3"/>')
    for a in (16, 32, 36, 48):
        out.append(f'<line x1="{x0 + a * bw}" y1="{top}" x2="{x0 + a * bw}" y2="{top + hgt}" stroke="{c["bg"]}" stroke-width="1.5"/>')

    cf = d["cf"]
    rows = [
        ("char", "identity[16];", "0", "16", c["blue"], f'"{d["name"]}"'),
        ("project_t", "shipped[4];", "16", "16", c["blue"], "paypilot, bosm, code_duel, entity_res"),
        ("uint32_t", "cf_rating;", "32", "4", c["orange"], f'{cf["rating"]}  // {cf["rank"]}, auto-updated'),
        ("topic_t", "learning[2];", "36", "12", c["blue"], "low_level_cpp, transformers"),
        ("char", "__pad[16];", "48", "16", c["muted"], "reserved: order_book_engine"),
    ]
    y = 392
    for typ, name, off, size, col, val in rows:
        out.append(t(64, y, f'<tspan fill="{c["red"]}">{typ}</tspan>', c["fg"], 13))
        out.append(t(168, y, escape(name), c["fg"], 13))
        out.append(t(312, y, f"/* {off:>2} {size:>2} */".replace(" ", " "), c["faint"], 13))
        out.append(t(430, y, escape(val), col, 13))
        y += 24
    out.append(t(40, y + 2, "};", c["muted"], 14))
    out.append(t(40, y + 28, "/* sum members: 48, holes: 0, padding: 16 */", c["faint"], 13))
    out.append(prompt(c, y + 70, ""))
    out.append(f'<rect class="cur" x="58" y="{y + 57}" width="9" height="17" fill="{c["fg"]}"/>')
    h = y + 96
    defs = (f'<defs><pattern id="hatch" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
            f'<rect width="10" height="10" fill="{c["hatch"][0]}"/><rect width="5" height="10" fill="{c["hatch"][1]}"/></pattern></defs>')
    label = (f'Terminal: whoami prints {d["name"]}, {d["school"]}. "{d["tagline"]}" '
             f'Then pahole shows a 64-byte struct devillish404: identity, four shipped projects, '
             f'Codeforces rating {cf["rating"]}, two learning topics, and 16 bytes of padding reserved for an order book engine that is not built yet.')
    return window(c, h, "devillish404@bits-pilani: ~ — bash", defs + "\n".join(out), label)


def audit(d, c):
    cf = d["cf"]
    state_col = {"EXECUTED": c["green"], "RECONCILED": c["blue"], "PENDING": c["orange"]}
    out = [prompt(c, 72, "devillish404 audit verify --all")]
    out.append(t(40, 110, "ITEM", c["faint"], 12))
    out.append(t(200, 110, "STATE", c["faint"], 12))
    out.append(t(340, 110, "EVIDENCE", c["faint"], 12))
    out.append(f'<line x1="40" y1="120" x2="{W-40}" y2="120" stroke="{c["border"]}"/>')
    y = 146
    counts = {}
    for i, r in enumerate(d["audit"]):
        ev = r["evidence"].format(cf_rating=cf["rating"], cf_rank=cf["rank"])
        counts[r["state"]] = counts.get(r["state"], 0) + 1
        out.append(f'<g class="in" style="animation-delay:{0.08 * i:.2f}s">'
                   + t(40, y, escape(r["item"]), c["fg"], 14)
                   + t(200, y, r["state"], state_col.get(r["state"], c["fg"]), 14, weight="700")
                   + t(340, y, escape(ev), c["muted"], 14) + "</g>")
        y += 28
    out.append(f'<line x1="40" y1="{y - 10}" x2="{W-40}" y2="{y - 10}" stroke="{c["border"]}"/>')
    ex, pe = counts.get("EXECUTED", 0), counts.get("PENDING", 0)
    out.append(t(40, y + 18, f'<tspan fill="{c["green"]}">✓</tspan> {ex} executed · {pe} pending · books balance · '
                 f'<tspan fill="{c["fg"]}" font-weight="700">0 claims without evidence</tspan>', c["muted"], 14))
    h = y + 46
    label = "Audit table. " + "; ".join(
        f'{r["item"]}: {r["state"]}, {r["evidence"].format(cf_rating=cf["rating"], cf_rank=cf["rank"])}' for r in d["audit"]
    ) + ". Summary: 0 claims without evidence."
    return window(c, h, "audit — paypilot-style verify", "\n".join(out), label)


def footer(d, c):
    body = (prompt(c, 72, "exit")
            + t(40, 100, f'logout · numbers verified {d["verified"]} by .github/workflows/refresh.yml', c["muted"], 13)
            + t(40, 128, f'<tspan fill="{c["faint"]}">[process completed · exit 0 · next commit: </tspan><tspan fill="{c["orange"]}">404</tspan><tspan fill="{c["faint"]}">]</tspan>', c["faint"], 13)
            + f'<rect class="cur" x="40" y="142" width="9" height="17" fill="{c["fg"]}"/>')
    return window(c, 176, "devillish404@bits-pilani: ~ — bash", body,
                  f'Terminal session ends: logout, numbers verified {d["verified"]}.')


def fetch_cf(d):
    url = f'https://codeforces.com/api/user.info?handles={d["cf"]["handle"]}'
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "profile-readme-refresh"})
        with urllib.request.urlopen(req, timeout=20) as r:
            res = json.load(r)
        if res.get("status") != "OK":
            raise ValueError("status not OK")
        u = res["result"][0]
        rating, rank = int(u["rating"]), str(u["rank"])
        if not (0 < rating < 5000) or not re.fullmatch(r"[a-z ]+", rank):
            raise ValueError("unexpected payload")
    except Exception as e:  # fail closed: keep what we had
        print(f"codeforces fetch failed, keeping {d['cf']['rating']}: {e}", file=sys.stderr)
        return False
    d["cf"]["rating"], d["cf"]["rank"] = rating, rank
    d["verified"] = datetime.now(timezone.utc).date().isoformat()
    return True


def sync_readme(d):
    if not README.exists():
        return
    s = README.read_text(encoding="utf-8")
    cf = d["cf"]
    s = re.sub(rf'({re.escape(cf["handle"])} · )\d+( · )[a-z ]+', rf'\g<1>{cf["rating"]}\g<2>{cf["rank"]}', s)
    README.write_text(s, encoding="utf-8")


def main():
    d = json.loads(DATA.read_text(encoding="utf-8"))
    if "--fetch" in sys.argv and fetch_cf(d):
        DATA.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ASSETS.mkdir(exist_ok=True)
    for mode, c in THEMES.items():
        for name, fn in (("header", header), ("audit", audit), ("footer", footer)):
            (ASSETS / f"{name}-{mode}.svg").write_text(fn(d, c), encoding="utf-8")
    sync_readme(d)


if __name__ == "__main__":
    main()
