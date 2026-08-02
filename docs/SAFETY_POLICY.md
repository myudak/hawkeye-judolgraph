# Bounded Read-Only Interaction Policy

Policy version `public-read-only-interaction-v1` validates every requested interaction on the
server side. Model instructions and fixture labels are not treated as security controls.

The executor exposes only `page_get_state`, `page_list_interactive_elements`,
`page_click_read_only`, `page_open_public_link`, `page_capture_state`, and
`page_get_redirect_chain`. A stable reference binds DOM path, role, tag, accessible name, visible
text, href/action, element ID, fingerprint, and discovery snapshot. A changed snapshot or
fingerprint is rejected.

Pre-click validation checks the element type and role, label, href, form owner/action, download
attribute, popup/new-tab behavior, destination scheme, forbidden keywords, budget, and current
snapshot. Login, registration, form or input actions, messaging/contact submission, payment,
deposit, withdrawal, betting, downloads/binaries, CAPTCHA actions, and external-application schemes
are always blocked. `Contact Us` is deliberately ambiguous and blocked.

The shared budget is five iterations, three interactions, three pages, depth one, five redirects,
one search query, three candidate pages, and 120 seconds. The controlled benchmark has exactly ten
scenarios and currently blocks all four prohibited controls (100%). This result is fixture scope,
not a live-web safety guarantee.

