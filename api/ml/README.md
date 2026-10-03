# Sachet classifier track

## Data status: PRE-REVIEW

Batch 3 added 154 items (254 -> 408 train pool) plus a **held-out set of
329 items that is never loaded by `load_items`** and therefore cannot reach
training. Batch 1+2 used `stratified_split` on a single pool, so train and
test shared a generator -- exactly the artifact risk `generation_spec.md`
warned about. `dataset.assert_disjoint` fails loudly if that ever regresses.

Held-out set is authored to be *unlike* training: promotion-first and
interleaved ordering (training is always education-then-promotion), wider
length range (median 167 / max 303 vs train 138 / 208), and structures
training never used (forwards with `Forwarded >`, lists, ALL CAPS, emoji,
voice-note markers). Verified 0 items above 85% token Jaccard with any
training item.

## Results

Two columns, because the gap between them is the whole point.

| Model | internal test acc / macro F1 | **HELD-OUT acc / macro F1** | edu FP (held-out) |
|---|---|---|---|
| TF-IDF + LogReg | 0.839 / 0.820 | **0.809 / 0.711** | 0.098 |
| Frozen MuRIL probe | 0.684 / 0.671 (batch 1) | see `ml.evaluate_heldout` | -- |
| LoRA MuRIL (r=16) | 0.767 / 0.568 | **0.775 / 0.575** | 0.000 |

Adding batch 3 moved TF-IDF on held-out from 0.647 -> 0.682 macro F1 (and
0.781 -> 0.796 accuracy). That
is the value of the new data: the bigger pool generalises to a differently
generated test set.

## Honest failure: LoRA collapses on `mixed`

The fine-tune predicts **zero** `mixed` items -- precision and recall both
0.000, at 12 epochs and at 30. This is the third recurrence of a failure this
file already documented ("collapsed to majority class", then "ignored the
mixed class"). It is **not fixed**, and tuning epochs did not fix it.

Diagnosis: `mixed` is the rarest class (59 train examples vs 122 promotion,
105 education) *and* the hardest, because it is the boundary between the other
two. A weak encoder plus r=16 LoRA on ~290 examples does not have the signal
to learn a rare boundary class.

Recommendation: stop asking the model to learn `mixed`. The deterministic
analyzer already computes the persuasion-category count, and `mixed` is
defined as exactly one category. Either let the model predict two classes
(education / promotion) and have the deterministic layer assign `mixed`, or
regress on category count instead of classifying a 3-way label. Both remove
the rare class from the learning problem entirely.

## Two methodology problems found while building this

1. **Relabelling gold from the heuristic is circular.** An intermediate step
   derived `mixed` -> `education` from the analyzer's own output. That makes
   the dataset unable to honestly measure the analyzer, and the model would
   just learn to imitate the regexes. Corrected: gold stays as authored, and
   disagreement is recorded as a finding.
2. **33 of 86 new promotion items are under-detected** by the analyzer
   (`<2` persuasion categories). Gold stays `promotion`. These are real
   coverage gaps and are the most useful thing in this batch -- they are why
   the analyzer's own held-out agreement is 73.9%, against 94.1% on the
   original corpus.

## Analyzer on the held-out set

| gold \ predicted | education | mixed | promotion | out_of_scope |
|---|---|---|---|---|
| education | 113 | 13 | 3 | 14 |
| mixed | 29 | 27 | 6 | 4 |
| promotion | 3 | 14 | 103 | 0 |

Agreement 243/329 = **73.9%**, versus 94.1% on the original corpus. The
drop is expected and honest: this set is deliberately harder and written to a
different distribution. `mixed` remains the weak row in both directions.

## How to run

```
.venv/bin/python -m ml.finetune              # LoRA, trains on train split only
.venv/bin/python -m ml.evaluate_heldout      # scores test + HELD-OUT
.venv/bin/python -m ml.evaluate_heldout --only tfidf
SACHET_MODEL=off .venv/bin/python -m ml.train_baseline   # keeps tests fast
```
