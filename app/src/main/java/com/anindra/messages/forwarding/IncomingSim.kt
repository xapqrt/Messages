package com.anindra.messages.forwarding

internal object IncomingSim {
    fun subscription(primary: Int, alternate: Int, slot: Int, subscriptionsBySlot: Map<Int, Int>): Int =
        when {
            primary >= 0 -> primary
            alternate >= 0 -> alternate
            slot >= 0 -> subscriptionsBySlot[slot] ?: -1
            else -> -1
        }
}
