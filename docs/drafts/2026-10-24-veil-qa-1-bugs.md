# VEIL-QA-1: bugs left open (drafts)

Found by black-box QA (Playwright) and a code audit on 24 Oct 2026, at commit aabbb71 on http://localhost:5173 with a local PostgreSQL, the AI model off (no Mubit key) and a fresh test account. The repo has no Linear line yet, so these are drafts; nothing was filed.

Fixed in the same pass and covered by `frontend/e2e/` (21 Playwright tests): the castle jumping sideways on press (L3), stamps under the band (L4), documents lost after a resize (L10), the hero's castle and hills sliding under the band while scrolling, the journey's hills sliding off a phone screen (L11), the skip button over the enlarged document on phones (L5), the closed gate in the reduced-motion finish (L13), a clean sweep shown as "guard finished" in the last 300 ms, hot-cursor sparks over buttons that are not pressable, the reduced-motion journey's unhydrated scroll ref, focus lost after "Play again", the hero castle size depending on resize history and the mobile URL bar, placeholder tags spilling out of their bars, the button glow (now a nudge, per DESIGN.md), and the app's review bar sitting at the end of a 10,000 px page on phones (A9).

## Open

### 1. [BE] NI number only partly hidden
- Actual: "QQ 12 34 56 C" becomes "QQ SORT_CODE_2 C"; the prefix and suffix letters stay visible.
- Expected: the whole NI number is one NI placeholder.
- Steps: sign in, paste "NI QQ 12 34 56 C", press Hide personal data, read the redacted line.
- Severity: major (part of an identifier leaks). Fingerprint: `be:/api/documents/redact:ni-number-partial`.
- Rule that would have caught it: a regex-layer test per UK identifier format that asserts the full span, not just a hit.

### 2. [BE] Dates of birth are not hidden with the model off
- Actual: in the black-box run (A7, a tenancy sample) the dates of birth stayed visible in number-only mode.
- Expected: either the number rules hide dates of birth, or the model-off notice says dates are not covered.
- Severity: minor. Fingerprint: `be:/api/documents/redact:dob-not-hidden`.

### 3. [FE] Ask panel shows developer wording when the model is off
- Actual: "Start the backend with MUBIT_API_KEY set".
- Expected: plain words for a user, for example "The AI is not connected on this server, so questions cannot be answered yet."
- Severity: minor. Fingerprint: `fe:/app:ask-model-off-copy`.

### 4. [FE] Browser Back from a document leaves the app
- Steps: open a document from the rail, press the browser Back button.
- Actual: the landing page opens. Expected: back to the intake or the previous document.
- Severity: minor. Fingerprint: `fe:/app?doc:back-leaves-app`.

### 5. [FE] Sign-in form comes back in sign-up mode after logging out
- Severity: minor. Fingerprint: `fe:/app:logout-shows-signup`.

### 6. [FE] Ask conversation gone after a reload
- Steps: approve a document, ask a question, reload. Actual: the thread is empty. Expected: the stored turns come back (the backend stores them since 551de87).
- Severity: minor. Fingerprint: `fe:/app?doc:ask-thread-lost-on-reload`.

### 7. [FE] Sessions get duplicate names
- Two pastes are both "pasted.txt"; repeated samples share a name. Expected: a distinguishing suffix or the first line of the text.
- Severity: minor. Fingerprint: `fe:/app:duplicate-session-names`.

### 8. [FE] Each document opens its redaction stream twice in development
- The first request is aborted at once. Probably React StrictMode running the effect twice in dev; confirm it does not happen in a production build.
- Severity: minor. Fingerprint: `fe:/api/documents/redact/stream:double-request`.

### 9. [FE] Victory screen is cramped at 1440 x 900
- The title touches the top edge (y=0) and Continue ends at y=900. Focus is lost after Continue.
- Severity: minor. Fingerprint: `fe:/app:victory-cramped`.

### 10. [FE] Small text and targets on phones
- The journey's answer text renders at about 7 px at 375 px wide (the whole stage is scaled down).
- App controls on phones are 15 to 40 px tall, under the 44 pt floor in the product kit.
- Severity: minor. Fingerprint: `fe:/:small-targets-mobile`.

### 11. [Design] DESIGN.md mismatches in the app
- The victory message (Veil speaking) is set in the serif; DESIGN.md wants a pixel face.
- Signal red is used for info chips and the error box; DESIGN.md keeps red for redaction marks and commit actions.
- Severity: minor. Fingerprint: `design:/app:type-and-red`.

### 12. [FE] Journey camera hops when a phone's URL bar shows or hides
- `useScroll` with `offset: ["end end"]` depends on the window height, so progress shifts by about 2.6% and the panning camera moves about 30 px.
- Severity: minor. Fingerprint: `fe:/:journey-camera-hop`.

### 13. [FE] At 1920 and 2560 wide the castle is large and "Follow a document" is below the fold
- By design the castle may run 10% past the first screen; check whether the team wants the cue visible on big screens.
- Severity: minor. Fingerprint: `fe:/:hero-cue-below-fold`.

## What would have caught the fixed bugs earlier
- Castle jump: a rule to never animate `translate` or `transform` on an element that is positioned with a Tailwind translate class; plus a Playwright bounding-box check for every new animated element.
- Stamps under the band, lost documents after resize: lay out absolutely positioned pieces from a ResizeObserver, not from window resize; a Playwright check after `setViewportSize`.
- Hills off screen on phones: tile moving backgrounds by background position, not by translating a finite strip.
- Review bar at the end of a long page: test long documents at phone size, not only short samples.
