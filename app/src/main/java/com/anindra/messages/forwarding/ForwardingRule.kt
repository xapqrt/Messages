package com.anindra.messages.forwarding

import com.google.re2j.Pattern
import java.time.Instant

enum class MatchType { ALL, SENDER_EXACT, SENDER_CONTAINS, BODY_CONTAINS, REGEX }
enum class RuleAction { FORWARD, KEEP_LOCAL }

data class ForwardingRule(
    val id: Long = 0,
    val name: String = "",
    val isEnabled: Boolean = true,
    val priority: Int = 0,
    val matchType: MatchType = MatchType.ALL,
    val matchValue: String = "",
    val action: RuleAction = RuleAction.KEEP_LOCAL,
    val targetNumber: String = "",
    val modifyBody: Boolean = false,
    val bodyPrefix: String = "",
    val bodySuffix: String = "",
    val applyToSimSlot: Int = -1,
    val outgoingSimSlot: Int = -1
)

data class ForwardingConfig(val enabled: Boolean = false, val rules: List<ForwardingRule> = emptyList())
data class IncomingSms(
    val sender: String,
    val body: String,
    val timestamp: Long,
    val subscriptionId: Int = -1,
    val simSlot: Int = -1
)

data class ForwardDecision(val rule: ForwardingRule, val body: String)

enum class ForwardStatus { RESERVED, SUBMITTED, SENT, FAILED, UNKNOWN, RATE_LIMITED, LOOP_BLOCKED }
data class ForwardLog(val token: String, val senderHash: String, val timestamp: Long, val ruleId: Long, val status: ForwardStatus)

object RuleEngine {
    const val COPY_MARKER = "[SMS copy] "
    private val placeholders = Regex("\\{(sender|timestamp|sim|original)\\}")
    private val internationalNumber = Regex("\\+[1-9][0-9]{7,14}")

    fun numberIdentity(value: String): String =
        if (value.any { it.isLetter() }) value.trim().lowercase(java.util.Locale.ROOT)
        else value.filter { it in '0'..'9' || it == '+' }

    fun valid(rule: ForwardingRule): Boolean =
        rule.id >= 0 && rule.name.isNotBlank() && rule.name.length <= 64 &&
            rule.applyToSimSlot in -1..7 && rule.outgoingSimSlot in -1..7 &&
            rule.matchValue.length <= 512 && rule.bodyPrefix.length <= 256 && rule.bodySuffix.length <= 256 &&
            (rule.matchType == MatchType.ALL || rule.matchValue.isNotBlank()) &&
            (rule.matchType !in listOf(MatchType.SENDER_EXACT, MatchType.SENDER_CONTAINS) || numberIdentity(rule.matchValue).isNotBlank()) &&
            (rule.action != RuleAction.FORWARD || internationalNumber.matches(rule.targetNumber)) &&
            (rule.matchType != MatchType.REGEX || runCatching { Pattern.compile(rule.matchValue) }.isSuccess)

    fun valid(config: ForwardingConfig): Boolean = config.rules.size <= 50 &&
        config.rules.all { valid(it) } && config.rules.map { it.id }.distinct().size == config.rules.size

    fun match(
        rules: List<ForwardingRule>, sms: IncomingSms,
        identity: (String) -> String = ::numberIdentity
    ): ForwardingRule? = rules.asSequence()
        .filter { it.isEnabled }
        .sortedWith(compareByDescending<ForwardingRule> { it.priority }.thenBy { it.id })
        .firstOrNull { rule ->
            (rule.applyToSimSlot == -1 || rule.applyToSimSlot == sms.simSlot) && when (rule.matchType) {
                MatchType.ALL -> true
                MatchType.SENDER_EXACT -> identity(sms.sender) == identity(rule.matchValue)
                MatchType.SENDER_CONTAINS -> rule.matchValue.isNotBlank() &&
                    identity(sms.sender).contains(identity(rule.matchValue))
                MatchType.BODY_CONTAINS -> rule.matchValue.isNotBlank() && sms.body.contains(rule.matchValue, ignoreCase = true)
                MatchType.REGEX -> runCatching { Pattern.compile(rule.matchValue).matcher(sms.body).find() }.getOrDefault(false)
            }
        }

    fun decide(config: ForwardingConfig, sms: IncomingSms, identity: (String) -> String = ::numberIdentity): ForwardDecision? {
        if (!config.enabled || !valid(config)) return null
        val rule = match(config.rules, sms, identity) ?: return null
        if (rule.action == RuleAction.KEEP_LOCAL) return null
        return ForwardDecision(rule, COPY_MARKER + transform(rule, sms))
    }

    fun loopRisk(config: ForwardingConfig, sms: IncomingSms, identity: (String) -> String = ::numberIdentity): Boolean =
        sms.body.startsWith(COPY_MARKER) || config.rules.any {
            it.isEnabled && it.action == RuleAction.FORWARD && identity(it.targetNumber) == identity(sms.sender)
        }

    fun transform(rule: ForwardingRule, sms: IncomingSms): String {
        if (!rule.modifyBody) return sms.body
        fun expand(template: String) = placeholders.replace(template) {
            when (it.groupValues[1]) {
                "sender" -> sms.sender
                "timestamp" -> Instant.ofEpochMilli(sms.timestamp).toString()
                "sim" -> if (sms.simSlot < 0) "?" else (sms.simSlot + 1).toString()
                else -> sms.body
            }
        }
        return expand(rule.bodyPrefix) + sms.body + expand(rule.bodySuffix)
    }
}
