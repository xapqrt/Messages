#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
: "${RELEASE_KEYSTORE:?Set RELEASE_KEYSTORE to an absolute path outside this repository}"
: "${KEYSTORE_PASSWORD:?Set KEYSTORE_PASSWORD in your local environment}"
: "${KEY_PASSWORD:?Set KEY_PASSWORD in your local environment}"
: "${APKSIGNER:?Set APKSIGNER to your Android build-tools apksigner executable}"
[[ "$RELEASE_KEYSTORE" = /* && -f "$RELEASE_KEYSTORE" ]] || { echo 'Keystore must exist at an absolute path' >&2; exit 1; }
[[ -x "$APKSIGNER" ]] || { echo 'apksigner executable not found' >&2; exit 1; }
cd "$ROOT"
./gradlew --no-daemon :app:assembleRelease
APK="$ROOT/app/build/outputs/apk/release/app-release.apk"
[[ -f "$APK" ]] || { echo 'Signed APK was not produced' >&2; exit 1; }
"$APKSIGNER" verify --verbose "$APK"
printf 'Verified signed APK: %s\n' "$APK"
