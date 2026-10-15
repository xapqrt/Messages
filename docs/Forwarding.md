# Selective SMS forwarding (transparent variant)

This branch extends the existing `xapqrt/Messages` checkout derived from
`an1ndra/Messages`. It does **not** implement concealed interception, hidden
settings, automatic deletion of originals, or a DROP action. Forwarding requires
explicit confirmation and remains visible. Use it only on your own device with
destinations you control; private messages and verification codes may be copied,
and carrier charges apply.

## Configure the example

1. Install the app and use the existing first-launch default-SMS prompt. On
   Android 10+, it requests `RoleManager.ROLE_SMS`. You can also use Android
   Settings → Apps → Default apps → SMS app → Messages. `ACTION_MANAGE_DEFAULT_APPS_SETTINGS`
   does not provide a portable SMS-only scope, so the role request is preferred.
2. Grant SMS, phone-state and notification permissions. Forwarding will not
   enable with notifications or its status channel disabled. READ_CONTACTS is
   not required for forwarding.
3. Open **Settings → SMS forwarding** (in either existing UI variant).
4. Choose **Two-rule setup**, enter the excluded sender and destination, and
   save. This replaces the rule list and leaves forwarding **off**.
5. Review the generated rules:

   | Priority | Match | Action |
   |---|---|---|
   | 100 | Excluded sender exactly | Keep local only |
   | 0 | All SMS | Forward a copy to the destination |

6. Turn forwarding on, review the destination(s), and choose **Confirm and
   enable**. Use international `+countrycode` numbers; the runtime normalizes
   phone identities using the upstream libphonenumber helper.
7. The inbox banner and ongoing low-importance notification indicate that it
   is enabled. **Stop** is available in both, and the settings switch disables
   it as well. Copies already submitted to the carrier cannot be recalled.

Editing, deleting or replacing rules automatically disables forwarding. Enable
again only after reviewing the new destinations. There are no PIN-search,
long-press, version-tap, launcher disguise or hidden-preference access paths.

## Rules and templates

- Enabled rules are ordered by descending priority, then ascending rule ID.
- Only the first match applies. Unmatched SMS stay local; there is no forwarding
  fallback or DROP action.
- Match by ALL, SENDER_EXACT, SENDER_CONTAINS, BODY_CONTAINS or REGEX.
- Contains matching is case-insensitive. REGEX searches the body using RE2/J,
  is case-sensitive unless the pattern opts in, and deliberately disallows
  backreferences/lookaround. RE2 avoids unbounded backtracking on incoming text.
- Up to 50 rules, 64-character names, 512-character match expressions, and
  256-character prefixes/suffixes.
- Incoming SIM filters use physical slot indices internally. UI labels are
  one-based. Subscription IDs are never treated as slot indices.
- Outgoing SIM defaults to the actual incoming subscription. An explicit slot
  override is available. Missing/inactive SIMs fail the copy rather than using
  an unintended SIM.
- `{sender}`, `{timestamp}` (ISO-8601 UTC), `{sim}` (one-based, `?` if unknown)
  and `{original}` expand in prefixes/suffixes only. The original body is always
  appended between prefix and suffix; substitutions never recurse.
- Every copy begins with `[SMS copy] `. Incoming copies with this marker and
  SMS from any enabled destination are not forwarded. This is intentionally
  not configurable; it reduces common reciprocal/self-forwarding loops.

## Delivery and failure semantics

`SMS_DELIVER` is the only accepted action. A non-default app returns before
`goAsync()`. Multipart PDUs are joined using the existing receiver pipeline.
The original is written through the existing system-provider/local SQLite
path **before** forwarding is attempted. Original-message notifications remain
unchanged. Blocked senders, blocked keywords and recognized reactions continue
through upstream handling and do not enter forwarding.

A dedicated `SmsCopySender` port wraps `SmsManager`. `divideMessage()` accounts
for GSM-7/UCS-2 and headers; it is not a naive 160-character split. A single
part uses `sendTextMessage`; multiple parts use `sendMultipartTextMessage`.
The safety cap is 10 parts per copy and 30 reserved send attempts per hour.

