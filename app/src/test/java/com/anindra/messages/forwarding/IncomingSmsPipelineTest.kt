package com.anindra.messages.forwarding

import org.junit.Assert.*
import org.junit.Test

class IncomingSmsPipelineTest {
    @Test fun notDefaultIsNoOp() {
        assertFalse(IncomingSmsPipeline.deliver(false, { error("must not persist") }, { error("must not send") }))
    }
    @Test fun originalAlwaysPrecedesCopy() {
        val events = mutableListOf<String>()
        assertTrue(IncomingSmsPipeline.deliver(true, { events += "local" }, { events += "copy" }))
        assertEquals(listOf("local", "copy"), events)
    }
    @Test fun failedForwardingDoesNotUndoLocalDelivery() {
        var retained = false
        var reported = false
        assertTrue(IncomingSmsPipeline.deliver(true, { retained = true }, { throw IllegalStateException() }, { reported = true }))
        assertTrue(retained)
        assertTrue(reported)
    }
    @Test fun failedPersistenceNeverForwards() {
        var sent = false
        assertThrows(IllegalStateException::class.java) {
            IncomingSmsPipeline.deliver(true, { throw IllegalStateException() }, { sent = true })
        }
        assertFalse(sent)
    }
}
