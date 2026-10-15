#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
: "${JAVA_HOME:?Set JAVA_HOME to a Java 17+ runtime}"
: "${KOTLIN_HOME:?Set KOTLIN_HOME to a Kotlin 2.2.20 compiler distribution}"
: "${JUNIT_JAR:?Set JUNIT_JAR to JUnit 4.13.2}"
: "${HAMCREST_JAR:?Set HAMCREST_JAR to Hamcrest core 1.3}"
: "${RE2J_JAR:?Set RE2J_JAR to a jar containing com.google.re2j}"
TMP_OUT="$(mktemp -d)"
trap 'rm -rf "$TMP_OUT"' EXIT
CP="$JUNIT_JAR:$HAMCREST_JAR:$RE2J_JAR"
SOURCES=(
    "$ROOT/app/src/main/java/com/anindra/messages/forwarding/ForwardingRule.kt"
    "$ROOT/app/src/main/java/com/anindra/messages/forwarding/IncomingSmsPipeline.kt"
    "$ROOT/app/src/main/java/com/anindra/messages/forwarding/IncomingSim.kt"
    "$ROOT/app/src/test/java/com/anindra/messages/forwarding/RuleEngineTest.kt"
    "$ROOT/app/src/test/java/com/anindra/messages/forwarding/IncomingSmsPipelineTest.kt"
    "$ROOT/app/src/test/java/com/anindra/messages/forwarding/IncomingSimTest.kt"
    "$ROOT/app/src/test/java/com/anindra/messages/forwarding/ForwardingIntegrationContractTest.kt"
    "$ROOT/app/src/test/java/com/anindra/messages/ui/previews/PreviewCoverageTest.kt"
    "$ROOT/app/src/test/java/com/anindra/messages/ui/previews/PreviewPlacementTest.kt"
    "$ROOT/app/src/test/java/com/anindra/messages/ui/NavTransitionDepthTest.kt"
    "$ROOT/app/src/test/java/com/anindra/messages/i18n/LocaleCatalog.kt"
    "$ROOT/app/src/test/java/com/anindra/messages/i18n/TranslationParityTest.kt"
)
TESTS=(
    com.anindra.messages.forwarding.RuleEngineTest
    com.anindra.messages.forwarding.IncomingSmsPipelineTest
    com.anindra.messages.forwarding.IncomingSimTest
    com.anindra.messages.forwarding.ForwardingIntegrationContractTest
    com.anindra.messages.ui.previews.PreviewCoverageTest
    com.anindra.messages.ui.previews.PreviewPlacementTest
    com.anindra.messages.ui.NavTransitionDepthTest
    com.anindra.messages.i18n.TranslationParityTest
)
if [[ -n "${JSON_JAR:-}" ]]; then
    CP="$CP:$JSON_JAR"
    SOURCES+=("$ROOT/app/src/main/java/com/anindra/messages/forwarding/ForwardingCodec.kt"
        "$ROOT/app/src/test/java/com/anindra/messages/forwarding/ForwardingCodecTest.kt")
    TESTS+=(com.anindra.messages.forwarding.ForwardingCodecTest)
fi
"$KOTLIN_HOME/bin/kotlinc" "${SOURCES[@]}" -cp "$CP" -d "$TMP_OUT/tests.jar"
cd "$ROOT/app"
"$JAVA_HOME/bin/java" -cp "$TMP_OUT/tests.jar:$CP:$KOTLIN_HOME/lib/kotlin-stdlib.jar" org.junit.runner.JUnitCore "${TESTS[@]}"
