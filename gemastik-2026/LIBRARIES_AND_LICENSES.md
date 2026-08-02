# Libraries and Licenses

This list is derived from `pyproject.toml`; it is not a legal opinion. Version ranges are declared
requirements, not proof of the exact environment lock. Exact installed versions and transitive
licenses must be exported and reviewed before submission or redistribution.

| Library/runtime | Declared use | Declared version range | License status |
|---|---|---|---|
| Python | Application runtime | `>=3.12` | TODO — requires human/legal verification of distribution terms |
| beautifulsoup4 | Deterministic HTML parsing | `>=4.12.3` | TODO — verify exact installed package metadata |
| FastAPI | Local API and UI routes | `>=0.115.0` | TODO — verify exact installed package metadata |
| Pillow | Screenshot metrics and crops | `>=10.4.0` | TODO — verify exact installed package metadata |
| Playwright | Bounded Chromium control | `>=1.50.0` | TODO — verify library and bundled browser terms |
| Pydantic | Validated schemas | `>=2.8.2` | TODO — verify exact installed package metadata |
| tldextract | Domain normalization | `>=5.1.3` | TODO — verify exact installed package and suffix-data terms |
| Uvicorn | Local ASGI server | `>=0.32.0` | TODO — verify exact installed package metadata |
| mypy | Development type checker | `>=1.13.0` | Development-only; TODO verify metadata |
| pytest | Automated tests | `>=8.3.3` | Development-only; TODO verify metadata |
| Ruff | Formatter/linter | `>=0.8.0` | Development-only; TODO verify metadata |
| httpx | Development API testing | `>=0.28.0` | Development-only; TODO verify metadata |
| types-beautifulsoup4 | Development typing stubs | declared range | Development-only; TODO verify metadata |
| Chromium | Browser engine installed by Playwright | environment-specific | TODO — verify redistribution and recording environment terms |
| SQLite | Python standard-library persistence backend | runtime-provided | TODO — verify runtime distribution metadata |
| Vanilla JavaScript/CSS/HTML | Local frontend | no package dependency | Project-authored source; originality still requires human declaration |

## Required final license procedure

1. Export exact installed packages and versions from the final environment.
2. Record license identifiers and upstream project URLs from authoritative package metadata.
3. Inspect transitive dependencies and bundled browser assets.
4. Confirm whether source or notice files must accompany the competition package.
5. Have an authorized human approve redistribution and attribution.
6. Do not replace TODO entries with remembered license names without verification.

