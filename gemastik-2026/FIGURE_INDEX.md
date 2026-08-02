# Figure Index

Six post-gate screenshots were captured from actual localhost software on 2026-08-03
(Asia/Jakarta). Every committed screenshot uses only reserved `.invalid` fixture data. The ignored
QQ screenshot used for local product QA is not a proposal asset.

| Figure | Content | Source | Asset path | Status |
|---|---|---|---|---|
| 1 | Evidence-first product flow | Repository architecture diagram | `assets/proposal/figure-01-flow.*` | planned — render during final document layout |
| 2 | Four capture dimensions and checkpoints | G4A model/readiness JSON | `assets/technical/figure-02-capture.*` | planned — render during final document layout |
| 3 | Graph-first workspace and screenshot inspector | `demo-harbor` sanitized case | `assets/proposal/figure-03-workspace.png` | implemented |
| 4 | Actual event replay in progress | `run-redirect-new-tab-0f033e69` | `assets/technical/figure-04-timeline.png` | implemented |
| 5 | Page B selected with fixture artifacts/assertion context | `run-redirect-new-tab-0f033e69` | `assets/proposal/figure-05-page-b-assertion.png` | implemented |
| 6 | Dashed candidate relationship before review | `run-redirect-new-tab-0f033e69` | `assets/video/figure-06-before-review.png` | implemented |
| 7 | Emphasized relationship after append-only review | same run, review version 1 | `assets/video/figure-07-after-review.png` | implemented |
| 8 | Stored policy preflight with `executed=false` | `run-login-register-distractors-35fd04ac` | `assets/proposal/figure-08-policy-block.png` | implemented |
| 9 | Three-mode benchmark table | checked-in Markdown/JSON | `assets/proposal/figure-09-benchmark.png` | planned — render during final document layout |
| 10 | Limitations and safety boundaries | technical document | `assets/technical/figure-10-boundaries.*` | planned — render during final document layout |

## Reproduction metadata

All six files use viewport `1280×720`, implementation commit `67a039b3471b`, localhost port `8767`,
deterministic fallback, and the ignored workspace `verification-output/g10-figure-workspace`.

| Asset | Capture time WIB | Bytes | SHA-256 |
|---|---|---:|---|
| `figure-03-workspace.png` | 2026-08-03 06:09:57 | 112,883 | `822f85341a1772e422730e4d0247443aaac17056bfc1dfd85ab0a210ed0d3dee` |
| `figure-04-timeline.png` | 2026-08-03 06:10:04 | 122,045 | `8c4f97f91b0b99bef9f4b635fc22b480b857dc67181e47c203fe7858ab8ab657` |
| `figure-05-page-b-assertion.png` | 2026-08-03 06:10:02 | 146,203 | `2bf79a78076c048c64cca81609c56a014901694a6492cac5d655db50df7b96b1` |
| `figure-06-before-review.png` | 2026-08-03 06:10:00 | 145,977 | `94daa86a04691e29da6a053910c2980e70bfc84f9d7d5425093c076da6aafde5` |
| `figure-07-after-review.png` | 2026-08-03 06:10:06 | 146,057 | `90b83b811106f68d5f1f5c5031b1ca35cd708677606c0dc7c72c8cae933e873d` |
| `figure-08-policy-block.png` | 2026-08-03 06:10:09 | 129,941 | `3e957c8ae94686c879e1528ccd9ec1c82954f3e39c4ee9ef38fc84109ebbc39e` |

Sanitization check: only `harbor.demo.invalid`, `scenario-6.example.invalid`,
`candidate-f.example.invalid`, and `scenario-8.example.invalid` fixture labels are visible. URL
query secrets are rendered as `[redacted]`. No live-site content, credentials, cookies, personal
data, VPN/session details, or fabricated graph content is present.
