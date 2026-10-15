package com.anindra.messages.ui.previews

import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.PreviewLightDark
import com.anindra.messages.data.Message
import com.anindra.messages.display.ResultDisplay
import com.anindra.messages.display.ResultDisplayNotice
import com.anindra.messages.ui.ChatBubble
import com.anindra.messages.ui.theme.MessagesTheme

@PreviewLightDark
@Composable
private fun ResultDisplayNoticePreview() {
    MessagesTheme { ResultDisplayNotice() }
}

@PreviewLightDark
@Composable
private fun ResultDisplayBubblePreview() {
    MessagesTheme {
        ChatBubble(Message(1, 1, "Any incoming SMS", 0, false, "received", address = ResultDisplay.SENDER),
            showTime = false, onTap = {}, deliveryReports = false, highlightLinks = false,
            linkWarningEnabled = false, hideLinks = false, isUnlocked = false, showSimIndicator = false)
    }
}
