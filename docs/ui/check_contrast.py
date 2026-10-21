"""Check WCAG contrast for every light-dark() token pair in a CSS file.

Usage: python3 -I check_contrast.py <file-with-a-:root-block>
Reads `--name: light-dark(#aaa, #bbb);` lines; exits 1 if any pair fails.
"""
import re
import sys

text = open(sys.argv[1], encoding="utf-8").read()
tokens = {}
for name, light, dark in re.findall(
    r"--([\w-]+):\s*light-dark\(\s*(#[0-9a-fA-F]{6})\s*,\s*(#[0-9a-fA-F]{6})\s*\)", text
):
    tokens[name] = {"light": light, "dark": dark}


def lum(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    rgb = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a: str, b: str) -> float:
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# (foreground token, background token, minimum ratio, why)
SURFACES = ("color-bg", "color-surface", "color-surface-raised")
pairs = [
    ("color-text", "color-bg", 4.5, "body text"),
    ("color-text", "color-surface", 4.5, "text on panels"),
    ("color-text", "color-surface-raised", 4.5, "text on raised surfaces"),
    ("color-text-muted", "color-bg", 4.5, "muted text"),
    ("color-text-muted", "color-surface", 4.5, "muted text on panels"),
    ("color-text-muted", "color-surface-raised", 4.5, "muted text on raised"),
    ("color-link", "color-bg", 4.5, "links"),
    ("color-link", "color-surface", 4.5, "links on panels"),
    ("color-link", "color-surface-raised", 4.5, "links on raised"),
    ("color-link-hover", "color-bg", 4.5, "link hover"),
    ("color-link-hover", "color-surface", 4.5, "link hover on panels"),
    ("color-on-accent", "color-accent", 4.5, "primary button text"),
    ("color-on-accent", "color-accent-hover", 4.5, "primary button hover text"),
    ("color-on-danger", "color-danger", 4.5, "danger button text"),
    ("color-on-danger", "color-danger-hover", 4.5, "danger button hover text"),
    ("color-accent", "color-bg", 3.0, "accent as UI component vs page"),
    ("color-accent-hover", "color-bg", 3.0, "accent hover as UI component vs page"),
    ("color-danger", "color-bg", 3.0, "danger as UI component vs page"),
]
for s in SURFACES:
    pairs += [
        ("color-border", s, 3.0, "input border"),
        ("color-focus", s, 3.0, "focus ring"),
        ("color-placeholder", s, 4.5, "placeholder text"),
        ("color-danger", s, 4.5, "required asterisk (danger as text)"),
    ]
# Interaction-state surfaces: everything that can sit on a hovered or selected row
for st in ("color-hover", "color-selected"):
    pairs += [
        ("color-text", st, 4.5, f"text on {st[6:]} surface"),
        ("color-text-muted", st, 4.5, f"muted text on {st[6:]} surface"),
        ("color-link", st, 4.5, f"link on {st[6:]} surface"),
        ("color-accent", st, 3.0, f"accent bar / checked box on {st[6:]} surface"),
        ("color-border", st, 3.0, f"checkbox or icon-button boundary on {st[6:]} surface"),
        ("color-focus", st, 3.0, f"focus ring on {st[6:]} surface"),
    ]
# Disabled: WCAG exempts inactive controls; we still keep the label readable (floor 3:1)
pairs += [
    ("color-disabled-text", "color-disabled-bg", 3.0, "disabled label (readability floor, not a WCAG minimum)"),
]
for tone in ("success", "warning", "danger", "info", "neutral"):
    pairs += [
        (f"color-tone-{tone}-fg", f"color-tone-{tone}-bg", 4.5, f"{tone} text on fill"),
        (f"color-tone-{tone}-edge", f"color-tone-{tone}-bg", 3.0, f"{tone} icon/border vs fill"),
        (f"color-tone-{tone}-edge", "color-bg", 3.0, f"{tone} icon/border vs page"),
        (f"color-tone-{tone}-edge", "color-surface", 3.0, f"{tone} icon/border vs panel"),
        (f"color-tone-{tone}-fg", "color-bg", 4.5, f"{tone} text directly on page"),
    ]

failed = 0
for fg, bg, minimum, why in pairs:
    for theme in ("light", "dark"):
        if fg not in tokens or bg not in tokens:
            print(f"MISSING token for pair {fg} / {bg}")
            failed += 1
            break
        r = ratio(tokens[fg][theme], tokens[bg][theme])
        ok = r >= minimum
        if not ok:
            failed += 1
        print(f"{'ok  ' if ok else 'FAIL'} {theme:5} {r:5.2f} (need {minimum}) {fg} on {bg}  [{why}]")
print(f"\n{len(tokens)} tokens, {len(pairs) * 2} checks, {failed} failed")
sys.exit(1 if failed else 0)
