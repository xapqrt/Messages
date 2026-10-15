package com.anindra.messages.forwarding

import org.junit.Assert.*
import org.junit.Test

class ForwardingCodecTest {
    @Test fun roundTripPreservesEveryRuleField() {
        val config = ForwardingConfig(true, listOf(ForwardingRule(42, "Test", false, 123, MatchType.REGEX,
            "hello.*", RuleAction.FORWARD, "+15551234567", true, "{sender}", "{original}", 1, 0)))
        assertEquals(config, ForwardingCodec.decode(ForwardingCodec.encode(config)))
    }
    @Test fun unknownVersionAndInvalidPayloadAreRejected() {
        assertThrows(Exception::class.java) { ForwardingCodec.decode("{}") }
        assertThrows(Exception::class.java) { ForwardingCodec.decode("""{"version":2,"enabled":false,"rules":[]}""") }
    }
    @Test fun malformedTargetsCannotBeRestoredEnabled() {
        val invalid = ForwardingConfig(true, listOf(ForwardingRule(1, "bad", action = RuleAction.FORWARD, targetNumber = "112")))
        assertThrows(Exception::class.java) { ForwardingCodec.decode(ForwardingCodec.encode(invalid)) }
    }
}
