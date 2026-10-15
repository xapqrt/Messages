package com.anindra.messages.forwarding

import org.junit.Assert.assertEquals
import org.junit.Test

class IncomingSimTest {
    @Test fun subscriptionZeroIsValid() { assertEquals(0, IncomingSim.subscription(0, 7, 1, mapOf(1 to 42))) }
    @Test fun invalidPrimaryFallsBackToAlternate() { assertEquals(7, IncomingSim.subscription(-1, 7, 1, mapOf(1 to 42))) }
    @Test fun slotIsResolvedNotTreatedAsSubscription() { assertEquals(42, IncomingSim.subscription(-1, -1, 1, mapOf(1 to 42))) }
    @Test fun unknownNeverSilentlySelectsAnotherSim() { assertEquals(-1, IncomingSim.subscription(-1, -1, 0, mapOf(1 to 42))) }
}
