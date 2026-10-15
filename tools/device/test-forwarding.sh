#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"

PASS=0 FAIL=0
pass() { PASS=$((PASS + 1)); printf '[PASS] %s\n' "$*"; }
fail() { FAIL=$((FAIL + 1)); printf '[FAIL] %s\n' "$*"; }

# UI-only: never enables forwarding or sends a real SMS.
adb_ get-state >/dev/null
adb_ shell am start -W -n "$ACT" --ez open_settings true >/dev/null
dump_ui
if grep -q 'text="SMS forwarding"' "$TMP/ui.xml"; then
    pass 'Forwarding is visibly accessible from settings'
else
    fail 'Missing visible SMS forwarding settings entry (run with English app language)'
    exit 1
fi
tap_text 'SMS forwarding'
dump_ui
if grep -q 'text="SMS forwarding"' "$TMP/ui.xml" && grep -q 'Originals remain in Messages' "$TMP/ui.xml"; then
    pass 'Forwarding screen explains local retention'
else
    fail 'Forwarding screen missing or retention disclosure absent'
fi
if grep -q 'text="Two-rule setup"' "$TMP/ui.xml"; then
    tap_text 'Two-rule setup'
    dump_ui
    grep -q 'text="Excluded sender"' "$TMP/ui.xml" && pass 'Exclusion field shown' || fail 'Exclusion field missing'
    grep -q 'text="Destination (+country code)"' "$TMP/ui.xml" && pass 'Destination field shown' || fail 'Destination field missing'
    tap_text 'Cancel'
else
    fail 'Two-rule setup not visible; verify default-role/permission prerequisites first'
fi
adb_ shell input keyevent KEYCODE_BACK
printf '\n%s passed, %s failed\n' "$PASS" "$FAIL"
exit $((FAIL > 0))
