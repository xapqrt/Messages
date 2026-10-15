# Changelog

## Unreleased — built-in sender display override (2026-10-15)

- Supersedes the editable result rule below: match raw `VMCPAT-S` instead of
  parsing a VMC result template; use the exact requested text for any body.
- Hard-code Chemistry 24 and literal Total 66 without recalculation.
- Remove the result settings route, editor, preference access and original-view
  dialog/button; retain a localized Modified display label.
- Preserve original persistence, notifications, Copy/Share and forwarding.
- Resolve missing per-message sender only from a one-to-one conversation;
  preserve outgoing/non-SMS/locked-body guards.
- 17 updated feature tests plus 16 existing source/resource tests pass (33 total).
  Five revised device tests are unrun; Android build/APK verification is pending.

## Unreleased — editable result display (2026-10-15)

- Added an opt-in, visible Result display settings page in both existing UI variants.
- Match incoming VMC Patna JEE MAIN result templates with variable names, exam
  numbers, whitespace and received scores; unmatched messages stay unchanged.
- Editable subject scores and rank default to 30 / 14 / 22 / 639. Total is
  calculated (66), not blindly replaced with an inconsistent value.
- Render customized bubbles and marked inbox previews without modifying stored
  or transmitted text; provide a selectable original-SMS dialog.
- Preserve locked-message privacy and original notification/copy/search behavior.
- Added localized strings, debug previews, 20 passing JVM tests, nine unrun
  Android tests and a device regression script. Sixteen existing source/resource
  tests also passed. Full Android build and device verification remain blocked.

## Unreleased — transparent selective forwarding (2026-10-15)

Based on the existing `xapqrt/Messages` checkout at
`c4b225e488965685dc78102c42d7620aa5867434`, derived from `an1ndra/Messages`.

### Added

- Optional priority-ordered, first-match selective SMS copying, sender exclusion,
  linear-time regex matching, prefix/suffix templates and SIM-slot rules.
- Visible forwarding settings in both upstream UI variants, destination consent,
  a two-rule setup, an inbox status banner and a notification Stop action.
- Encrypted rule configuration, metadata-only activity history, persistent replay
  protection, per-part send results, loop and cost safeguards.
- WorkManager integrity/status maintenance and boot/package-upgrade handling.
- JVM tests, Android transport/store tests, Compose consent/RTL-banner tests,
  debug previews and a non-sending device regression script.
- Build/signing instructions, a fail-fast release-signing helper and documented
  validation gaps.

### Changed

- SMS receiver now accepts only SMS_DELIVER and rejects delivery when not default.
- Incoming subscription ID resolution handles zero and resolves SIM slots rather
  than treating slots as subscription IDs.
- Forwarding occurs only after local persistence; forwarding failures do not
  suppress normal notifications or remove originals.
- Added RE2/J runtime dependency and Android instrumentation-test dependencies.

### Deliberate scope differences

- No stealth UI, secret settings gestures, DROP action, forwarded-message hiding
  or automatic removal of originals. Editing rules requires renewed opt-in.
- Preserved the actual upstream SQLite schema and manual Compose navigation.
  No Room/SQLCipher message-store migration, min-SDK downgrade, or theme rewrite.
- Rule configuration encryption is not full message-database encryption.
- No new INTERNET or FOREGROUND_SERVICE permission. Static receivers are not
  periodically re-registered; WorkManager cannot override OS force-stop policy.
- Upstream minimum SDK 29 and compile/target SDK 36 are unchanged.
- New translations, full Android build, connected tests, carrier/dual-SIM checks,
  screenshot parity and a signed release artifact remain unverified/unproduced.

See [Forwarding.md](docs/Forwarding.md) for usage and failure semantics, and
[ForwardingValidation.md](docs/ForwardingValidation.md) for actual test results.
