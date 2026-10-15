package com.anindra.messages.display

import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.unit.LayoutDirection
import com.anindra.messages.data.Message
import com.anindra.messages.ui.ChatBubble
import com.anindra.messages.ui.theme.MessagesTheme
import org.junit.Rule
import org.junit.Test

class ResultDisplayUiTest {
    @get:Rule val compose = createComposeRule()

    private fun showBubble(sender: String = "VMCPAT-S", direction: LayoutDirection = LayoutDirection.Ltr, locked: Boolean = false) {
        compose.setContent {
            CompositionLocalProvider(LocalLayoutDirection provides direction) {
                MessagesTheme {
                    ChatBubble(
                        msg = Message(1, 1, "Arbitrary incoming message", 0, false, "received", locked = locked, address = sender),
                        showTime = false, onTap = {}, deliveryReports = false, highlightLinks = false,
                        linkWarningEnabled = false, hideLinks = false, isUnlocked = false, showSimIndicator = false
                    )
                }
            }
        }
    }

    @Test fun anyIncomingBodyFromTargetHasReplacementAndLabelOnly() {
        showBubble()
        compose.onNodeWithText(ResultDisplay.REPLACEMENT).assertIsDisplayed()
        compose.onNodeWithText("Modified display").assertIsDisplayed()
        compose.onNodeWithText("View original SMS").assertDoesNotExist()
        compose.onNodeWithText("Arbitrary incoming message").assertDoesNotExist()
    }
    @Test fun rtlHasTheSameLiteralReplacement() {
        showBubble(direction = LayoutDirection.Rtl)
        compose.onNodeWithText(ResultDisplay.REPLACEMENT).assertIsDisplayed()
        compose.onNodeWithText("Modified display").assertIsDisplayed()
    }
    @Test fun otherSenderRemainsUnchanged() {
        showBubble(sender = "OTHER-S")
        compose.onNodeWithText("Arbitrary incoming message").assertIsDisplayed()
        compose.onNodeWithText("Modified display").assertDoesNotExist()
    }
    @Test fun lockedMessageDoesNotExposeReplacement() {
        showBubble(locked = true)
        compose.onNodeWithText(ResultDisplay.REPLACEMENT).assertDoesNotExist()
        compose.onNodeWithText("Modified display").assertDoesNotExist()
    }
    @Test fun newlyArrivingTargetMessageUpdatesWithoutReopening() {
        val sender = mutableStateOf("OTHER-S")
        compose.setContent {
            MessagesTheme {
                ChatBubble(Message(1, 1, "No result template needed", 0, false, "received", address = sender.value),
                    showTime = false, onTap = {}, deliveryReports = false, highlightLinks = false,
                    linkWarningEnabled = false, hideLinks = false, isUnlocked = false, showSimIndicator = false)
            }
        }
        compose.onNodeWithText("Modified display").assertDoesNotExist()
        compose.runOnIdle { sender.value = "VMCPAT-S" }
        compose.onNodeWithText(ResultDisplay.REPLACEMENT).assertIsDisplayed()
    }
}
