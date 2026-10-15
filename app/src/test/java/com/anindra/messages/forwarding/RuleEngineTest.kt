package com.anindra.messages.forwarding

import org.junit.Assert.*
import org.junit.Test

class RuleEngineTest {
    private val sms = IncomingSms("+15551234567", "Hello Alice", 0, 7, 1)
    private val forward = ForwardingRule(2, "Copy", action = RuleAction.FORWARD, targetNumber = "+15559876543")
    private val keep = ForwardingRule(1, "Exclude", priority = 100, matchType = MatchType.SENDER_EXACT, matchValue = sms.sender)

    @Test fun exclusionBeatsCatchAllRegardlessOfInputOrder() {
        assertEquals(keep, RuleEngine.match(listOf(forward, keep), sms))
        assertNull(RuleEngine.decide(ForwardingConfig(true, listOf(forward, keep)), sms))
    }
    @Test fun firstMatchWinsWithoutCascading() {
        assertEquals(forward.copy(priority = 101), RuleEngine.match(listOf(keep, forward.copy(priority = 101)), sms))
    }
    @Test fun tiesAreDeterministic() {
        assertEquals(1L, RuleEngine.match(listOf(forward, keep.copy(priority = 0)), sms)?.id)
    }
    @Test fun disabledRulesAreIgnored() {
        assertEquals(forward, RuleEngine.match(listOf(keep.copy(isEnabled = false), forward), sms))
    }
    @Test fun disabledMasterAndNoMatchKeepLocal() {
        assertNull(RuleEngine.decide(ForwardingConfig(false, listOf(forward)), sms))
        assertNull(RuleEngine.decide(ForwardingConfig(true, listOf(keep)), sms.copy(sender = "other")))
    }
    @Test fun containsMatchesAreCaseInsensitive() {
        assertNotNull(RuleEngine.match(listOf(keep.copy(matchType = MatchType.BODY_CONTAINS, matchValue = "ALICE")), sms))
        assertNotNull(RuleEngine.match(listOf(keep.copy(matchType = MatchType.SENDER_CONTAINS, matchValue = "BANK")), sms.copy(sender = "vm-bank")))
    }
    @Test fun senderFormattingIsNormalized() {
        assertNotNull(RuleEngine.match(listOf(keep.copy(matchValue = "+1 (555) 123-4567")), sms))
    }
    @Test fun runtimeMayUseRegionAwareIdentity() {
        assertNotNull(RuleEngine.match(listOf(keep.copy(matchValue = "local")), sms) { "+15551234567" })
    }
    @Test fun regexMatchesBodyAndInvalidRegexFailsClosed() {
        assertNotNull(RuleEngine.match(listOf(keep.copy(matchType = MatchType.REGEX, matchValue = "Hello [A-Z]")), sms))
        assertNull(RuleEngine.match(listOf(keep.copy(matchType = MatchType.REGEX, matchValue = "[")), sms))
        assertFalse(RuleEngine.valid(keep.copy(matchType = MatchType.REGEX, matchValue = "(?=secret)")))
    }
    @Test fun simSlotIsNotSubscriptionId() {
        assertEquals(forward, RuleEngine.match(listOf(keep.copy(applyToSimSlot = 7), forward), sms))
        assertEquals(keep.copy(applyToSimSlot = 1), RuleEngine.match(listOf(keep.copy(applyToSimSlot = 1), forward), sms))
    }
    @Test fun allPlaceholdersExpandWithoutChangingOriginalBody() {
        val rule = forward.copy(modifyBody = true, bodyPrefix = "{sender}|{timestamp}|{sim}|", bodySuffix = "|{original}")
        assertEquals("+15551234567|1970-01-01T00:00:00Z|2|Hello Alice|Hello Alice", RuleEngine.transform(rule, sms))
    }
    @Test fun substitutionsAreNotRecursiveAndNeverTouchBodyTokens() {
        val rule = forward.copy(modifyBody = true, bodyPrefix = "{original}:")
        assertEquals("{sender}:{sender}", RuleEngine.transform(rule, sms.copy(body = "{sender}")))
    }
    @Test fun disabledTransformationIsUnchanged() {
        assertEquals(sms.body, RuleEngine.transform(forward.copy(bodyPrefix = "ignored"), sms))
    }
    @Test fun copyMarkerAndLoopChecksProtectBothDirections() {
        val config = ForwardingConfig(true, listOf(forward))
        assertTrue(RuleEngine.decide(config, sms)!!.body.startsWith(RuleEngine.COPY_MARKER))
        assertTrue(RuleEngine.loopRisk(config, sms.copy(body = RuleEngine.COPY_MARKER + sms.body)))
        assertTrue(RuleEngine.loopRisk(config, sms.copy(sender = forward.targetNumber)))
        assertFalse(RuleEngine.loopRisk(config, sms))
    }
    @Test fun malformedConfigNeverForwards() {
        assertFalse(RuleEngine.valid(forward.copy(targetNumber = "112")))
        assertFalse(RuleEngine.valid(keep.copy(matchValue = "")))
        assertFalse(RuleEngine.valid(keep.copy(matchType = MatchType.SENDER_CONTAINS, matchValue = "---")))
        assertFalse(RuleEngine.valid(ForwardingConfig(true, listOf(forward, forward))))
        assertNull(RuleEngine.decide(ForwardingConfig(true, listOf(forward.copy(targetNumber = "bad"))), sms))
    }
    @Test fun regexDoesNotBacktrackExponentially() {
        val rule = keep.copy(matchType = MatchType.REGEX, matchValue = "(a+)+$")
        assertNull(RuleEngine.match(listOf(rule), sms.copy(body = "a".repeat(10000) + "!")))
    }
}
