package com.anindra.messages.display

object ResultDisplay {
    const val SENDER = "VMCPAT-S"
    const val REPLACEMENT = "Dear VIVAAN PANDEY, Your JEE MAIN-03 result has been declared Marks in Phy- 30 Che- 24 Maths- 22 Total- 66 Rank- 639. Regards, VMC Patna"

    fun replacement(
        sender: String,
        fallbackSender: String = "",
        isIncoming: Boolean = true,
        isSms: Boolean = true,
        isLocked: Boolean = false
    ): String? {
        if (!isIncoming || !isSms || isLocked) return null
        val address = sender.ifBlank { fallbackSender }.trim()
        return REPLACEMENT.takeIf { address.equals(SENDER, ignoreCase = true) }
    }
}
