# Dijkstra Assessment: NL Skill Routing (#24)

Date: 2026-04-03

## Verdict

The NL router design should not be implemented. The routing function is underspecified (designer cannot determine correct target at design time), misrouting costs are asymmetric (wrong skill consumes context budget on irrelevant output), and the router either requires inference (violating deterministic-first) or regex patterns (which is just worse slash commands with latent cognitive load instead of visible).

## Key Arguments

1. **Preconditions for correct routing cannot be stated precisely.** "Are my corrections working?" maps to either calibrate or dashboard. If the designer can't determine the target at design time, the router can't at runtime.

2. **Skill preconditions differ and are exclusive.** deep-eval needs a scoreable response, fmea needs a failure event, foundry needs staged proposals. A correct router would need to verify system state, not just parse language.

3. **The 8 skills are not a problem.** The target user has already accepted concepts like overfit gates and FMEA RPNs. Remembering 8 unambiguous command names is negligible overhead. Count is within Miller's 7+/-2.

4. **Misrouting cost > memorization cost.** A correct route saves remembering a name. A misroute wastes context window tokens and requires diagnosing why the system did the wrong thing — exactly the extraneous cognitive load LCARS exists to eliminate.

## Constructive Alternative

A single `/lcars` help screen showing commands grouped by cluster:

```
Observe:    /lcars:dashboard  /lcars:discover  /lcars:deep-eval  /lcars:fmea  /lcars:setup
Tune:       /lcars:calibrate  /lcars:consolidate
Strategize: /lcars:foundry
```

3 lines, ~30 tokens. Complete, unambiguous, no inference.
