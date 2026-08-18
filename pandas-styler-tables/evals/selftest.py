"""Validate grade.py itself: a hand-built GOOD table must score high and a
naive BAD table must score low. If this ever fails, trust nothing the grader
says about real runs. Doubles as a reference for what "passing" looks like.

Run:  python selftest.py    (exit 0 = grader behaves correctly)
"""
import os

import pandas as pd

import grade as G

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")


def _score(eval_name, html):
    r = G.grade(eval_name, html)
    return r["pass_rate"], r


# --------------------------------------------------------------------------- #
# eval_0: revenue currency table
# --------------------------------------------------------------------------- #
def good_0():
    df = pd.read_csv(os.path.join(DATA, "eval_0_revenue.csv")).set_index("segment")
    return (
        df.style.format({"revenue": "${:,.2f}", "arpu": "${:,.2f}", "customers": "{:,d}"})
        .background_gradient(cmap="Greens", subset=["revenue"])
        .set_caption("FY revenue by customer segment")
        .to_html(doctype_html=True)
    )


def bad_0():
    df = pd.read_csv(os.path.join(DATA, "eval_0_revenue.csv"))
    return df.to_html()  # raw floats, no $, no caption, no styling


# --------------------------------------------------------------------------- #
# eval_1: YoY diverging table
# --------------------------------------------------------------------------- #
def good_1():
    df = pd.read_csv(os.path.join(DATA, "eval_1_yoy.csv")).set_index("region")
    vmax = df.abs().max().max()
    return (
        df.style.format("{:.1%}")
        .background_gradient(cmap="RdBu_r", vmin=-vmax, vmax=vmax, axis=None)
        .to_html(doctype_html=True)
    )


def bad_1_uncentered():
    df = pd.read_csv(os.path.join(DATA, "eval_1_yoy.csv")).set_index("region")
    # naive: no percent format, gradient NOT centered at zero
    return df.style.background_gradient(cmap="RdBu_r", axis=None).to_html(doctype_html=True)


def bad_1_sequential():
    df = pd.read_csv(os.path.join(DATA, "eval_1_yoy.csv")).set_index("region")
    return df.style.background_gradient(cmap="Blues", axis=None).to_html(doctype_html=True)


def good_1_signed_customuuid():
    """Regression: signed percents (+21.1%) and a custom Styler uuid must still
    grade as a proper diverging table (past grader bugs mis-parsed both)."""
    df = pd.read_csv(os.path.join(DATA, "eval_1_yoy.csv")).set_index("region")
    vmax = df.abs().max().max()
    return (
        df.style.format("{:+.1%}")
        .background_gradient(cmap="RdBu_r", vmin=-vmax, vmax=vmax, axis=None)
        .set_uuid("customtable")
        .to_html(doctype_html=True)
    )


# --------------------------------------------------------------------------- #
# eval_2: heatmap matrix
# --------------------------------------------------------------------------- #
def good_2():
    df = pd.read_csv(os.path.join(DATA, "eval_2_matrix.csv")).set_index("channel")
    return df.style.background_gradient(cmap="Greens", axis=None).to_html(doctype_html=True)


def bad_2():
    df = pd.read_csv(os.path.join(DATA, "eval_2_matrix.csv"))
    return df.to_html()  # no gradient


# --------------------------------------------------------------------------- #
# eval_3: empty-DataFrame guard
# --------------------------------------------------------------------------- #
def good_3():
    return ("<html><body><p>No segments were flagged for margin review "
            "this month.</p></body></html>")


def bad_3():
    df = pd.read_csv(os.path.join(DATA, "eval_3_empty.csv"))
    return df.style.set_caption("Flagged segments").to_html(doctype_html=True)


def main():
    checks = [
        ("eval_0_revenue", "GOOD", good_0(), lambda r: r >= 0.9),
        ("eval_0_revenue", "BAD", bad_0(), lambda r: r <= 0.3),
        ("eval_1_yoy", "GOOD", good_1(), lambda r: r >= 0.9),
        ("eval_1_yoy", "BAD-uncentered", bad_1_uncentered(), lambda r: r <= 0.5),
        ("eval_1_yoy", "BAD-sequential", bad_1_sequential(), lambda r: r <= 0.5),
        ("eval_1_yoy", "GOOD-signed+uuid", good_1_signed_customuuid(), lambda r: r >= 0.9),
        ("eval_2_matrix", "GOOD", good_2(), lambda r: r >= 0.9),
        ("eval_2_matrix", "BAD", bad_2(), lambda r: r <= 0.5),
        ("eval_3_empty", "GOOD", good_3(), lambda r: r >= 0.9),
        ("eval_3_empty", "BAD", bad_3(), lambda r: r <= 0.1),
    ]
    ok = True
    for eval_name, tag, html, want in checks:
        rate, r = _score(eval_name, html)
        good = want(rate)
        ok = ok and good
        flag = "ok " if good else "FAIL"
        print(f"[{flag}] {eval_name:16s} {tag:16s} pass_rate={rate:.2f}")
        if not good:
            for e in r["expectations"]:
                print(f"        {'P' if e['passed'] else 'x'} {e['text']}")
                print(f"          -> {e['evidence']}")
    print("\nSELFTEST", "PASSED" if ok else "FAILED")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
