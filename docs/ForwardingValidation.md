# Forwarding validation status

Date: 2026-10-15. Branch: `arena/8d095b01-messages`.

**This is a source implementation, not a completed or device-certified release.**
The original stealth/deletion acceptance criteria were intentionally replaced
with transparent opt-in forwarding and local retention.

## Executed successfully

| Check | Result |
|---|---|
| RuleEngineTest | 16 tests passed |
| IncomingSmsPipelineTest | 4 tests passed |
| IncomingSimTest | 4 tests passed |
| ForwardingIntegrationContractTest | 4 source-contract tests passed |
| Existing PreviewCoverageTest / PreviewPlacementTest | 6 source-contract tests passed |
| Existing NavTransitionDepthTest | 3 source-contract tests passed |
| Existing TranslationParityTest | 7 resource-contract tests passed |
| **Standalone JVM total** | **44 tests, 0 failures** |
| Rule/codec/crypto/store/SIM/pipeline Kotlin compilation against an API-36 jar | Passed (partial compilation, not an Android app build) |
| XML parse: manifest + 13 forwarding resource files | 14 files passed |
| Bash syntax: added helpers and device script | Passed |
| Release helper with no signing environment | Failed early as intended; no build/signing attempted |
| `git diff --check` | Passed |

The standalone JVM run used Kotlin 2.2.20, JUnit 4.13.2, Hamcrest 1.3 and a
Java 21 runtime. Because Maven was unavailable, RE2/J classes came from the
standalone Closure Compiler Java distribution, **not** a resolved Gradle
`com.google.re2j:re2j:1.8` artifact. Run the normal Gradle suite with the declared
dependency versions before release. Dependencies/test output were kept in an
excluded cache outside the repository, not vendored or committed.

An initial standalone run launched from the repository root failed seven
resource tests because their existing harness expects the `app/` working
directory. Re-running from `app/` passed all 44. `tools/test-forwarding-core.sh`
now selects that directory automatically. No production code was changed to
bypass those tests.

The supplemental test helper takes `JAVA_HOME`, `KOTLIN_HOME`, `JUNIT_JAR`,
`HAMCREST_JAR` and `RE2J_JAR`. It can include the three codec tests if `JSON_JAR`
is supplied. It is **not a replacement for the Android Gradle build**.

## Not executed / blocked

- Baseline `./gradlew assembleDebug` initially failed because Java was missing.
- After provisioning a standalone JVM, Gradle failed downloading its distribution
  from `services.gradle.org` with a TLS handshake error under this sandbox's
  network allowlist. Google Maven/Maven Central are also outside the allowlist.
- No complete Android SDK, emulator or device is installed. An Android API jar
  was obtained only for partial compilation; it is not an SDK/build-tools install.
- Full Gradle unit suite, three codec tests, lint, resource compilation, Compose
  compilation and APK packaging have **not** run successfully here.
- Eleven Android store/transport tests and four Compose tests were authored but
  **not compiled or run on a device**. The transport tests use the injected
  SmsCopySender port; they do not send paid SMS or certify SmsManager/carrier
  integration. Local-retention assertions use an isolated SQLite inbox fixture,
  not the upstream production Repository/provider database.
- `tools/device/test-forwarding.sh` was syntax-checked only. No UI negative-control
  run, install, screenshot comparison, or LTR/RTL conversation-bubble test was
  performed. The new RTL UI test covers the status banner, not chat bubbles.
- No signed release APK was created. No release key, password, token or APK was
  added to Git. No GitHub PR, push, release or remote CI run was initiated.

## Required release checklist

- [ ] Run `:app:assembleDebug :app:testDebugUnitTest :app:lintDebug` on a complete
      Android toolchain; fix any compiler/lint/dependency errors found.
- [ ] Run `:app:connectedDebugAndroidTest` on API 34 and the supported API bounds.
- [ ] Verify default-SMS eligibility and actual incoming multipart SMS ingestion.
- [ ] With two numbers you control, confirm exclusion, copying, local retention,
      normal original-message notifications and visible forwarding status.
- [ ] Exercise two real SIMs whose subscription IDs differ from slot indices,
      including slot override, SIM removal, airplane mode and carrier failure.
- [ ] Confirm Unicode/multipart callbacks, no duplicate sends after process death,
      notification permission/channel revocation, and Stop during incoming SMS.
- [ ] Confirm reboot, upgrade, force-stop and OEM battery behavior; document gaps.
- [ ] Run the UI regression for both UI variants and perform a negative-control run.
- [ ] Validate original inbox/provider sync, import/export and existing regression
      suites after the receiver changes.
- [ ] Review new localization text in all shipped languages (currently English
      fallbacks), accessibility, large font sizes and RTL layouts.
- [ ] Build with the owner's release key and verify with `apksigner` before
      distribution; preserve GPL source/license obligations.

## Intentionally not implemented

Concealed forwarding, hidden controls, deletion/hiding of forwarded originals,
DROP rules, Room/SQLCipher message-store migration, min-SDK-26 downgrade,
NavHost rewrite, mandatory default-app onboarding replacement, automatic MMS/RCS
forwarding and a claim of indistinguishable Google Messages screenshots.

The `scripts/` submodule has a local regression-script copy and TODO update.
Its commit pointer is unchanged. The parent repository also carries the script
at `tools/device/test-forwarding.sh` and this checklist so those deliverables
are not dependent on publishing an unrelated submodule branch.
