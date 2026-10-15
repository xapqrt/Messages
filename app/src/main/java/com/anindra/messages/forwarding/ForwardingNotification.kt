package com.anindra.messages.forwarding

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import com.anindra.messages.MainActivity
import com.anindra.messages.R

internal object ForwardingNotification {
    private const val CHANNEL = "sms_forwarding_status"
    private const val ID = 0x465744

    fun channelEnabled(context: Context): Boolean =
        context.getSystemService(NotificationManager::class.java).getNotificationChannel(CHANNEL)?.importance != NotificationManager.IMPORTANCE_NONE

    fun update(context: Context, enabled: Boolean) {
        val manager = context.getSystemService(NotificationManager::class.java)
        if (!enabled) { manager.cancel(ID); return }
        manager.createNotificationChannel(NotificationChannel(CHANNEL, context.getString(R.string.forward_title), NotificationManager.IMPORTANCE_LOW))
        val open = PendingIntent.getActivity(context, ID,
            Intent(context, MainActivity::class.java).putExtra("open_forwarding", true),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val stop = PendingIntent.getBroadcast(context, ID, Intent(context, StopForwardingReceiver::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        manager.notify(ID, NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(android.R.drawable.stat_notify_chat)
            .setContentTitle(context.getString(R.string.forward_active))
            .setContentText(context.getString(R.string.forward_notification))
            .setContentIntent(open).setOngoing(true).setOnlyAlertOnce(true)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .addAction(0, context.getString(R.string.forward_stop), stop)
            .build())
    }
}
