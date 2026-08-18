"""Generate the three fixed eval datasets for the pandas-styler-tables harness.

Deterministic (hardcoded values, no RNG) so every run grades the same numbers.
Raw CSVs carry *unformatted* floats on purpose — formatting them is the skill's job.

Run:  python make_data.py   ->  writes data/eval_0_revenue.csv, eval_1_yoy.csv, eval_2_matrix.csv
"""
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)


def eval_0_revenue():
    """Exec revenue-by-segment table. Tests currency + integer formatting + caption.

    Magnitudes are in the millions (commas required) and ARPU carries messy
    cents so an unformatted render leaks long decimals.
    """
    segment = ["Residential", "Small Business", "Commercial", "Municipal", "Wholesale"]
    revenue = [12345678.90, 8765432.10, 23456789.55, 4567890.25, 34567890.00]
    customers = [45231, 12043, 3987, 512, 89]
    arpu = [rev / cust for rev, cust in zip(revenue, customers)]  # raw floats, long decimals
    df = pd.DataFrame(
        {"segment": segment, "revenue": revenue, "customers": customers, "arpu": arpu}
    )
    df.to_csv(os.path.join(DATA, "eval_0_revenue.csv"), index=False)


def eval_1_yoy():
    """Year-over-year change by region. Tests diverging-palette-centered-at-zero + percent.

    Values are proportions with mixed signs and a genuine near-zero cell
    (margin_change Mid-Atlantic = 0.001). The data midpoint (~0.041) is far
    from zero, so an *uncentered* gradient puts its neutral color on the wrong
    cell — that is exactly what the grader detects.
    """
    region = ["Northeast", "Midwest", "South", "West", "Mid-Atlantic"]
    rev_growth = [0.083, -0.052, 0.211, -0.128, 0.004]
    margin_change = [-0.015, 0.032, 0.058, -0.091, 0.001]
    churn_change = [0.012, -0.007, -0.034, 0.045, -0.002]
    df = pd.DataFrame(
        {
            "region": region,
            "rev_growth": rev_growth,
            "margin_change": margin_change,
            "churn_change": churn_change,
        }
    ).set_index("region")
    df.to_csv(os.path.join(DATA, "eval_1_yoy.csv"))


def eval_2_matrix():
    """Channel x month conversion-rate matrix. Tests that a gradient/heatmap is applied.

    One obvious hotspot (Referral / Apr = 0.187) and a cold corner
    (Direct Mail / Jan = 0.018) so 'which cells jump out?' has a real answer.
    """
    channels = ["Paid Search", "Email", "Direct Mail", "Referral", "Social", "Organic"]
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    rows = [
        [0.052, 0.061, 0.058, 0.067, 0.071, 0.069],  # Paid Search
        [0.089, 0.092, 0.101, 0.098, 0.110, 0.105],  # Email
        [0.018, 0.021, 0.019, 0.024, 0.022, 0.026],  # Direct Mail
        [0.121, 0.134, 0.152, 0.187, 0.161, 0.149],  # Referral (hotspot Apr)
        [0.043, 0.039, 0.047, 0.051, 0.048, 0.055],  # Social
        [0.077, 0.081, 0.079, 0.084, 0.088, 0.091],  # Organic
    ]
    df = pd.DataFrame(rows, index=channels, columns=months)
    df.index.name = "channel"
    df.to_csv(os.path.join(DATA, "eval_2_matrix.csv"))


def eval_3_empty():
    """A monthly exception report that happens to be empty this period. Tests
    the empty-DataFrame guard: df.style on an empty frame renders a headers-only
    <table> with no rows and no error, so it is easy to ship a blank table by
    mistake. A guard that says 'no data' is the documented skill behavior.
    """
    df = pd.DataFrame(columns=["segment", "margin_pct", "flagged_date"])
    df.to_csv(os.path.join(DATA, "eval_3_empty.csv"), index=False)


if __name__ == "__main__":
    eval_0_revenue()
    eval_1_yoy()
    eval_2_matrix()
    eval_3_empty()
    print("wrote:", sorted(os.listdir(DATA)))
