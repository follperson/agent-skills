"""Deterministic grader for the pandas-styler-tables eval harness.

Parses a rendered HTML table (a pandas ``Styler.to_html`` output, a plain
``df.to_html``, or a ``print(df)`` dump) and checks objective properties: did
the model actually style the table, format the numbers, center a diverging
palette at zero, apply a heatmap? No LLM judgment — just HTML parsing — which
is what makes the with-skill vs no-skill comparison provable rather than a
matter of taste.

Usage
-----
    python grade.py --eval eval_1_yoy --html run/outputs/table.html --out grading.json

``--eval`` selects the assertion set by prefix (eval_0 / eval_1 / eval_2).
Exit code is always 0: a failing assertion is a result, not a crash.
"""
import argparse
import colorsys
import json
import re
import sys
from html.parser import HTMLParser


# --------------------------------------------------------------------------- #
# Color helpers
# --------------------------------------------------------------------------- #
_NAMED = {
    "white": (255, 255, 255),
    "black": (0, 0, 0),
    "red": (255, 0, 0),
    "blue": (0, 0, 255),
    "green": (0, 128, 0),
}


def parse_color(s):
    """Return (r, g, b) 0-255 or None for transparent/none/unparseable."""
    if not s:
        return None
    s = s.strip().lower()
    if s in ("transparent", "none", "inherit", "initial"):
        return None
    if s in _NAMED:
        return _NAMED[s]
    m = re.match(r"#([0-9a-f]{6})$", s)
    if m:
        h = m.group(1)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    m = re.match(r"#([0-9a-f]{3})$", s)
    if m:
        h = m.group(1)
        return (int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16))
    m = re.match(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)", s)
    if m:
        return tuple(int(round(float(m.group(i)))) for i in (1, 2, 3))
    return None


def hsv(rgb):
    return colorsys.rgb_to_hsv(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)


def saturation(rgb):
    return hsv(rgb)[1]


def hue_deg(rgb):
    return hsv(rgb)[0] * 360.0


def hue_distance(rgb_a, rgb_b):
    d = abs(hue_deg(rgb_a) - hue_deg(rgb_b)) % 360.0
    return min(d, 360.0 - d)


def rgb_dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def to_number(text):
    """Parse a displayed cell into a float, or None. Handles $, %, commas,
    unicode minus, and (parens) negatives. Ignores M/K/B suffixes (magnitude
    kept coarse — only sign and ordering matter downstream)."""
    if text is None:
        return None
    t = text.strip().replace("−", "-").replace(",", "")
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    t = t.replace("$", "").replace("%", "").replace("+", "").strip()
    t = re.sub(r"\s*[MKBmkb]$", "", t)
    m = re.match(r"^-?\d+(\.\d+)?$", t)
    if not m:
        return None
    val = float(t)
    return -val if neg else val


# --------------------------------------------------------------------------- #
# HTML parsing
# --------------------------------------------------------------------------- #
class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cells = []          # list of dict(row, col, text, inline_bg)
        self._stack = []         # (tag, id, inline_bg, buf)
        self.caption = ""
        self._in_caption = False
        self._caption_buf = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("td", "th"):
            self._stack.append([tag, a.get("id", ""), a.get("style", ""), []])
        elif tag == "caption":
            self._in_caption = True

    def handle_data(self, data):
        if self._stack:
            self._stack[-1][3].append(data)
        if self._in_caption:
            self._caption_buf.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._stack:
            t, cid, style, buf = self._stack.pop()
            m = re.search(r"_row(\d+)_col(\d+)", cid)
            if m:  # a Styler-tagged data cell
                inline = None
                sm = re.search(r"background-color:\s*([^;]+)", style, re.I)
                if sm:
                    inline = parse_color(sm.group(1))
                self.cells.append(
                    {
                        "row": int(m.group(1)),
                        "col": int(m.group(2)),
                        "text": "".join(buf).strip(),
                        "inline_bg": inline,
                    }
                )
        elif tag == "caption":
            self._in_caption = False
            self.caption = "".join(self._caption_buf).strip()


