# Model Self-Report on LCARS Corrections

Date: 2026-04-04

## Context

During a long discussion session, the model (Claude) was asked whether it was aware of LCARS correction injections and how they affected output. The model confirmed awareness of two corrections in the session (filler, density) and provided feedback.

## Key Observations

### 1. Corrections are parsed semantically, not just behaviorally
The model reports parsing "density: 0.583" as a numeric target and adjusting toward higher density specifically. Precise dimensional corrections are more actionable than categorical ones ("too verbose"). This supports investing in richer correction signals (hybrid scoring dimensions).

### 2. Correction stickiness / oscillation
"After a filler correction I tend to over-compress for a turn or two before recalibrating." At low correction frequency (2 per session) this is benign, but implies:
- Correction fitness may overcount effectiveness (next response looks improved partly due to overcorrection, not equilibrium)
- High-frequency corrections could produce choppy output
- The current amortization (corrections on next user message, not every response) is well-calibrated

### 3. Discussion-mode density is load-bearing
"Some of what LCARS scores as filler may be rhetorical scaffolding that helps the human track the reasoning." The model identifies that connective tissue between ideas is functional in exploratory sessions but would be filler in implementation sessions. This is exactly the query-type-aware threshold problem — and validates the classifier's role in selecting appropriate density targets per mode.

## Design Implications

- Correction templates should include specific dimensions and values, not just categories
- Investigate whether correction fitness tracking accounts for oscillation effects
- The residual ambiguous bucket (29%) absorbing discussion-mode prompts is a real threshold-mismatch source
- Hybrid scoring's richer dimensions (SyA, VDet, EpAd, EPad) would give the model more precise adjustment signals
