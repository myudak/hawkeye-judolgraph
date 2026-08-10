"""Server-side policy checks for one bounded read-only interaction request."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from .models import InteractiveElement

_FORBIDDEN = re.compile(
    r"\b(login|log in|sign in|register|sign up|create account|submit|send|chat|"
    r"payment|pay|deposit|withdraw|withdrawal|bet|wager|download|install|captcha)\b",
    re.I,
)
_EXTERNAL_APPLICATION_SCHEMES = {"mailto", "tel", "sms", "tg", "whatsapp", "intent"}
_SAFE_REVEALS = {
    "reveal_modal",
    "reveal_menu",
    "reveal_tab",
    "inspect_public_iframe",
}


def validate_read_only_interaction(
    element: InteractiveElement,
) -> tuple[bool, str, dict[str, object]]:
    """Validate every relevant pre-click attribute; fixture declarations are not sole authority."""

    combined = " ".join(
        value
        for value in (
            element.accessible_name,
            element.visible_text,
            element.href,
            element.action,
            element.form_action,
        )
        if value
    )
    destination = element.destination_url or element.href
    scheme = urlsplit(destination).scheme.casefold() if destination else ""
    checks: dict[str, object] = {
        "element_type": element.tag,
        "role": element.role,
        "label": element.accessible_name,
        "href": element.href,
        "form_owner": element.form_owner,
        "form_action": element.form_action,
        "download_attribute": element.download_attribute,
        "opens_new_tab": element.opens_new_tab,
        "destination_url": destination,
        "destination_scheme": scheme,
        "forbidden_keyword": bool(_FORBIDDEN.search(combined)),
    }
    if element.download_attribute:
        return False, "download_attribute_blocked", checks
    if (
        element.form_owner
        or element.form_action
        or element.tag.casefold() in {"input", "select", "textarea"}
    ):
        return False, "form_or_input_action_blocked", checks
    if scheme in _EXTERNAL_APPLICATION_SCHEMES:
        return False, "external_application_launch_blocked", checks
    if _FORBIDDEN.search(combined):
        return False, "forbidden_action_keyword", checks
    if element.expected_unsafe:
        return False, "fixture_marks_control_as_prohibited", checks
    if element.declared_behavior in _SAFE_REVEALS:
        return True, "validated_public_reveal", checks
    if element.declared_behavior == "open_public_link":
        split = urlsplit(destination or "")
        if split.scheme not in {"http", "https"} or not split.hostname:
            return False, "public_link_destination_invalid", checks
        if split.path.casefold().endswith((".apk", ".bin", ".dmg", ".exe", ".msi", ".zip")):
            return False, "binary_destination_blocked", checks
        return True, "validated_public_link", checks
    return False, "ambiguous_or_undeclared_action", checks