Each attempt reserves a persistent HMAC fingerprint before dispatch. A repeated
broadcast does not send the same copy again during the 7-day retention window.
This deduplicates **forwarding attempts**, not upstream inbox inserts. Sent
callbacks have explicit, immutable PendingIntents with unique token/part URIs.
A callback is not an SMS delivery report:

- Preparing: reserved, not yet submitted.
- Submitted: waiting for all part callbacks.
- Sent to network: every part reported `Activity.RESULT_OK`; **not proof of
  recipient delivery**.
- Failed: an exception or at least one failed part; partial delivery is possible.
- Unknown: no final result after 10 minutes, as detected by a later health job.
- Loop blocked / rate limited: not submitted.

There are no automatic retries. Process death between reserving and dispatch
can lose a copy, and death after dispatch can leave an unknown result. Prefer
retaining the original and avoiding duplicate charges over pretending Android
can provide exactly-once carrier delivery. Metadata is cleaned after 7 days;
settings show the newest 100 entries.

The receiver finishes its asynchronous result in `finally`. WorkManager runs
best-effort integrity/status checks every 15 minutes; this is not an exact
schedule. Boot and package-replacement receivers enqueue a health check.
Manifest receivers do not need periodic registration, and a job cannot undo
force-stop restrictions or guarantee delivery on every OEM. No foreground
service or new Internet permission is used. Battery optimization is explained
in settings with a link to Android's battery settings, not a forced exemption.

## Storage and privacy boundaries

The **existing message database is still ordinary SQLite**. Android's system
SMS provider also contains originals. This implementation does not claim
SQLCipher protection for either database, or protection against root/ADB access
on a debuggable device. Upstream backup/export features retain their existing
security characteristics.

The new `forwarding.db` is separate from the upstream message schema:

- The rule configuration blob is AES-256-GCM encrypted with an Android Keystore
  key and authenticated with a version-specific AAD.
- Log entries contain an installation-keyed HMAC of the sender, time, rule ID,
  status and part counts. No message bodies, raw sender addresses or target
  numbers are written to the log. Hashes are still correlatable metadata, not
  anonymous statistics.
- The replay key is an HMAC over sender, original timestamp, subscription and
  body; the original body is not stored there.
- Keys are not derived from non-exportable Keystore bytes. Keystore performs
  the encryption/HMAC operations directly. These rule files cannot be restored
  to a different installation without their keys.
- The existing manifest disables Android app backup. No new telemetry, remote
  API, network transport or remote configuration has been added.

A Room/SQLCipher migration of the message store remains a separate, unimplemented
project: upstream provider sync, import/export, recovery and direct SQLite
queries must all be migrated together and tested against real user databases.
Do not infer full-database encryption from encrypted forwarding configuration.

## Compatibility and deliberate divergences

- Retains upstream min SDK **29**, compile/target **36**; Android 14 is within
  the supported range but has not been exercised here. Lowering to 26 would
  require auditing upstream API-29 assumptions, not just changing Gradle numbers.
- Retains upstream single-activity route state, themes, conversation list,
  thread UI and message schema; no NavHost/Room rewrite was attempted.
- Keeps upstream default-app onboarding rather than a new mandatory full-screen
  gate. Default-role qualification already includes SENDTO, SEND, SMS_DELIVER,
  WAP_PUSH_DELIVER, and the required RESPOND_VIA_MESSAGE service.
- Automatic **MMS and RCS forwarding are unsupported**. Existing local MMS
  support is untouched. RCS is not available to this app through Google Messages.
- No claim of pixel-identical parity with a current Google Messages release.
  No new screenshot comparison was performed.
- New forwarding strings have explicit English fallbacks in all existing
  locales; human-reviewed translations remain pending.
- No signed APK was produced in this sandbox. See the build and signing guide
  in the main README and [validation status](ForwardingValidation.md).

## References

The documented rule/transport separation in
[pppscn/SmsForwarder](https://github.com/pppscn/SmsForwarder) and the small receiver/
relay approach of [automagen-ab/sms-relay](https://github.com/automagen-ab/sms-relay)
were reviewed for architectural context. Their remote endpoints, remote controls,
telemetry and implementation code were not imported. This module uses only
carrier SMS and the existing app foundation.
