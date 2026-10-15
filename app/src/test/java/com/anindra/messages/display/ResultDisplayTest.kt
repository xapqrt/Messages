package com.anindra.messages.display

import org.junit.Assert.*
import org.junit.Test

class ResultDisplayTest {
    private val expected = "Dear VIVAAN PANDEY, Your JEE MAIN-03 result has been declared Marks in Phy- 30 Che- 24 Maths- 22 Total- 66 Rank- 639. Regards, VMC Patna"

    @Test fun exactSenderGetsExactLiteralReplacement() {
        assertEquals(expected, ResultDisplay.replacement("VMCPAT-S"))
    }
    @Test fun senderCaseAndSurroundingWhitespaceAreNormalized() {
        assertEquals(expected, ResultDisplay.replacement("  vmcpat-s\n"))
    }
    @Test fun senderMatchIsNotContainsOrSuffix() {
        listOf("AD-VMCPAT-S", "VMCPAT-S-extra", "XVMCPAT-S", "VMCPAT", "VMCPAT S", "+919876543210").forEach {
            assertNull(it, ResultDisplay.replacement(it))
        }
    }
    @Test fun blankSenderWithoutKnownConversationStaysOriginal() {
        assertNull(ResultDisplay.replacement(""))
        assertNull(ResultDisplay.replacement("   "))
    }
    @Test fun arbitraryIncomingBodiesUseTheSameReplacement() {
        listOf("New exam result", "Class cancelled", "Your code is 613", "", "x".repeat(10000)).forEach { original ->
            val displayed = ResultDisplay.replacement("VMCPAT-S") ?: original
            assertEquals(expected, displayed)
        }
    }
    @Test fun otherSendersKeepArbitraryBodies() {
        val original = "An unrelated message"
        assertEquals(original, ResultDisplay.replacement("OTHER-S") ?: original)
    }
    @Test fun outgoingMessagesAreNeverReplaced() {
        assertNull(ResultDisplay.replacement("VMCPAT-S", isIncoming = false))
    }
    @Test fun mmsBubblesAreNeverReplaced() {
        assertNull(ResultDisplay.replacement("VMCPAT-S", isSms = false))
    }
    @Test fun lockedBodiesNeverExposeReplacement() {
        assertNull(ResultDisplay.replacement("VMCPAT-S", isLocked = true))
    }
    @Test fun blankMessageSenderCanUseSingleRecipientConversationAddress() {
        assertEquals(expected, ResultDisplay.replacement("", fallbackSender = "VMCPAT-S"))
    }
    @Test fun knownMessageSenderAlwaysWinsOverConversationFallback() {
        assertNull(ResultDisplay.replacement("OTHER-S", fallbackSender = "VMCPAT-S"))
        assertEquals(expected, ResultDisplay.replacement("VMCPAT-S", fallbackSender = "OTHER-S"))
    }
    @Test fun suppliedNumbersAreLiteralNotRecalculated() {
        assertTrue(ResultDisplay.REPLACEMENT.contains("Che- 24"))
        assertTrue(ResultDisplay.REPLACEMENT.contains("Total- 66"))
        assertFalse(ResultDisplay.REPLACEMENT.contains('\n'))
    }
}
