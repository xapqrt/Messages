package com.anindra.messages.forwarding

import org.json.JSONArray
import org.json.JSONObject

internal object ForwardingCodec {
    fun encode(config: ForwardingConfig): String = JSONObject().apply {
        put("version", 1)
        put("enabled", config.enabled)
        put("rules", JSONArray().apply {
            config.rules.forEach { r -> put(JSONObject().apply {
                put("id", r.id); put("name", r.name); put("enabled", r.isEnabled); put("priority", r.priority)
                put("matchType", r.matchType.name); put("matchValue", r.matchValue); put("action", r.action.name)
                put("target", r.targetNumber); put("modify", r.modifyBody); put("prefix", r.bodyPrefix); put("suffix", r.bodySuffix)
                put("incomingSlot", r.applyToSimSlot); put("outgoingSlot", r.outgoingSimSlot)
            }) }
        })
    }.toString()

    fun decode(text: String): ForwardingConfig {
        val json = JSONObject(text)
        require(json.getInt("version") == 1)
        val array = json.getJSONArray("rules")
        require(array.length() <= 50)
        val config = ForwardingConfig(json.getBoolean("enabled"), List(array.length()) { index ->
            val r = array.getJSONObject(index)
            ForwardingRule(
                id = r.getLong("id"), name = r.getString("name"), isEnabled = r.getBoolean("enabled"),
                priority = r.getInt("priority"), matchType = MatchType.valueOf(r.getString("matchType")),
                matchValue = r.getString("matchValue"), action = RuleAction.valueOf(r.getString("action")),
                targetNumber = r.getString("target"), modifyBody = r.getBoolean("modify"),
                bodyPrefix = r.getString("prefix"), bodySuffix = r.getString("suffix"),
                applyToSimSlot = r.getInt("incomingSlot"), outgoingSimSlot = r.getInt("outgoingSlot")
            )
        })
        require(RuleEngine.valid(config))
        return config
    }
}
