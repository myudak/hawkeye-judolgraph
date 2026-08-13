# Backend safety

- Preserve deterministic collection, extraction, provenance, append-only review history, and
  evidence integrity.
- Never crawl generated candidates automatically or bypass authentication, CAPTCHA, geographic
  restrictions, rate limits, or other access controls.
- Model output is advisory and schema-bound; deterministic fallback must remain available.
- Add fixture-backed tests for engine behavior. Live websites are not automated-test truth.
