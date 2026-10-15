#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"

PASS=0 FAIL=0
pass() { PASS=$((PASS + 1)); printf '[PASS] %s\n' "$*"; }
fail() { FAIL=$((FAIL + 1)); printf '[FAIL] %s\n' "$*"; }

# Only test fixtures are displayed; no SMS is sent or overwritten.
adb_ get-state >/dev/null
adb_ shell am start -W -n "$ACT" --ez open_settings true >/dev/null
dump_ui
if ! grep -q 'text="SMS forwarding"' "$TMP/ui.xml"; then
    fail 'Expected current settings screen (use English app language)'
    exit 1
fi
if grep -q 'text="Result display"' "$TMP/ui.xml"; then
    fail 'Removed result-display settings entry is still present'
else
    pass 'No result-display editor in settings'
fi
adb_ shell input keyevent KEYCODE_BACK

if ! adb_ shell pm path "$PKG.test" | grep -q '^package:'; then
    fail 'Install the debug Android test APK before running this script'
    exit 1
fi
OUTPUT="$(mktemp)"
trap 'rm -f "$OUTPUT"' EXIT
adb_ shell am instrument -w -r -e class com.anindra.messages.display.ResultDisplayUiTest \
    "$PKG.test/androidx.test.runner.AndroidJUnitRunner" >"$OUTPUT"
cat "$OUTPUT"
if grep -q 'OK (5 tests)' "$OUTPUT" && ! grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED' "$OUTPUT"; then
    pass 'Sender replacement, label, RTL, non-match, lock and reactive update checks'
else
    fail 'Connected sender-display tests did not all pass'
fi
printf '\n%s passed, %s failed\n' "$PASS" "$FAIL"
exit $((FAIL > 0))
