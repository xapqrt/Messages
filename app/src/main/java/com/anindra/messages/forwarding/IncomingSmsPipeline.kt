package com.anindra.messages.forwarding

internal object IncomingSmsPipeline {
    fun deliver(isDefault: Boolean, persist: () -> Unit, forward: () -> Unit, onForwardError: () -> Unit = {}): Boolean {
        if (!isDefault) return false
        persist()
        try { forward() } catch (_: Exception) { onForwardError() }
        return true
    }
}
