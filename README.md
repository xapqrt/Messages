# Messages

[![VirusTotal](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/an1ndra/Messages/main/.github/virustotal.json)](https://github.com/an1ndra/Messages/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/an1ndra/Messages/total?label=Downloads&logo=github)](https://github.com/an1ndra/Messages/releases)
[![License](https://img.shields.io/github/license/an1ndra/Messages?label=License)](LICENSE)

Simple, private SMS messaging. Offline-first, no ads, no tracking.

Built with **Kotlin + Jetpack Compose + Material 3 (M3)**. No internet permission — everything is local SMS + local database.

## ⚠️ Keep Android Open — Important

> **Unless you oppose it, Google will lock down Android in 2027** — silencing independent
> developers, F-Droid, and open-source distribution worldwide, with no opt-out [keepandroidopen.org](https://keepandroidopen.org).

## Built-in VMCPAT-S display override

Incoming SMS from the exact raw sender **VMCPAT-S** use a fixed, built-in display
body, regardless of their original contents: Physics **30**, Chemistry **24**,
Maths **22**, literal Total **66**, Rank **639**, for VIVAAN PANDEY / JEE MAIN-03.
There is no Result display settings editor or View original SMS button.

The **Modified display** label remains. Storage, notifications, copying and
forwarding retain the original message; this is not a rewrite of received SMS.
Other sender IDs and outgoing messages are unaffected. No forwarding setup is
required. See [ResultDisplay.md](docs/ResultDisplay.md) for the exact text,
matching boundaries and validation status. No APK has been produced here.

## This branch: transparent selective SMS forwarding

**Source implementation; not yet an Android-verified release.** This branch adds
opt-in selective forwarding with sender exclusions, normal settings access,
visible enabled status and a Stop action. Originals are retained. It does not
implement hidden interception or trace removal.

- Open **Settings → SMS forwarding → Two-rule setup**.
- Enter the excluded sender and a destination you control, save, then explicitly
  confirm enabling forwarding. Editing rules turns it off again.
- Read [configuration, safeguards and limitations](docs/Forwarding.md),
  [test results and remaining checks](docs/ForwardingValidation.md), and
  [divergences from upstream](CHANGELOG.md).

The upstream release links and screenshots below describe upstream Messages;
**they do not contain or demonstrate this branch's forwarding changes**.

## Build and test this checkout

Use Android Studio with JDK 21 and Android SDK Platform 36. The checked-in
wrapper and version catalog select Gradle 9.8.0, AGP 9.4.0 and Kotlin 2.2.20.
Google Maven, Maven Central, and Gradle distribution access are required.

```bash
# From the repository root; keep machine-specific SDK paths out of Git.
export ANDROID_HOME=/absolute/path/to/Android/Sdk
./gradlew --no-daemon :app:assembleDebug :app:testDebugUnitTest
adb install -r app/build/outputs/apk/debug/app-debug.apk
# With an API-34+ emulator/device connected:
./gradlew :app:connectedDebugAndroidTest
```

The existing first-launch prompt requests the default SMS role. Alternatively:
Android Settings → Apps → Default apps → SMS app → Messages. Then grant SMS,
phone-state and notification permissions. Forwarding settings also link to
these prerequisites. No hidden settings gesture is needed.

For the UI-only forwarding regression (English app language; no SMS sent):

```bash
git -c url.https://github.com/.insteadOf=git@github.com: submodule update --init scripts
ADB="$ANDROID_HOME/platform-tools/adb" ANDROID_SERIAL=emulator-5554 \
  bash tools/device/test-forwarding.sh
```

### Signed release build

Use your own release key, stored **outside the repository**. Do not use a shared
or committed test key for distribution. The existing signing config expects the
alias `messages`. Android Studio's Generate Signed Bundle / APK flow can create
or select it; alternatively run `keytool -genkeypair` interactively with that
alias. Keep passwords in your local environment or CI secret store, never in
source files or chat.

Set `RELEASE_KEYSTORE` to the absolute keystore path, `KEYSTORE_PASSWORD` and
`KEY_PASSWORD` locally, and `APKSIGNER` to your installed build-tools executable:

```bash
export RELEASE_KEYSTORE="$HOME/.android-keys/messages.jks"
export APKSIGNER="$ANDROID_HOME/build-tools/36.0.0/apksigner"
# Set the two password variables securely in your own environment first.
bash tools/build-signed-release.sh
```

The helper refuses missing signing inputs, builds the existing release variant,
and verifies `app/build/outputs/apk/release/app-release.apk`. Without signing
inputs, direct Gradle release builds may be unsigned. **No signed APK has been
built or verified in this sandbox.**

## Features

- **Real SMS + MMS**: Send/receive SMS with multi-SIM support; imports and displays MMS (text + photos) from the system provider
- **Google Messages UI**: Material 3 design, dark/light themes, conversation avatars, animated message bubbles
- **Backup & Restore**: PIN-encrypted backup/restore with a chosen save location (including external SD cards)
- **Message Management**: Pin, archive, delete, block numbers, trash with 30-day auto-purge
- **Drafts**: Auto-save drafts, restore on conversation open
- **Scheduled Messages**: Long-press send to schedule messages with DatePicker + TimePicker
- **Quick Reply**: Reply directly from notifications
- **Message Lock**: Biometric-protect sensitive messages
- **OTP Highlighting**: One-time passwords automatically highlighted in blue
- **Contact Photos**: Loads real contact profile pictures
- **Delayed Sending**: Configurable delay before sending messages
- **Work Profile Contacts**: Search contacts in both the personal and work (managed) profile; work contacts are shown with a briefcase badge in the picker, home list, and chat header
- **Accessibility Mode**: TalkBack descriptions, high-contrast themes, larger text and touch targets, and reduced motion

## Screenshots

| Conversations | Chat | Contact details | Reactions |
|---|---|---|---|
| <img src="fastlane/metadata/android/en-US/images/phoneScreenshots/01-home.png" alt="Conversations" width="160" height="356"> | <img src="fastlane/metadata/android/en-US/images/phoneScreenshots/03-chat.png" alt="Chat" width="160" height="356"> | <img src="fastlane/metadata/android/en-US/images/phoneScreenshots/04-contact.png" alt="Contact details" width="160" height="356"> | <img src="fastlane/metadata/android/en-US/images/phoneScreenshots/05-reaction.png" alt="Reactions" width="160" height="356"> |

| Typing | SIM switcher | Settings | New chat |
|---|---|---|---|
| <img src="fastlane/metadata/android/en-US/images/phoneScreenshots/06-typing.png" alt="Typing" width="160" height="356"> | <img src="fastlane/metadata/android/en-US/images/phoneScreenshots/07-sim-switcher.png" alt="SIM switcher" width="160" height="356"> | <img src="fastlane/metadata/android/en-US/images/phoneScreenshots/02-settings.png" alt="Settings" width="160" height="356"> | <img src="fastlane/metadata/android/en-US/images/phoneScreenshots/08-new-chat.png" alt="New chat" width="160" height="356"> |

## Download

### GitHub Releases
<a href="https://github.com/an1ndra/Messages/releases/latest"><img src="docs/get-it-on-github.png" alt="Get it on GitHub" height="80"></a>

Download the latest APK directly from [GitHub Releases](https://github.com/an1ndra/Messages/releases/latest) — no store account needed. Every release is scanned with VirusTotal (report posted on the release page).

### F-Droid
<a href="https://f-droid.org/en/packages/com.anindra.messages/"><img src="docs/get-it-on-fdroid.png" alt="Get it on F-Droid" height="80"></a>

F-Droid builds the app from source and signs it with the F-Droid project key.

## Requirements

- Android 10 (API 29) or higher
- SMS/MMS permissions (send, receive, read, MMS/WAP push)
- Contact permission (READ_CONTACTS)
- Notification permission (Android 13+), phone state (dual-SIM), and photo access (attachments)
- No internet permission

## Technical Details

- **Package**: `com.anindra.messages`
- **Min SDK**: 29 (Android 10)
- **Compile / Target SDK**: 36 (Android 16)
- **Database**: SQLite with Flow-based reactive queries
- **Architecture**: Single-Activity, manual `navRoute` state (no Navigation-Compose)

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Contributing

See [docs/Developer.md](docs/Developer.md) for development setup instructions.
