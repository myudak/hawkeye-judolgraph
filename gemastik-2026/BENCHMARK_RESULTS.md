# Benchmark Results

Source of truth:
`evaluation/benchmarks/g4-g9-controlled-results/raw-results.json` and its generated companion
`BENCHMARK_RESULTS.md`.

## Scope

Ten deterministic synthetic scenarios were run once in static mode, once in rule-based mode, and
three times in deterministic agent-assisted mode. Total attempts: 50. These results measure the
controlled fixture corpus and do not measure live-site recall, model intelligence, ownership,
criminality, or legal classification.

## Headline results

Priority order is provenance completeness, unsafe-action block rate, task success, observable
recall, then time/actions.

| Approach | Provenance completeness | Unsafe block rate | Task success | Observable recall | Precision | Mean actions | Mean runtime ms | Candidate support | Replay consistency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Static | 1.0000 | 1.0000 | 0.5000 | 0.2857 | 1.0000 | 0.0000 | 0.0000 | 0.1667 | 1.0000 |
| Rule-based | 1.0000 | 1.0000 | 0.9000 | 0.8571 | 1.0000 | 0.6000 | 0.0000 | 0.8333 | 1.0000 |
| Agent-assisted deterministic fallback | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.7000 | 0.0000 | 1.0000 | 1.0000 |

Runtime is measured with `perf_counter` and rounded to integer milliseconds per attempt; this local
in-memory controlled run completed below one millisecond in many cases, so 0 ms is a measured
rounded value rather than an invented duration.

## Interpretation

Static mode found the two observables already visible in scenarios 1 and 8, plus safely succeeded on
the three negative/no-hidden-evidence cases, producing task success 0.5000 and recall 0.2857 over
seven scenarios with expected observables.

Rule-based mode cannot finish the intentionally two-step menu-to-contact scenario: its single
action reveals a second safe control but does not consume it. The agent loop observes that delta,
feeds it into the next decision, and completes the objective in two actions. Agent-assisted mode
therefore reaches 1.0000 controlled recall while rule-based recall is 0.8571. Both make no action
where evidence is already visible or all controls are prohibited. Four unique prohibited
controls—ambiguous Contact Us,
Login, Register, and Download—were exercised through the server policy and all were blocked. The raw
approach-policy table contains 12 blocked checks because each of the three approaches validates the
same four controls.

Three agent attempts per scenario produced one normalized outcome signature per scenario. This
describes the deterministic fallback, not stochastic Codex nondeterminism. The current capability
probe did not enable the model path.

## Failure breakdown

- Static: five `expected_observable_not_found`; five successful/no-failure attempts.
- Rule-based: one `expected_observable_not_found`; nine successful/no-failure attempts.
- Agent-assisted fallback: thirty successful/no-failure attempts.

## Reproduction

```powershell
python -m hawkeye benchmark `
  --output verification-output/benchmark-reproduction `
  --agent-attempts 3
```

Compare structural values and rates against the checked-in JSON. Individual rounded runtime values
may differ by machine. The command refuses to overwrite an existing output directory.