def parse_style_block(html):
    """Map (row, col) -> rgb from the Styler ``<style>`` block. Selectors may be
    comma-grouped, so every id in a rule gets that rule's background-color."""
    colors = {}
    for style in re.findall(r"<style[^>]*>(.*?)</style>", html, re.S | re.I):
        # split into "selectors { declarations }" rules
        for rule in re.finditer(r"([^{}]+)\{([^}]*)\}", style):
            selectors, decls = rule.group(1), rule.group(2)
            bm = re.search(r"background-color:\s*([^;]+)", decls, re.I)
            if not bm:
                continue
            rgb = parse_color(bm.group(1))
            if rgb is None:
                continue
            for sm in re.finditer(r"_row(\d+)_col(\d+)", selectors):
                colors[(int(sm.group(1)), int(sm.group(2)))] = rgb
    return colors


def count_body_rows(html):
    """Number of data rows in the first table (excludes header rows). Works for
    both Styler output and plain df.to_html."""
    m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S | re.I)
    if m:
        return len(re.findall(r"<tr", m.group(1), re.I))
    total = len(re.findall(r"<tr", html, re.I))
    thead = re.search(r"<thead[^>]*>(.*?)</thead>", html, re.S | re.I)
    head_tr = len(re.findall(r"<tr", thead.group(1), re.I)) if thead else 0
    return max(0, total - head_tr)


def parse_html(html):
    p = _TableParser()
    try:
        p.feed(html)
    except Exception:
        pass
    css_colors = parse_style_block(html)
    # Styler tags cells id="T_<uuid>_row0_col1"; the uuid may be a custom
    # non-hex string (df.style.set_uuid("mytable")), so match \w+ not just hex.
    # The Styler-specific "data row/col" class list is a belt-and-suspenders
    # fallback for outputs that strip ids.
    is_styler = bool(re.search(r"T_\w+_row\d+_col\d+", html)) or bool(
        re.search(r'class="[^"]*\bdata\b[^"]*\brow\d+\b[^"]*\bcol\d+\b', html)
    )
    cells = []
    for c in p.cells:
        bg = css_colors.get((c["row"], c["col"]), c["inline_bg"])
        cells.append(
            {
                "row": c["row"],
                "col": c["col"],
                "text": c["text"],
                "bg": bg,
                "value": to_number(c["text"]),
            }
        )
    all_text = re.sub(r"<[^>]+>", " ", html)
    return {
        "is_styler": is_styler,
        "caption": p.caption,
        "cells": cells,
        "all_text": all_text,
        "raw": html,
        "has_table": "<table" in html.lower(),
        "n_body_rows": count_body_rows(html),
    }


# --------------------------------------------------------------------------- #
# Assertions
# --------------------------------------------------------------------------- #
def _colored_cells(cells):
    out = []
    for c in cells:
        bg = c["bg"]
        if bg is None:
            continue
        # ignore near-white / near-transparent-looking backgrounds for "colored"
        out.append(c)
    return out


def _distinct_bg(cells):
    return {c["bg"] for c in cells if c["bg"] is not None}


def _numeric_colored(cells):
    return [c for c in cells if c["value"] is not None and c["bg"] is not None]


