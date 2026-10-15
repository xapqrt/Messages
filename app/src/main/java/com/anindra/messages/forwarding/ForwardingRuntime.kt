package com.anindra.messages.forwarding

import android.Manifest
import android.app.Activity
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.Telephony
import android.telephony.SmsManager
import android.telephony.SubscriptionManager
import androidx.core.app.NotificationManagerCompat
import com.anindra.messages.MessagesApplication
import com.anindra.messages.data.PhoneNumberUtils
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class ForwardingRuntime internal constructor(
    private val context: Context,
    internal val store: ForwardingStore = ForwardingStore(context),
    private val sender: SmsCopySender = AndroidSmsCopySender(context),
    private val readiness: (() -> Boolean)? = null,
    private val showStatus: (Boolean) -> Unit = { ForwardingNotification.update(context, it) },
    private val scheduleHealth: (Boolean) -> Unit = { ForwardingHealthWorker.schedule(context, it) }
) {
    val config = store.config
    private val dispatchLock = Any()

    fun isDefault(): Boolean = Telephony.Sms.getDefaultSmsPackage(context) == context.packageName

    fun ready(): Boolean = readiness?.invoke() ?: (isDefault() && listOf(
        Manifest.permission.SEND_SMS, Manifest.permission.RECEIVE_SMS,
        Manifest.permission.READ_SMS, Manifest.permission.READ_PHONE_STATE
    ).all { context.checkSelfPermission(it) == PackageManager.PERMISSION_GRANTED } &&
        NotificationManagerCompat.from(context).areNotificationsEnabled() && ForwardingNotification.channelEnabled(context))

    fun load(): ForwardingConfig = synchronized(dispatchLock) { store.load() }

    fun save(config: ForwardingConfig) = synchronized(dispatchLock) {
        require(!config.enabled || ready())
        require(!config.enabled || config.rules.any { it.isEnabled && it.action == RuleAction.FORWARD })
        store.save(config)
        showStatus(config.enabled)
        scheduleHealth(config.enabled)
    }

    fun stop() = synchronized(dispatchLock) {
        // Stop must still work when an encrypted configuration cannot be read.
        val config = runCatching { store.load() }.getOrDefault(ForwardingConfig())
        save(config.copy(enabled = false))
    }

    fun incoming(sms: IncomingSms) = synchronized(dispatchLock) {
        val config = store.load()
        if (!config.enabled) return
        if (!ready()) { stop(); return }
        val identity: (String) -> String = { PhoneNumberUtils.toE164(it, PhoneNumberUtils.region()) ?: RuleEngine.numberIdentity(it) }
        val decision = RuleEngine.decide(config, sms, identity) ?: return
        val token = ForwardingCrypto.hash("message\u0000${identity(sms.sender)}\u0000${sms.timestamp}\u0000${sms.subscriptionId}\u0000${sms.body}")
        val senderHash = ForwardingCrypto.hash("sender\u0000${identity(sms.sender)}")
        if (!store.reserve(token, senderHash, decision.rule.id, System.currentTimeMillis(), RuleEngine.loopRisk(config, sms, identity))) return
        try {
            showStatus(true)
            sender.send(sms, decision, token) { parts -> store.submitted(token, parts) }
        } catch (_: Exception) {
            store.failed(token)
        }
    }

    companion object {
        const val SENT_ACTION = "com.anindra.messages.FORWARD_SENT"
        fun get(context: Context) = (context.applicationContext as MessagesApplication).forwarding
    }
}

internal fun interface SmsCopySender {
    fun send(sms: IncomingSms, decision: ForwardDecision, token: String, onSubmitted: (Int) -> Unit)
}

internal class AndroidSmsCopySender(private val context: Context) : SmsCopySender {
    override fun send(sms: IncomingSms, decision: ForwardDecision, token: String, onSubmitted: (Int) -> Unit) {
        val subs = context.getSystemService(SubscriptionManager::class.java).activeSubscriptionInfoList.orEmpty()
        val subscription = if (decision.rule.outgoingSimSlot >= 0) {
            subs.firstOrNull { it.simSlotIndex == decision.rule.outgoingSimSlot }?.subscriptionId
        } else subs.firstOrNull { it.subscriptionId == sms.subscriptionId }?.subscriptionId
        require(subscription != null && SubscriptionManager.isValidSubscriptionId(subscription))
        @Suppress("DEPRECATION")
        val manager = SmsManager.getSmsManagerForSubscriptionId(subscription)
        val parts = manager.divideMessage(decision.body)
        require(parts.size in 1..10)
        onSubmitted(parts.size)
        val callbacks = ArrayList(parts.indices.map { part ->
            val intent = Intent(context, ForwardingSentReceiver::class.java).apply {
                action = ForwardingRuntime.SENT_ACTION
                data = Uri.parse("messages-forward-result://$token/$part")
                putExtra("token", token); putExtra("part", part)
            }
            PendingIntent.getBroadcast(context, 0, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        })
        if (parts.size == 1) manager.sendTextMessage(decision.rule.targetNumber, null, parts[0], callbacks[0], null)
        else manager.sendMultipartTextMessage(decision.rule.targetNumber, null, parts, callbacks, null)
    }
}

class ForwardingSentReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != ForwardingRuntime.SENT_ACTION) return
        val token = intent.getStringExtra("token") ?: return
        val part = intent.getIntExtra("part", -1)
        val ok = resultCode == Activity.RESULT_OK
        val pending = goAsync()
        CoroutineScope(SupervisorJob() + Dispatchers.IO).launch {
            try { ForwardingRuntime.get(context).store.completePart(token, part, ok) }
            catch (_: Exception) { android.util.Log.w("Forwarding", "Unable to record send result") }
            finally { pending.finish() }
        }
    }
}

class StopForwardingReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val pending = goAsync()
        CoroutineScope(SupervisorJob() + Dispatchers.IO).launch {
            try { ForwardingRuntime.get(context).stop() }
            catch (_: Exception) { android.util.Log.w("Forwarding", "Unable to save disabled state") }
            finally { pending.finish() }
        }
    }
}
