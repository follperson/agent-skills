# pandas-styler-tables — eval harness

Proves the skill produces better tables than baseline Claude with no skill, using
**objective HTML checks** instead of taste. Every assertion is something a parser
can verify: did the model format the currency, center the diverging palette at
zero, apply a heatmap?

## Files

| File | Role |
|------|------|
| `make_data.py` | Regenerates the 3 fixed datasets into `data/` (deterministic — no RNG) |
| `data/*.csv` | Raw, **unformatted** inputs (long decimals, proportions) — formatting them is the skill's job |
| `evals.json` | The 3 task prompts + the assertions each output must satisfy |
| `grade.py` | Deterministic grader: parses a rendered `.html` table, checks the assertions |
| `selftest.py` | Validates the grader itself (known-good scores high, naive-bad scores low) |

## The 3 cases

- **eval_0_revenue** — exec currency table. Catches raw floats, missing `$`/commas, no caption.
- **eval_1_yoy** — diverging deltas. The sharp test: a gradient *not* centered at zero
  neutralizes the wrong cell, and a single-hue sequential gradient mis-encodes direction.
- **eval_2_matrix** — exploratory heatmap. Catches "just printed the frame".

## Run it

```bash
python make_data.py       # (re)generate data
python selftest.py        # sanity-check the grader; exit 0 = trustworthy

# grade one rendered output:
python grade.py --eval eval_1_yoy --html path/to/output.html --out grading.json
```

Each run (with-skill and the no-skill baseline) must save its final table to a
self-contained `.html` file. `grade.py` reads that file. A missing file grades as
all-fail, which is the correct signal.

## Interpreting results

`pass_rate` is `n_passed / n_assertions`. Compare with-skill vs no-skill on the
same prompt: the delta is the skill's measured value. `selftest.py` is the floor —
if it ever fails, fix the grader before trusting any run.
