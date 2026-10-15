package com.anindra.messages.forwarding

import java.io.File
import org.junit.Assert.*
import org.junit.Test

class ForwardingIntegrationContractTest {
    private val root = generateSequence(File("").absoluteFile) { it.parentFile }.first { File(it, "app/src/main").isDirectory }
    private fun source(path: String) = File(root, "app/src/main/$path").readText()

    @Test fun receiverIsDeliverOnlyAndRejectsNonDefaultBeforeGoingAsync() {
        val receiver = source("java/com/anindra/messages/sms/SmsReceiver.kt")
        assertFalse(receiver.contains("SMS_RECEIVED_ACTION"))
        assertTrue(receiver.indexOf("getDefaultSmsPackage") < receiver.indexOf("goAsync()"))
        assertTrue(receiver.contains("IncomingSmsPipeline.deliver"))
        assertTrue(receiver.contains("pendingResult.finish()"))
    }
    @Test fun forwardingControlsAreVisibleInBothSettingsVariants() {
        for (file in listOf("ui/SettingsScreen.kt", "ui/legacy/LegacySettingsScreen.kt")) {
            val text = source("java/com/anindra/messages/$file")
            assertTrue(text.contains("onClick = onOpenForwarding"))
            assertTrue(text.contains("R.string.forward_title"))
        }
        val main = source("java/com/anindra/messages/MainActivity.kt")
        assertTrue(main.contains("ForwardingBanner("))
        assertTrue(main.contains("\"forwarding\" to 2"))
    }
    @Test fun manifestPreservesRoleEligibilityAndDoesNotExposeControlReceivers() {
        val manifest = source("AndroidManifest.xml")
        listOf("SMS_DELIVER", "WAP_PUSH_DELIVER", "RESPOND_VIA_MESSAGE", "SENDTO", "text/plain").forEach {
            assertTrue(it, manifest.contains(it))
        }
        assertFalse(manifest.contains("android.permission.INTERNET"))
        listOf("ForwardingSentReceiver", "StopForwardingReceiver").forEach {
            assertTrue(manifest.contains(".forwarding.$it\" android:exported=\"false\""))
        }
    }
    @Test fun metadataHasNoBodyAndCopiesCannotDropOriginals() {
        val store = source("java/com/anindra/messages/forwarding/ForwardingStore.kt")
        assertFalse(store.contains("body TEXT"))
        val rules = source("java/com/anindra/messages/forwarding/ForwardingRule.kt")
        assertFalse(rules.contains("DROP"))
        assertFalse(rules.contains("deleteAfterForward"))
    }
}
