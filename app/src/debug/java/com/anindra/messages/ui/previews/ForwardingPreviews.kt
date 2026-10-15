package com.anindra.messages.ui.previews

import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.PreviewLightDark
import com.anindra.messages.forwarding.*
import com.anindra.messages.ui.theme.MessagesTheme

@PreviewLightDark
@Composable
private fun ForwardingSettingsPreview() {
    MessagesTheme {
        ForwardingContent(
            state = ForwardingUiState(config = ForwardingConfig(rules = listOf(
                ForwardingRule(1, "Keep family local", priority = 100, matchType = MatchType.SENDER_EXACT, matchValue = "+15551234567"),
                ForwardingRule(2, "Copy other SMS", action = RuleAction.FORWARD, targetNumber = "+15559876543")
            )), ready = true, busy = false),
            onSaveRules = {}, onEnable = {}, onStop = {}, onRefresh = {}, onBack = {},
            onPermissions = {}, onRole = {}, onNotificationSettings = {}, onBatterySettings = {}
        )
    }
}

@PreviewLightDark
@Composable
private fun ForwardingBannerPreview() { MessagesTheme { ForwardingBanner(true, {}, {}) } }

@PreviewLightDark
@Composable
private fun ForwardingEditorPreview() { MessagesTheme { ForwardingRuleEditor(ForwardingRule(1, "Example"), {}, {}) } }

@PreviewLightDark
@Composable
private fun ForwardingPresetPreview() { MessagesTheme { ForwardingPreset({}, {}) } }

@PreviewLightDark
@Composable
private fun ForwardingChoicePreview() { MessagesTheme { ForwardingChoice("Match", listOf("All SMS", "Sender"), 0, {}) } }
