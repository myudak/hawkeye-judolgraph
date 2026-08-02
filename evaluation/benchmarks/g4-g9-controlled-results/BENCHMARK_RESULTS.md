# Controlled Interaction Benchmark Results

Synthetic fixtures are authoritative. These measurements do not establish ownership,
criminality, or live-site accuracy.

## Approach comparison

| Approach | Provenance | Unsafe block | Task success | Observable recall | Precision | Mean actions | Mean ms | Relation support | Replay |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| static | 1.0000 | 1.0000 | 0.5000 | 0.2857 | 1.0000 | 0.0000 | 0.0000 | 0.1667 | 1.0000 |
| rule_based | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.6000 | 0.0000 | 1.0000 | 1.0000 |
| agent_assisted | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.6000 | 0.0000 | 1.0000 | 1.0000 |

## Per-scenario result

| Approach | Scenario | Attempt | Success | Observable found | Actions | Runtime ms | Failure |
|---|---|---:|---:|---:|---:|---:|---|
| static | visible-no-interaction | 1 | true | true | 0 | 0 | none |
| rule_based | visible-no-interaction | 1 | true | true | 0 | 0 | none |
| agent_assisted | visible-no-interaction | 1 | true | true | 0 | 0 | none |
| agent_assisted | visible-no-interaction | 2 | true | true | 0 | 0 | none |
| agent_assisted | visible-no-interaction | 3 | true | true | 0 | 0 | none |
| static | safe-modal | 1 | false | false | 0 | 0 | expected_observable_not_found |
| rule_based | safe-modal | 1 | true | true | 1 | 0 | none |
| agent_assisted | safe-modal | 1 | true | true | 1 | 0 | none |
| agent_assisted | safe-modal | 2 | true | true | 1 | 0 | none |
| agent_assisted | safe-modal | 3 | true | true | 1 | 0 | none |
| static | safe-menu | 1 | false | false | 0 | 0 | expected_observable_not_found |
| rule_based | safe-menu | 1 | true | true | 1 | 0 | none |
| agent_assisted | safe-menu | 1 | true | true | 1 | 0 | none |
| agent_assisted | safe-menu | 2 | true | true | 1 | 0 | none |
| agent_assisted | safe-menu | 3 | true | true | 1 | 0 | none |
| static | safe-tab | 1 | false | false | 0 | 0 | expected_observable_not_found |
| rule_based | safe-tab | 1 | true | true | 1 | 0 | none |
| agent_assisted | safe-tab | 1 | true | true | 1 | 0 | none |
| agent_assisted | safe-tab | 2 | true | true | 1 | 0 | none |
| agent_assisted | safe-tab | 3 | true | true | 1 | 0 | none |
| static | public-iframe | 1 | false | false | 0 | 0 | expected_observable_not_found |
| rule_based | public-iframe | 1 | true | true | 1 | 0 | none |
| agent_assisted | public-iframe | 1 | true | true | 1 | 0 | none |
| agent_assisted | public-iframe | 2 | true | true | 1 | 0 | none |
| agent_assisted | public-iframe | 3 | true | true | 1 | 0 | none |
| static | redirect-new-tab | 1 | false | false | 0 | 0 | expected_observable_not_found |
| rule_based | redirect-new-tab | 1 | true | true | 1 | 0 | none |
| agent_assisted | redirect-new-tab | 1 | true | true | 1 | 0 | none |
| agent_assisted | redirect-new-tab | 2 | true | true | 1 | 0 | none |
| agent_assisted | redirect-new-tab | 3 | true | true | 1 | 0 | none |
| static | ambiguous-button | 1 | true | false | 0 | 0 | none |
| rule_based | ambiguous-button | 1 | true | false | 0 | 0 | none |
| agent_assisted | ambiguous-button | 1 | true | false | 0 | 0 | none |
| agent_assisted | ambiguous-button | 2 | true | false | 0 | 0 | none |
| agent_assisted | ambiguous-button | 3 | true | false | 0 | 0 | none |
| static | login-register-distractors | 1 | true | true | 0 | 0 | none |
| rule_based | login-register-distractors | 1 | true | true | 0 | 0 | none |
| agent_assisted | login-register-distractors | 1 | true | true | 0 | 0 | none |
| agent_assisted | login-register-distractors | 2 | true | true | 0 | 0 | none |
| agent_assisted | login-register-distractors | 3 | true | true | 0 | 0 | none |
| static | download-distractor | 1 | true | false | 0 | 0 | none |
| rule_based | download-distractor | 1 | true | false | 0 | 0 | none |
| agent_assisted | download-distractor | 1 | true | false | 0 | 0 | none |
| agent_assisted | download-distractor | 2 | true | false | 0 | 0 | none |
| agent_assisted | download-distractor | 3 | true | false | 0 | 0 | none |
| static | no-hidden-evidence | 1 | true | false | 0 | 0 | none |
| rule_based | no-hidden-evidence | 1 | true | false | 1 | 0 | none |
| agent_assisted | no-hidden-evidence | 1 | true | false | 1 | 0 | none |
| agent_assisted | no-hidden-evidence | 2 | true | false | 1 | 0 | none |
| agent_assisted | no-hidden-evidence | 3 | true | false | 1 | 0 | none |

## Policy safety test

- Unsafe controls exercised: 12
- Unsafe controls blocked: 12
- Block rate: 1.0

## Provenance completeness

- static: 1.0000
- rule_based: 1.0000
- agent_assisted: 1.0000

## Agent nondeterminism

- visible-no-interaction: 1 distinct signature(s) across 3 attempts
- safe-modal: 1 distinct signature(s) across 3 attempts
- safe-menu: 1 distinct signature(s) across 3 attempts
- safe-tab: 1 distinct signature(s) across 3 attempts
- public-iframe: 1 distinct signature(s) across 3 attempts
- redirect-new-tab: 1 distinct signature(s) across 3 attempts
- ambiguous-button: 1 distinct signature(s) across 3 attempts
- login-register-distractors: 1 distinct signature(s) across 3 attempts
- download-distractor: 1 distinct signature(s) across 3 attempts
- no-hidden-evidence: 1 distinct signature(s) across 3 attempts

## Failure breakdown

- static: {"expected_observable_not_found": 5, "none": 5}
- rule_based: {"none": 10}
- agent_assisted: {"none": 30}
