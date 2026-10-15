#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
: "${JAVA_HOME:?Set JAVA_HOME to a Java 17+ runtime}"
: "${KOTLIN_HOME:?Set KOTLIN_HOME to a Kotlin 2.2.20 compiler distribution}"
: "${JUNIT_JAR:?Set JUNIT_JAR to JUnit 4.13.2}"
: "${HAMCREST_JAR:?Set HAMCREST_JAR to Hamcrest core 1.3}"
TMP_OUT="$(mktemp -d)"
trap 'rm -rf "$TMP_OUT"' EXIT
CP="$JUNIT_JAR:$HAMCREST_JAR"
SOURCES=(
    "$ROOT/app/src/main/java/com/anindra/messages/display/ResultDisplay.kt"
    "$ROOT/app/src/test/java/com/anindra/messages/display/ResultDisplayTest.kt"
    "$ROOT/app/src/test/java/com/anindra/messages/display/ResultDisplayIntegrationTest.kt"
    "$ROOT/app/src/test/java/com/anindra/messages/ui/previews/PreviewCoverageTest.kt"
    "$ROOT/app/src/test/java/com/anindra/messages/ui/previews/PreviewPlacementTest.kt"
    "$ROOT/app/src/test/java/com/anindra/messages/ui/NavTransitionDepthTest.kt"
    "$ROOT/app/src/test/java/com/anindra/messages/i18n/LocaleCatalog.kt"
    "$ROOT/app/src/test/java/com/anindra/messages/i18n/TranslationParityTest.kt"
)
TESTS=(
    com.anindra.messages.display.ResultDisplayTest
    com.anindra.messages.display.ResultDisplayIntegrationTest
    com.anindra.messages.ui.previews.PreviewCoverageTest
    com.anindra.messages.ui.previews.PreviewPlacementTest
    com.anindra.messages.ui.NavTransitionDepthTest
    com.anindra.messages.i18n.TranslationParityTest
)
"$KOTLIN_HOME/bin/kotlinc" "${SOURCES[@]}" -cp "$CP" -d "$TMP_OUT/tests.jar"
cd "$ROOT/app"
"$JAVA_HOME/bin/java" -cp "$TMP_OUT/tests.jar:$CP:$KOTLIN_HOME/lib/kotlin-stdlib.jar" org.junit.runner.JUnitCore "${TESTS[@]}"
