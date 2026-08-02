# Figure Index

Six post-gate screenshots were captured from actual localhost software on 2026-08-03
(Asia/Jakarta). Every committed screenshot uses only reserved `.invalid` fixture data. The ignored
QQ screenshot used for local product QA is not a proposal asset.

| Figure | Content | Source | Asset path | Status |
|---|---|---|---|---|
| 1 | Evidence-first product flow | Repository architecture diagram | `assets/proposal/figure-01-flow.*` | planned — render during final document layout |
| 2 | Four capture dimensions and checkpoints | G4A model/readiness JSON | `assets/technical/figure-02-capture.*` | planned — render during final document layout |
| 3 | Graph-first workspace and screenshot inspector | `demo-harbor` sanitized case | `assets/proposal/figure-03-workspace.png` | implemented |
| 4 | Actual event replay in progress | `run-redirect-new-tab-df8d392d` | `assets/technical/figure-04-timeline.png` | implemented |
| 5 | Page B selected with fixture artifacts/assertion context | `run-redirect-new-tab-df8d392d` | `assets/proposal/figure-05-page-b-assertion.png` | implemented |
| 6 | Dashed candidate relationship before review | `run-redirect-new-tab-df8d392d` | `assets/video/figure-06-before-review.png` | implemented |
| 7 | Emphasized relationship after append-only review | same run, review version 1 | `assets/video/figure-07-after-review.png` | implemented |
| 8 | Stored policy preflight with `executed=false` | `run-login-register-distractors-16d80d30` | `assets/proposal/figure-08-policy-block.png` | implemented |
| 9 | Three-mode benchmark table | checked-in Markdown/JSON | `assets/proposal/figure-09-benchmark.png` | planned — render during final document layout |
| 10 | Limitations and safety boundaries | technical document | `assets/technical/figure-10-boundaries.*` | planned — render during final document layout |

## Reproduction metadata

All six files use viewport `1280×720`, commit `445079ce41b1`, localhost port `8766`, deterministic
fallback, and the ignored workspace `verification-output/g4-g9/ui-demo-final/workspace`.

| Asset | Capture time WIB | Bytes | SHA-256 |
|---|---|---:|---|
| `figure-03-workspace.png` | 2026-08-03 04:40:34 | 96,851 | `3c309ba5c43be521e26e9acff3c6d5cc46d8acfc5ad1726bbd307a308b9ad753` |
| `figure-04-timeline.png` | 2026-08-03 04:40:42 | 80,478 | `8e1525b1fc104fd4b40acb2160da9450661c2d8a354f0cd6ea56eed7136acfcf` |
| `figure-05-page-b-assertion.png` | 2026-08-03 04:40:38 | 89,965 | `b9001046af4e4b20b93f24c8815b0b790f741dfa570d0db542ba47e2ff11b27a` |
| `figure-06-before-review.png` | 2026-08-03 04:40:37 | 88,627 | `0e7c31eb3a9d14bf965726fde31c436b5c7b6fec7a1c7dec0a7ea7c1cf96f26f` |
| `figure-07-after-review.png` | 2026-08-03 04:41:01 | 84,528 | `3e006cce06088dced2cdeac948156d4aac5859d0fb7fe65efad6daf78fd36b1b` |
| `figure-08-policy-block.png` | 2026-08-03 04:41:25 | 81,794 | `e4a8631dd8ae8326c160de52c052a2758293236309924540f7163891cb9d862d` |

Sanitization check: only `harbor.demo.invalid`, `scenario-6.example.invalid`,
`candidate-f.example.invalid`, and `scenario-8.example.invalid` fixture labels are visible. URL
query secrets are rendered as `[redacted]`. No live-site content, credentials, cookies, personal
data, VPN/session details, or fabricated graph content is present.