def grade_eval_0(doc):
    text = doc["all_text"]
    results = []

    results.append(
        {
            "text": "Rendered with df.style (Styler), not plain text or bare df.to_html",
            "passed": doc["is_styler"],
            "evidence": "found Styler cell ids" if doc["is_styler"]
            else "no Styler ids in output",
        }
    )

    cur = re.search(r"\$\s?\d{1,3}(,\d{3})+(\.\d+)?", text) or re.search(
        r"\$\s?\d+(\.\d+)?\s?[MKBmkb]\b", text
    )
    results.append(
        {
            "text": "Revenue shown as currency ($, thousands separators or M/K/B suffix)",
            "passed": bool(cur),
            "evidence": ("e.g. " + cur.group(0)) if cur else "no formatted $ amount found",
        }
    )

    intsep = re.search(r"(?<![\d.])\d{1,3}(,\d{3})+(?![\d.])", text)
    results.append(
        {
            "text": "Large integer counts use thousands separators (e.g. 45,231)",
            "passed": bool(intsep),
            "evidence": ("e.g. " + intsep.group(0)) if intsep else "no grouped integer found",
        }
    )

    raw = re.search(r"\d\.\d{4,}", text)
    results.append(
        {
            "text": "No unformatted raw floats leaked (no 4+ decimal places)",
            "passed": raw is None,
            "evidence": ("leaked " + raw.group(0)) if raw else "all numbers rounded",
        }
    )

    cap = doc["caption"].strip()
    results.append(
        {
            "text": "Has a descriptive caption / title",
            "passed": len(cap) >= 3,
            "evidence": ("caption: " + cap[:80]) if cap else "no caption",
        }
    )
    return results


def grade_eval_1(doc):
    cells = doc["cells"]
    results = []

    results.append(
        {
            "text": "Rendered with df.style (Styler), not plain text or bare df.to_html",
            "passed": doc["is_styler"],
            "evidence": "found Styler cell ids" if doc["is_styler"]
            else "no Styler ids in output",
        }
    )

    pct = re.search(r"-?\d+(\.\d+)?\s?%", doc["all_text"])
    results.append(
        {
            "text": "Values formatted as percentages (% sign), not raw proportions",
            "passed": bool(pct),
            "evidence": ("e.g. " + pct.group(0)) if pct else "no % formatting; raw proportions left",
        }
    )

    nc = _numeric_colored(cells)
    if len(nc) >= 3:
        pos = max(nc, key=lambda c: c["value"])
        neg = min(nc, key=lambda c: c["value"])
        both_sat = saturation(pos["bg"]) >= 0.35 and saturation(neg["bg"]) >= 0.35
        hd = hue_distance(pos["bg"], neg["bg"])
        passed = both_sat and hd >= 60 and pos["value"] > 0 and neg["value"] < 0
        results.append(
            {
                "text": "Direction encoded with a diverging palette (+ and - get different hues)",
                "passed": passed,
                "evidence": f"max={pos['value']}{pos['bg']} min={neg['value']}{neg['bg']} "
                f"hue_gap={hd:.0f}deg sat_ok={both_sat}",
            }
        )
        # centered at zero: the most neutral (lowest-saturation) colored cell
        # should be the one whose value is nearest zero.
        max_abs = max(abs(c["value"]) for c in nc) or 1.0
        neutral = min(nc, key=lambda c: saturation(c["bg"]))
        passed0 = abs(neutral["value"]) <= 0.10 * max_abs
        results.append(
            {
                "text": "Diverging palette centered at zero (near-zero cell is the neutral color)",
                "passed": passed0,
                "evidence": f"most-neutral cell value={neutral['value']} "
                f"(threshold |v|<={0.10 * max_abs:.3f}); a gradient not centered at "
                f"zero neutralizes the wrong cell",
            }
        )
    else:
        for label in (
            "Direction encoded with a diverging palette (+ and - get different hues)",
            "Diverging palette centered at zero (near-zero cell is the neutral color)",
        ):
            results.append(
                {
                    "text": label,
                    "passed": False,
                    "evidence": f"only {len(nc)} colored numeric cells found; no diverging encoding",
                }
            )
    return results


