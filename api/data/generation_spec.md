# Sachet dataset generation spec (v1, Oct 2026)

Gold set goal: 200+ hand-reviewed items for training eval + classifier
training. Batch 1 = 124 synthetic candidates (education/mixed/promotion
JSONL). Batch 2 = 130 more (education2: 20 synthetic on fresh topics +
30 official-derived paraphrases of SEBI/AMFI/RBI educational material;
mixed2/promotion2: fresh trap topics). Total 254. Status: batch 1
owner-approved with no corrections; full gold review still pending.

## Label definitions (must match api/analyzer.py rubric v1.1)

- education: explains a concept or process. No sales pressure, no promises,
  no unverifiable authority. Carries (or clearly implies) risk awareness.
- mixed: genuine explanatory content plus 1-2 promotional signals
  (typically paid_service_cta, social_proof, or urgency_pressure).
- promotion: built to sell or recruit. 2+ flags, or any return promise
  combined with a CTA.

## Hard negatives (required, ~20% of education)

Education items that MENTION returns, profit, or risk words but stay
educational through framing + disclosure. These are what stop the
classifier from over-flagging. Example shape: "Equity funds have
delivered ~12% long-term on average, but returns vary yearly and capital
is at risk. This is educational, not advice."

## Constraints (every item)

1. 20-600 chars, 1-4 sentences. Looks like a reel caption, forward, or
   voice-note transcript.
2. Synthetic only. No real creator names, handles, or group names. No real
   client anecdotes. Paid groups are always generic ("my premium group").
3. Every listed flag must be evidenced in the text. Education items list [].
   missing_disclosure is never item-labeled: it is computed doc-level by
   the analyzer (risky content with no disclaimer), so expect it uncovered
   in item-level flag coverage.
4. Languages: en (English), hi (Devanagari Hindi), hinglish (Latin-script
   Hindi/English mix). Target split ~40/30/30.
5. No two items may share the same underlying template; vary openers,
   topics (mutual funds, SIP, options, insurance, crypto, budgeting,
   pensions, taxes, IPOs), and closers.
6. Promotion items must read like real traps, not cartoons: specific
   numbers, deadlines, insider language, screenshot-proof.
7. Review contract: a reviewer sets "review" to accept/edit/reject and, for
   edits, writes the corrected text in "review_text". Only accept + edited
   items enter the gold set. Batch 1 needs 100% review (124 items).

## Schema (JSONL, one object per line)

{"id": "edu-0001", "lang": "en", "label": "education",
 "flags": [], "text": "...", "source": "synthetic-v1"}
