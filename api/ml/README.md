# Sachet classifier track

## Data status: PRE-REVIEW

All numbers below are on 254 synthetic **candidate** items (owner review
pending). Re-run everything after the gold review; expect numbers to move.

## How to run

```
.venv/bin/python -m ml.train_baseline          # TF-IDF word+char + LogReg
.venv/bin/python -m ml.probe                   # frozen MuRIL + LogReg
.venv/bin/python -m ml.finetune                # LoRA on MuRIL (needs GPU)
.venv/bin/python -m ml.finetune --model xlm-roberta-base   # fallback encoder
```

Splits are stratified 70/15/15, seed 42, shared by all three scripts.

## Results (test, n=38)

| Model | Acc | Macro F1 | FP on education |
|---|---|---|---|
| TF-IDF + LogReg (baseline) | 0.789 | 0.779 | 1/14 (0.071) |
| Frozen MuRIL probe | 0.684 | 0.671 | 4/14 (0.286) |
| LoRA MuRIL (r=16, lr 3e-4, 30ep, ls 0.1) | **0.921** | **0.917** | **0/14 (0.000)** |

Confusion (LoRA/test, rows=true edu/mix/pro): 14/0/0, 1/10/0, 0/2/11.

## Honest caveats (for the submission)

- The val split hit 100%: with template-generated candidates, the model
  may be keying on generation artifacts. Gold review + fresh phrasing in
  batch 2 halves this risk; re-run on gold before quoting numbers.
- n=38 test is small; report confidence intervals or cross-seed variance
  before the deadline.
- Two failed attempts are documented in git history, not hidden: plain
  LoRA collapsed to majority class (fix: balanced class weights), then
  ignored the mixed class (fix: higher LR, r=16, label smoothing).
- The heuristic baseline in ../analyzer.py stays the demo engine: it is
  explainable per-claim, while the classifier gives one opaque label.
  Recommended product shape: heuristic decides, classifier shadow-scores.
