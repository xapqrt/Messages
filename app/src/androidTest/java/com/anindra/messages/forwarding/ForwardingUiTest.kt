package com.anindra.messages.forwarding

import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.unit.LayoutDirection
import com.anindra.messages.ui.theme.MessagesTheme
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

class ForwardingUiTest {
    @get:Rule val compose = createComposeRule()
    private val config = ForwardingConfig(rules = listOf(ForwardingRule(1, "Example", action = RuleAction.FORWARD, targetNumber = "+15551234567")))

    @Test fun enablingRequiresExplicitDestinationConfirmation() {
        var enabled = false
        compose.setContent {
            MessagesTheme { ForwardingContent(ForwardingUiState(config = config, ready = true, busy = false),
                {}, { enabled = true }, {}, {}, {}, {}, {}, {}, {}) }
        }
        compose.onNodeWithTag("forwarding-switch").performClick()
        compose.runOnIdle { assertFalse(enabled) }
        compose.onNodeWithText("Confirm and enable").performClick()
        compose.runOnIdle { assertTrue(enabled) }
    }
    @Test fun unmetPermissionsDisableEnableSwitch() {
        compose.setContent {
            MessagesTheme { ForwardingContent(ForwardingUiState(config = config, ready = false, busy = false),
                {}, {}, {}, {}, {}, {}, {}, {}, {}) }
        }
        compose.onNodeWithTag("forwarding-switch").assertIsNotEnabled()
    }
    @Test fun rtlBannerOffersImmediateStop() {
        var stopped = false
        compose.setContent {
            CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
                MessagesTheme { ForwardingBanner(true, {}, { stopped = true }) }
            }
        }
        compose.onNodeWithText("SMS forwarding is on").assertIsDisplayed()
        compose.onNodeWithText("Stop").performClick()
        compose.runOnIdle { assertTrue(stopped) }
    }
    @Test fun disabledForwardingHasNoActiveBanner() {
        compose.setContent { MessagesTheme { ForwardingBanner(false, {}, {}) } }
        compose.onNodeWithText("SMS forwarding is on").assertDoesNotExist()
    }
}
