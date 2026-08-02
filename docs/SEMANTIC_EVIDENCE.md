# Semantic Evidence (G4B)

The semantic chain keeps separate records for artifacts, observations, extracted entities,
candidate assertions, and human reviews. `observations.json` is generated only when the capture is
eligible: captured navigation, content access outcome, adequate capture, and direct extractor input
at most 2 MB.

Implemented observation types are claimed brand identity; public Telegram alias, WhatsApp link,
phone number, and email address; outgoing link and redirect target; download destination; payment
method and provider; offer claim; legal or license claim; referral code; and tracking identifier.
Payment, offer, and legal dictionaries are weak public claims. A visible brand is stored with
`entity_class: ClaimedBrandIdentity` and `verified_ownership: false`.

Every observation preserves raw and normalized value, page URL and ID, source HTML artifact,
selector when available, bounded surrounding text, canonical screenshot, confidence, extraction
method, strength, and limitations. The collector snapshots at most 300 visible evidence-bearing
elements in the final viewport. When one matches an observation and its bounded box is valid, the
pipeline writes a PNG crop linked to the observation and full screenshot. Crop failure never
removes an observation.

Download observations inspect only the anchor destination, extension, target, and download
attribute. The collector does not open messaging applications or download, install, execute,
submit, or transact.
