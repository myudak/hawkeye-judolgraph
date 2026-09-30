from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "apps/web/src/demo"
ASSETS = OUTPUT / "assets"
AT = "2026-09-01T09:00:00Z"
LIMIT = "Authored synthetic example. No live collection, model inference, or ownership claim."
STYLE = """
body { margin: 0; background: #eef2f5; color: #182e3f; font: 18px Arial, sans-serif; }
header { background: #163a45; color: white; padding: 28px 70px; }
header strong { font-size: 25px; } header span { float: right; color: #b2d9d4; }
main { max-width: 1000px; margin: 45px auto; }
h1 { font-size: 48px; margin: 15px 0; } p { line-height: 1.7; max-width: 780px; }
.eyebrow { color: #54737d; font-size: 14px; letter-spacing: 2px; }
.card { background: white; border: 1px solid #d5e1e6; padding: 30px; margin: 25px 0; }
a { color: #186b76; } footer { margin-top: 38px; font-size: 14px; color: #54737d; }
"""


def document(brand: str, title: str, body: str) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{title}</title><style>{STYLE}</style></head><body>"
        f"<header><strong>{brand}</strong><span>FICTIONAL DEMO PAGE</span></header>"
        f'<main><div class="eyebrow">HAWK-EYE / SYNTHETIC FIXTURE</div><h1>{title}</h1>'
        f"{body}<footer>{LIMIT}</footer></main></body></html>"
    )


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    assets: dict[str, dict[str, str]] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 760}, device_scale_factor=1)
        page.route("**/*", lambda route: route.abort())

        def case(
            case_id: str, host: str, pages: list[tuple[str, str, str]], limited: bool = False
        ) -> dict[str, Any]:
            records = []
            evidence = []
            assets[case_id] = {}
            for index, (route, title, body) in enumerate(pages):
                page_id = f"{case_id}-page-{index + 1}"
                url = f"https://{host}{route}"
                html = document(host.split(".")[0].title() + " Demo", title, body)
                page.set_content(html)
                text = page.locator("body").inner_text()
                screenshot = ASSETS / f"{page_id}.png"
                page.screenshot(path=str(screenshot))
                for kind, suffix, content in (
                    ("html", ".html.txt", html),
                    ("visible_text", ".txt", text),
                    ("screenshot", ".png", None),
                ):
                    artifact_id = f"{page_id}-{kind}"
                    path = ASSETS / f"{page_id}{suffix}"
                    if content is not None:
                        path.write_text(content, encoding="utf-8")
                    assets[case_id][artifact_id] = path.name
                    record: dict[str, Any] = {
                        "id": artifact_id,
                        "type": kind,
                        "source_url_display": url,
                        "collected_at": AT,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "page_id": page_id,
                        "artifact_available": True,
                    }
                    if kind == "screenshot":
                        record["image_dimensions"] = {"width": 1200, "height": 760}
                    evidence.append(record)
                records.append(
                    {
                        "id": page_id,
                        "depth": index,
                        "state": "complete",
                        "final_url_display": url,
                        "capture_outcome": "captured",
                        "access_outcome": "restricted" if limited else "accessible",
                        "capture_adequacy": "limited" if limited else "usable",
                        "extraction_eligible": not limited,
                        "extraction_tier": "none" if limited else "dom",
                        "extraction_skip_reason": "restricted_sample" if limited else None,
                        "public_status": "limited" if limited else "complete",
                        "limitation_reasons": [LIMIT]
                        + (["Restricted sample: no content extracted."] if limited else []),
                        "html_evidence_id": f"{page_id}-html",
                        "visible_text_evidence_id": f"{page_id}-visible_text",
                        "screenshot_evidence_id": f"{page_id}-screenshot",
                        "initial_screenshot_evidence_id": f"{page_id}-screenshot",
                        "full_page_screenshot_evidence_id": f"{page_id}-screenshot",
                    }
                )
            return {
                "case_id": case_id,
                "integrity": "verified",
                "status": "complete",
                "started_at": AT,
                "completed_at": AT,
                "page_title": pages[0][1],
                "seed_url_display": f"https://{host}/",
                "final_url_display": f"https://{host}/",
                "capture_outcome": "captured",
                "access_outcome": "restricted" if limited else "accessible",
                "capture_adequacy": "limited" if limited else "usable",
                "content_usable": not limited,
                "extraction_eligible": not limited,
                "extraction_tier": "none" if limited else "dom",
                "extraction_skip_reason": "restricted_sample" if limited else None,
                "public_status": "limited" if limited else "complete",
                "limitation_reasons": records[0]["limitation_reasons"],
                "pages": records,
                "evidence": evidence,
                "observations": [],
                "candidates": [],
                "page_count": len(records),
                "candidate_count": 0,
                "gambling_indicator_count": 0,
                "gambling_indicators": {
                    "status": "sample",
                    "policy_version": "demo-v1",
                    "indicator_count": 0,
                    "reviewed_observation_count": 0,
                    "category_counts": {},
                    "classifications": [],
                    "limitations": [LIMIT],
                },
            }

        contact = case(
            "demo-contact-case",
            "harbor.demo.invalid",
            [
                (
                    "/",
                    "Harbor Demo",
                    "<p>A fictional public site for exploring evidence provenance.</p>"
                    '<div class="card"><h2>Sample casino bonus offer</h2>'
                    "<p>This offer is authored demo text, not a real promotion.</p></div>"
                    '<a href="/contact">Public contact page</a>',
                ),
                (
                    "/contact",
                    "Public contact",
                    "<p>Contact information displayed by the fictional Harbor Demo site.</p>"
                    '<div class="card"><h2>Support desk</h2>'
                    "<p>Email: support@harbor.demo.invalid</p></div>",
                ),
            ],
        )
        related = case(
            "demo-related-case",
            "tide.demo.invalid",
            [
                (
                    "/",
                    "Tide Demo",
                    "<p>This fictional page visibly links to another example site.</p>"
                    '<div class="card"><h2>Related public page</h2>'
                    '<a href="https://harbor.demo.invalid/">Visit Harbor Demo</a>'
                    "<p>A link alone does not establish common ownership.</p></div>",
                ),
            ],
        )
        restricted = case(
            "demo-restricted-case",
            "restricted.demo.invalid",
            [
                (
                    "/",
                    "Content unavailable",
                    "<p>The sample page represents an access restriction.</p>"
                    '<div class="card"><h2>Collection stopped here</h2>'
                    "<p>The visible restriction is preserved. No contacts or offers are inferred "
                    "from unavailable content.</p></div>",
                ),
            ],
            limited=True,
        )

        def observation(
            value: dict[str, Any], index: int, kind: str, display: str
        ) -> dict[str, Any]:
            record = value["pages"][index]
            item = {
                "id": f"{value['case_id']}-obs-{len(value['observations']) + 1}",
                "type": kind,
                "display_value": display,
                "raw_value": display,
                "source_page_id": record["id"],
                "source_artifact_id": record["html_evidence_id"],
                "screenshot_evidence_id": record["screenshot_evidence_id"],
                "surrounding_text": display,
                "evidence_strength": "observed",
                "extraction_method": "authored_fixture",
                "limitations": [LIMIT],
            }
            value["observations"].append(item)
            return item

        observation(contact, 0, "claimed_brand_identity", "Harbor Demo")
        offer = observation(contact, 0, "public_offer_claim", "Sample casino bonus offer")
        observation(contact, 1, "public_email_address", "support@harbor.demo.invalid")
        contact["gambling_indicator_count"] = 1
        contact["gambling_indicators"].update(
            {
                "indicator_count": 1,
                "reviewed_observation_count": 3,
                "category_counts": {"gambling_offer": 1},
                "classifications": [
                    {
                        "observation_id": offer["id"],
                        "label": "indicator",
                        "category": "gambling_offer",
                        "display_value": offer["display_value"],
                        "matched_terms": ["casino"],
                        "source_artifact_id": offer["source_artifact_id"],
                        "screenshot_evidence_id": offer["screenshot_evidence_id"],
                    }
                ],
            }
        )
        observation(related, 0, "public_link", "https://harbor.demo.invalid/")
        related["candidate_count"] = 1
        related["candidates"] = [
            {
                "candidate_id": "demo-harbor-lead",
                "hostname": "harbor.demo.invalid",
                "url": "https://harbor.demo.invalid/",
                "state": "pending",
                "reasons": [{"kind": "direct_public_link"}],
            }
        ]

        def run(value: dict[str, Any], workspace_id: str) -> dict[str, Any]:
            nodes: list[dict[str, Any]] = []
            edges: list[dict[str, Any]] = []
            events: list[dict[str, Any]] = []
            animations: list[dict[str, Any]] = []

            def event(kind: str, target: str | None = None, **payload: Any) -> str:
                sequence = len(events) + 1
                event_id = f"{workspace_id}-event-{sequence}"
                events.append(
                    {
                        "event_id": event_id,
                        "sequence": sequence,
                        "case_id": value["case_id"],
                        "run_id": workspace_id,
                        "kind": kind,
                        "occurred_at": AT,
                        "schema_version": "1",
                        "payload": {"collection_mode": "synthetic_fixture", **payload},
                    }
                )
                if target:
                    animations.append({"target_id": target, "sequence": sequence})
                return event_id

            seed_id = f"page:{value['pages'][0]['id']}"
            event("run.started", seed_id)
            for index, record in enumerate(value["pages"]):
                node_id = f"page:{record['id']}"
                nodes.append(
                    {
                        "id": node_id,
                        "kind": "seed_page" if index == 0 else "collected_page",
                        "label": record["final_url_display"],
                        "status": "limited"
                        if value["capture_adequacy"] == "limited"
                        else "observed",
                        "attributes": {
                            "page": record,
                            "page_id": record["id"],
                            "url": record["final_url_display"],
                            "screenshot_evidence_id": record["screenshot_evidence_id"],
                            "limitations": value["limitation_reasons"],
                        },
                    }
                )
                event("collection.started", node_id, page_id=record["id"])
                captured = event(
                    "artifact.captured",
                    node_id,
                    artifact_id=record["screenshot_evidence_id"],
                    artifact_type="screenshot",
                )
                if index:
                    edges.append(
                        {
                            "id": f"navigation-{node_id}",
                            "source": seed_id,
                            "target": node_id,
                            "relation": "public_navigation",
                            "appearance": "solid",
                            "supporting_event_ids": [captured],
                        }
                    )
            for item in value["observations"]:
                node_id = f"observation:{item['id']}"
                kind = {
                    "claimed_brand_identity": "claimed_brand",
                    "public_email_address": "public_contact",
                    "public_offer_claim": "public_claim",
                    "public_link": "candidate_domain",
                }[item["type"]]
                nodes.append(
                    {
                        "id": node_id,
                        "kind": kind,
                        "label": item["display_value"],
                        "status": "lead" if kind == "candidate_domain" else "observed",
                        "attributes": {
                            "page": next(
                                page
                                for page in value["pages"]
                                if page["id"] == item["source_page_id"]
                            ),
                            "observation": item,
                            "observation_type": item["type"],
                            "claim_category": "Offer claims" if kind == "public_claim" else "",
                            "limitations": [LIMIT],
                        },
                    }
                )
                observed = event("observation.created", node_id, **item)
                edges.append(
                    {
                        "id": f"observed-{item['id']}",
                        "source": f"page:{item['source_page_id']}",
                        "target": node_id,
                        "relation": "candidate_lead"
                        if kind == "candidate_domain"
                        else "observed_on_page",
                        "appearance": "dashed" if kind == "candidate_domain" else "solid",
                        "supporting_event_ids": [observed],
                        "evidence": {
                            "source_artifact_ids": [item["source_artifact_id"]],
                            "limitations": [LIMIT],
                        },
                    }
                )
            pending = value is related
            if pending:
                event(
                    "candidate_page.approval_required",
                    nodes[-1]["id"],
                    url="https://harbor.demo.invalid/",
                )
            event(
                "run.completed",
                seed_id,
                stop_reason="waiting_for_approval"
                if pending
                else "limited"
                if value is restricted
                else "completed",
            )
            return {
                "workspace_id": workspace_id,
                "case_id": value["case_id"],
                "run_id": workspace_id,
                "source_kind": "synthetic_fixture",
                "source_case_id": value["case_id"],
                "seed_url": value["seed_url_display"],
                "investigation_name": "Sample investigation",
                "investigation_mode": "guided",
                "agent_mode": "demo_replay",
                "agent_steps": 0,
                "capture_adequacy": value["capture_adequacy"],
                "extraction_tier": value["extraction_tier"],
                "agent_stop_reason": "waiting_for_approval"
                if pending
                else "limited"
                if value is restricted
                else "completed",
                "lead_status": "waiting_for_approval"
                if pending
                else "limited"
                if value is restricted
                else "complete",
                "updated_at": AT,
                "pending_leads": [
                    {
                        "lead_id": "demo-harbor-lead",
                        "url": "https://harbor.demo.invalid/",
                        "hostname": "harbor.demo.invalid",
                        "status": "pending",
                    }
                ]
                if pending
                else [],
                "events": events,
                "graph": {"nodes": nodes, "edges": edges, "animations": animations},
                "source_case": value,
                "gambling_indicators": value["gambling_indicators"],
                "assertions": [],
                "reviews": [],
                "all_reviews": [],
                "assertion_statuses": {},
                "pending_review_count": 0,
                "artifacts": [
                    {"name": name, "type": evidence["type"]}
                    for evidence in value["evidence"]
                    for name in [assets[value["case_id"]][evidence["id"]]]
                ],
            }

        runs = [
            run(contact, "demo-contact"),
            run(related, "demo-related"),
            run(restricted, "demo-restricted"),
        ]
        write_json(OUTPUT / "fixtures.json", {"runs": runs, "assets": assets, "limitation": LIMIT})
        browser.close()


if __name__ == "__main__":
    main()
