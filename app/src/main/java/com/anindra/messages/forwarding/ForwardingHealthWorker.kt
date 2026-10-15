package com.anindra.messages.forwarding

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import java.util.concurrent.TimeUnit

class ForwardingHealthWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val runtime = ForwardingRuntime.get(applicationContext)
        return try {
            runtime.store.maintain()
            val config = runtime.load()
            if (config.enabled && !runtime.ready()) runtime.stop()
            else ForwardingNotification.update(applicationContext, config.enabled)
            Result.success()
        } catch (_: Exception) {
            runCatching { runtime.stop() }
            Result.failure()
        }
    }

    companion object {
        fun schedule(context: Context, enabled: Boolean) {
            val work = WorkManager.getInstance(context)
            if (!enabled) { work.cancelUniqueWork("forwarding-health"); return }
            work.enqueueUniquePeriodicWork("forwarding-health", ExistingPeriodicWorkPolicy.KEEP,
                PeriodicWorkRequestBuilder<ForwardingHealthWorker>(15, TimeUnit.MINUTES).build())
        }
    }
}

class ForwardingBootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED && intent.action != Intent.ACTION_MY_PACKAGE_REPLACED) return
        WorkManager.getInstance(context).enqueue(OneTimeWorkRequestBuilder<ForwardingHealthWorker>().build())
    }
}
