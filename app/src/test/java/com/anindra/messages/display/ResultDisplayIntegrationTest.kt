package com.anindra.messages.display

import java.io.File
import org.junit.Assert.*
import org.junit.Test

class ResultDisplayIntegrationTest {
    private val main = generateSequence(File("").absoluteFile) { it.parentFile }
        .map { File(it, "app/src/main/java/com/anindra/messages") }.first { it.isDirectory }
    private fun source(path: String) = File(main, path).readText()

    @Test fun presentationNeverChangesStoredSentOrNotifiedBodies() {
        listOf("sms/SmsReceiver.kt", "data/Repository.kt", "forwarding/ForwardingRuntime.kt", "sms/SmsSupport.kt").forEach {
            assertFalse(it, source(it).contains("ResultDisplay"))
        }
    }
    @Test fun bothInboxVariantsMatchAddressNotContactName() {
        listOf("ui/ConversationsScreen.kt", "ui/legacy/LegacyConversationsScreen.kt").forEach {
            val code = source(it)
            assertTrue(code.contains("sender = convo.address"))
            assertTrue(code.contains("isIncoming = !convo.isMe && convo.groupTitle.isBlank()"))
            assertTrue(code.contains("R.string.result_display_custom"))
            assertFalse(code.contains("LocalResultDisplayRule"))
        }
    }
    @Test fun bubblesUseRawSenderAndRespectTransportAndLock() {
        val code = source("ui/ChatScreen.kt")
        assertEquals(2, Regex("ResultDisplayNotice\\(\\)").findAll(code).count())
        assertEquals(2, Regex("(?m)^\\s*sender = msg.address,").findAll(code).count())
        assertEquals(2, Regex("isSms = msg.transport == \"sms\"").findAll(code).count())
        assertEquals(2, Regex("isLocked = isLockedAndHidden").findAll(code).count())
        assertTrue(code.contains("else customBody ?: msg.body"))
        assertTrue(code.contains("fallbackSender = if (isGroupConversation) \"\" else convo?.address.orEmpty()"))
    }
    @Test fun settingsAndPreferencesAreRemoved() {
        assertFalse(source("MainActivity.kt").contains("\"result-display\""))
        assertFalse(source("data/SettingsStore.kt").contains("result_display_"))
        listOf("ui/SettingsScreen.kt", "ui/legacy/LegacySettingsScreen.kt").forEach {
            assertFalse(source(it).contains("onOpenResultDisplay"))
        }
        assertFalse(File(main, "display/ResultDisplaySettings.kt").exists())
    }
    @Test fun noticeIsLabelOnlyWithoutAnOriginalDialog() {
        val code = source("display/ResultDisplayUi.kt")
        assertTrue(code.contains("R.string.result_display_custom"))
        listOf("AlertDialog", "TextButton", "onClick", "showOriginal").forEach { assertFalse(code.contains(it)) }
    }
}
