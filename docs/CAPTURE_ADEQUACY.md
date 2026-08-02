# Capture Adequacy (G4A)

Canonical collection measures four fixed checkpoints at 0, 500, 1,500, and 3,000 ms after
`domcontentloaded`. It performs no click, scroll, consent dismissal, form submission, download, or
`networkidle` wait. The final checkpoint is canonical; the initial screenshot is retained only when
its hash differs.

The persisted dimensions are independent:

- `navigation_status`: captured, failed, timed_out, or blocked_by_policy;
- `access_outcome`: content, access_challenge, geo_restriction, consent_wall, unavailable, or
  unknown_restriction;
- `capture_adequacy`: adequate, limited, or failed;
- `extraction_eligible`: true only for captured content with adequate capture and canonical HTML
  at most 2,000,000 UTF-8 bytes.

The browser-visible text source is `document.body.innerText`, never BeautifulSoup text. Each
checkpoint records browser/collector/policy versions, response metadata, DOM and visible-element
counts, document dimensions, screenshot dimensions/hash/bytes, normalized grayscale entropy, and
the ratio of 64-pixel tiles whose intensity range is at least 12.

A final adjacent delta is material when HTML changes by at least 32 bytes, visible text by at least
4 characters, visible elements by at least one, document height by at least 8 pixels, or viewport
pixels change. Continued material change produces `rendering_changed_at_budget_end`. A textless,
linkless, image/iframe/canvas-free final viewport with informative-tile ratio below 0.01 is limited
as `low_information_capture`.

Canonical HTML is persisted through 5,000,000 bytes. From 2–5 MB it is preserved but automatic
extraction is skipped with `direct_extractor_input_exceeds_2_mb`. Above 5 MB its byte count and
SHA-256 remain in readiness evidence while HTML persistence is omitted; visible text, screenshots,
response metadata, redirects, and readiness remain. Full-page capture is bounded at 12,000 pixels
high and records truncation. Oversize HTML is never converted into a navigation failure.

Legacy fields remain optional and old case JSON continues to parse through the existing loader.

