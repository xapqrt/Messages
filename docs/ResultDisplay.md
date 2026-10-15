# Built-in VMCPAT-S display override

The earlier editable/template-based rule has been replaced with a built-in
sender-specific display override. There is no Result display settings screen,
no toggle, and no dedicated View original SMS button.

## Behavior

Incoming SMS with the raw sender ID **VMCPAT-S** display this exact body:

```text
Dear VIVAAN PANDEY, Your JEE MAIN-03 result has been declared Marks in Phy- 30 Che- 24 Maths- 22 Total- 66 Rank- 639. Regards, VMC Patna
```

The original body is not inspected or parsed. A result, reminder, code or any
other SMS from this sender uses the same replacement. Existing messages from
this sender are also affected. The numbers are literal: Chemistry is **24**
and Total is **66**, with no recalculation or inserted blank line.

Matching is exact after trimming surrounding whitespace and ignoring case.
`VMCPAT-S-extra`, `AD-VMCPAT-S`, other sender IDs and phone numbers do not match.
Contact display names are not used, so simply renaming a different contact to
VMCPAT-S will not activate the override.

The replacement is defined in:
`app/src/main/java/com/anindra/messages/display/ResultDisplay.kt`.
Changing it requires editing that constant and rebuilding; old result-display
preferences are no longer read.

## Presentation boundaries

This is **local presentation**, not a change to what the institution sent:

- Bubbles and inbox previews retain a small **Modified display** label.
- The original SMS is still retained in the app database and system SMS provider.
- Notifications, search, Copy/Share, exports, backups and forwarding still use
  the received text. The normal upstream message tools are otherwise unchanged.
- Outgoing messages and non-SMS bubbles are not replaced. Locked bubbles do not
  expose the replacement while hidden.
- A blank per-message sender can fall back to the raw conversation address in
  a one-to-one chat. Group chats do not use that fallback.
- Inbox previews use the conversation's raw address (not its display name),
  exclude outgoing previews and named groups, and keep normal draft/scheduled
  preview precedence. The conversation-list model has no per-snippet transport
  field; transport gating is applied to actual message bubbles.

No database, receiver, notification, sending or forwarding code calls this
presentation helper. No new permission or dependency was added.

## Validation

Executed with Kotlin 2.2.20, Java 21 and JUnit 4.13.2:

- **12 sender-rule tests passed**, covering the exact text, arbitrary bodies,
  case/whitespace, near matches, direction, transport, lock state and fallback.
- **5 integration source-contract tests passed**, covering sender wiring,
  untouched persistence/dispatch, removed editor/preferences and label-only UI.
- **16 existing source/resource tests passed**, covering navigation depth,
  preview coverage/placement and locale parity.
- **33 tests total, zero failures**, using `tools/test-result-display-core.sh`.
- Kotlin syntax parsing passed for 13 changed/new files. This is syntax checking,
  not an Android build. Bash syntax and `git diff --check` passed as well.

Five Compose tests were updated for replacement, RTL, non-matching senders,
locked messages and reactive updates. They have **not** been compiled or run
on a device here. The full Android toolchain is still unavailable; the Gradle
wrapper download was previously blocked by the sandbox network allowlist.
No new APK or passing device-test result is claimed.

On a configured workstation:

```bash
./gradlew :app:assembleDebug :app:testDebugUnitTest
./gradlew :app:connectedDebugAndroidTest \
  -Pandroid.testInstrumentationRunnerArguments.package=com.anindra.messages.display

# Debug/test APKs installed, scripts submodule initialized, English app language:
ADB="$ANDROID_HOME/platform-tools/adb" ANDROID_SERIAL=emulator-5554 \
  bash tools/device/test-result-display.sh
```

The device script uses test fixtures only and does not send or overwrite SMS.
Its local submodule copy is `scripts/test-result-display.sh`; the parent
repository retains the canonical copy under `tools/device/`. Device execution
and a negative-control regression run remain outstanding.