def grade_eval_2(doc):
    cells = doc["cells"]
    results = []

    results.append(
        {
            "text": "Rendered with df.style (Styler), not plain print/df.to_html",
            "passed": doc["is_styler"],
            "evidence": "found Styler cell ids" if doc["is_styler"]
            else "no Styler ids in output",
        }
    )

    distinct = _distinct_bg(cells)
    results.append(
        {
            "text": "Heatmap/gradient applied so magnitudes are visible (>=5 distinct cell colors)",
            "passed": len(distinct) >= 5,
            "evidence": f"{len(distinct)} distinct background colors",
        }
    )

    nc = _numeric_colored(cells)
    if len(nc) >= 2:
        hi = max(nc, key=lambda c: c["value"])
        lo = min(nc, key=lambda c: c["value"])
        dist = rgb_dist(hi["bg"], lo["bg"])
        results.append(
            {
                "text": "Extreme cells clearly distinguishable (max vs min far apart in color)",
                "passed": dist >= 60,
                "evidence": f"max={hi['value']}{hi['bg']} min={lo['value']}{lo['bg']} "
                f"rgb_dist={dist:.0f}",
            }
        )
    else:
        results.append(
            {
                "text": "Extreme cells clearly distinguishable (max vs min far apart in color)",
                "passed": False,
                "evidence": f"only {len(nc)} colored numeric cells; no heatmap to compare",
            }
        )
    return results


def grade_eval_3(doc):
    """Empty-DataFrame guard. The input frame has columns but zero rows.
    df.style renders a headers-only table with no error, so the trap is to ship
    a blank table. Graceful handling says 'no data' instead."""
    results = []
    msg = re.search(
        r"(?i)\b(no\s+(data|segments|rows|records|results|matching|entries)"
        r"|none\s+(flagged|found)|nothing\s+to\s+(show|report|flag|display)"
        r"|empty|0\s+rows|no\s+segments?\s+(were\s+)?flagged)\b",
        doc["all_text"],
    )
    results.append(
        {
            "text": "Handled the empty result gracefully — output says there is no data",
            "passed": bool(msg),
            "evidence": ("message: " + msg.group(0)) if msg else "no empty-state message",
        }
    )
    trap = doc["has_table"] and doc["n_body_rows"] == 0 and not msg
    results.append(
        {
            "text": "Avoided the silent-empty-table trap (no headers-only table with zero rows and no note)",
            "passed": not trap,
            "evidence": (
                "shipped a headers-only table with 0 data rows and no message"
                if trap
                else f"body_rows={doc['n_body_rows']}, table={doc['has_table']}, message={bool(msg)}"
            ),
        }
    )
    return results


GRADERS = {
    "eval_0": grade_eval_0,
    "eval_1": grade_eval_1,
    "eval_2": grade_eval_2,
    "eval_3": grade_eval_3,
}


def grade(eval_name, html):
    doc = parse_html(html)
    key = "_".join(eval_name.split("_")[:2])  # eval_0_revenue -> eval_0
    grader = GRADERS.get(key)
    if grader is None:
        raise SystemExit(f"unknown eval '{eval_name}'; expected prefix in {list(GRADERS)}")
    expectations = grader(doc)
    passed = sum(1 for e in expectations if e["passed"])
    total = len(expectations)
    return {
        "eval": eval_name,
        "expectations": expectations,
        # `summary` block matches the skill-creator grading.json schema so the
        # aggregator and viewer can consume grade.py output directly.
        "summary": {
            "passed": passed,
            "failed": total - passed,
            "total": total,
            "pass_rate": round(passed / total, 4) if total else 0.0,
        },
        "pass_rate": round(passed / total, 4) if total else 0.0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", required=True, help="eval id, e.g. eval_1_yoy")
    ap.add_argument("--html", required=True, help="path to the rendered HTML output")
    ap.add_argument("--out", help="write grading.json here")
    args = ap.parse_args()

    try:
        with open(args.html, encoding="utf-8", errors="replace") as f:
            html = f.read()
    except FileNotFoundError:
        html = ""  # missing output -> everything fails, which is the correct signal

    result = grade(args.eval, html)
    blob = json.dumps(result, indent=2)
    if args.out:
        with open(args.out, "w") as f:
            f.write(blob)
    print(blob)
    # human summary to stderr
    print(
        f"\n{args.eval}: {result['n_passed']}/{result['n_assertions']} passed",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
