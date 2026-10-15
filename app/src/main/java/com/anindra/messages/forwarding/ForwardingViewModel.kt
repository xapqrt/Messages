package com.anindra.messages.forwarding

import android.app.Application
import android.os.PowerManager
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

data class ForwardingUiState(
    val config: ForwardingConfig = ForwardingConfig(),
    val logs: List<ForwardLog> = emptyList(),
    val ready: Boolean = false,
    val busy: Boolean = true,
    val error: Boolean = false,
    val batteryRestricted: Boolean = false
)

class ForwardingViewModel(application: Application) : AndroidViewModel(application) {
    private val runtime = ForwardingRuntime.get(application)
    private val mutableState = MutableStateFlow(ForwardingUiState())
    val state = mutableState.asStateFlow()

    private var loaded = false

    init {
        viewModelScope.launch { runtime.config.collect { config -> mutableState.update { it.copy(config = config) } } }
        refresh()
    }

    fun refresh() = runOperation {
        val config = runtime.load()
        val ready = runtime.ready()
        if (config.enabled && !ready) runtime.stop()
    }

    fun saveRules(rules: List<ForwardingRule>) = runOperation {
        runtime.save(ForwardingConfig(enabled = false, rules = rules))
    }

    fun enable() = runOperation { runtime.save(runtime.load().copy(enabled = true)) }
    fun stop() = runOperation(force = true) { runtime.stop() }

    private fun runOperation(force: Boolean = false, block: () -> Unit) {
        if (!force && mutableState.value.busy && loaded) return
        loaded = true
        mutableState.update { it.copy(busy = true, error = false) }
        viewModelScope.launch {
            val result = withContext(Dispatchers.IO) {
                runCatching {
                    block()
                    val app = getApplication<Application>()
                    val power = app.getSystemService(PowerManager::class.java)
                    Triple(runtime.load(), runtime.store.logs(), !power.isIgnoringBatteryOptimizations(app.packageName))
                }
            }
            result.fold(onSuccess = { (_, logs, battery) ->
                mutableState.value = ForwardingUiState(runtime.config.value, logs, runtime.ready(), false, false, battery)
            }, onFailure = { mutableState.update { it.copy(busy = false, error = true) } })
        }
    }

}
