package com.anindra.messages.forwarding

import android.Manifest
import android.app.role.RoleManager
import android.content.Intent
import android.os.Build
import android.provider.Settings
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import com.anindra.messages.R
import java.text.DateFormat
import java.util.Date

@Composable
fun ForwardingScreen(vm: ForwardingViewModel, onBack: () -> Unit) {
    val state by vm.state.collectAsState()
    val context = LocalContext.current
    val permissions = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { vm.refresh() }
    val role = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { vm.refresh() }
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { vm.refresh() }
    ForwardingContent(state, vm::saveRules, vm::enable, vm::stop, vm::refresh, onBack,
        onPermissions = {
            permissions.launch((listOf(Manifest.permission.SEND_SMS, Manifest.permission.RECEIVE_SMS,
                Manifest.permission.READ_SMS, Manifest.permission.READ_PHONE_STATE) +
                if (Build.VERSION.SDK_INT >= 33) listOf(Manifest.permission.POST_NOTIFICATIONS) else emptyList()).toTypedArray())
        },
        onRole = {
            val manager = context.getSystemService(RoleManager::class.java)
            role.launch(if (manager.isRoleAvailable(RoleManager.ROLE_SMS)) manager.createRequestRoleIntent(RoleManager.ROLE_SMS)
                else Intent(Settings.ACTION_MANAGE_DEFAULT_APPS_SETTINGS))
        },
        onNotificationSettings = {
            context.startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName))
        },
        onBatterySettings = { context.startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)) }
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ForwardingContent(
    state: ForwardingUiState,
    onSaveRules: (List<ForwardingRule>) -> Unit,
    onEnable: () -> Unit,
    onStop: () -> Unit,
    onRefresh: () -> Unit,
    onBack: () -> Unit,
    onPermissions: () -> Unit,
    onRole: () -> Unit,
    onNotificationSettings: () -> Unit,
    onBatterySettings: () -> Unit
) {
    BackHandler(onBack = onBack)
    var editing by remember { mutableStateOf<ForwardingRule?>(null) }
    var preset by remember { mutableStateOf(false) }
    var consent by remember { mutableStateOf(false) }
    Scaffold(topBar = {
        TopAppBar(title = { Text(stringResource(R.string.forward_title)) }, navigationIcon = {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Rounded.ArrowBack, stringResource(R.string.forward_back)) }
        })
    }) { padding ->
        Column(Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(stringResource(R.string.forward_explanation), style = MaterialTheme.typography.bodyMedium)
            Card {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(stringResource(if (state.config.enabled) R.string.forward_active else R.string.forward_off), Modifier.weight(1f))
                        Switch(checked = state.config.enabled, enabled = !state.busy && (state.config.enabled || state.ready &&
                            state.config.rules.any { it.isEnabled && it.action == RuleAction.FORWARD }),
                            modifier = Modifier.testTag("forwarding-switch"),
                            onCheckedChange = { if (it) consent = true else onStop() })
                    }
                    Text(stringResource(R.string.forward_safety), style = MaterialTheme.typography.bodySmall)
                }
            }
            if (state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            if (state.error) Text(stringResource(R.string.forward_error), color = MaterialTheme.colorScheme.error)
            if (!state.ready) {
                Text(stringResource(R.string.forward_requirements))
                TextButton(onClick = onRole) { Text(stringResource(R.string.forward_default)) }
                TextButton(onClick = onPermissions) { Text(stringResource(R.string.forward_permissions)) }
                TextButton(onClick = onNotificationSettings) { Text(stringResource(R.string.forward_notifications)) }
            }
            if (state.batteryRestricted) {
                Text(stringResource(R.string.forward_battery), style = MaterialTheme.typography.bodySmall)
                TextButton(onClick = onBatterySettings) { Text(stringResource(R.string.forward_battery_settings)) }
            }
            Text(stringResource(R.string.forward_rules), style = MaterialTheme.typography.titleLarge)
            Text(stringResource(R.string.forward_order), style = MaterialTheme.typography.bodySmall)
            Row {
                TextButton(onClick = {
                    editing = ForwardingRule(id = (state.config.rules.maxOfOrNull { it.id } ?: 0L) + 1L)
                }, enabled = !state.busy && state.config.rules.size < 50) { Text(stringResource(R.string.forward_add)) }
                TextButton(onClick = { preset = true }, enabled = !state.busy) { Text(stringResource(R.string.forward_preset)) }
            }
            state.config.rules.sortedWith(compareByDescending<ForwardingRule> { it.priority }.thenBy { it.id }).forEach { rule ->
                Card(Modifier.fillMaxWidth().testTag("rule-${rule.id}")) {
                    Column(Modifier.padding(16.dp)) {
                        Text(rule.name, style = MaterialTheme.typography.titleMedium)
                        Text(stringResource(R.string.forward_rule_summary, rule.priority, stringResource(actionLabel(rule.action))))
                        if (rule.action == RuleAction.FORWARD) Text(rule.targetNumber)
                        Text(stringResource(if (rule.isEnabled) R.string.forward_rule_on else R.string.forward_rule_off))
                        Row {
                            TextButton(onClick = { editing = rule }, enabled = !state.busy) { Text(stringResource(R.string.forward_edit)) }
                            TextButton(onClick = { onSaveRules(state.config.rules.filterNot { it.id == rule.id }) }, enabled = !state.busy) {
                                Text(stringResource(R.string.forward_delete))
                            }
                        }
                    }
                }
            }
            Text(stringResource(R.string.forward_history), style = MaterialTheme.typography.titleLarge)
            Text(stringResource(R.string.forward_history_hint), style = MaterialTheme.typography.bodySmall)
            TextButton(onClick = onRefresh, enabled = !state.busy) { Text(stringResource(R.string.forward_refresh)) }
            if (state.logs.isEmpty()) Text(stringResource(R.string.forward_no_history))
            state.logs.forEach { log ->
                ListItem(headlineContent = { Text(stringResource(statusLabel(log.status))) }, supportingContent = {
                    Text(stringResource(R.string.forward_log_detail, DateFormat.getDateTimeInstance().format(Date(log.timestamp)),
                        log.ruleId, log.senderHash.take(12)))
                })
            }
        }
    }
    editing?.let { rule -> ForwardingRuleEditor(rule, onSave = { edited ->
        onSaveRules(state.config.rules.filterNot { it.id == edited.id } + edited)
        editing = null
    }, onDismiss = { editing = null }) }
    if (preset) ForwardingPreset(onSave = { rules -> onSaveRules(rules); preset = false }, onDismiss = { preset = false })
    if (consent) AlertDialog(onDismissRequest = { consent = false },
        title = { Text(stringResource(R.string.forward_consent_title)) },
        text = { Column {
            Text(stringResource(R.string.forward_consent))
            state.config.rules.filter { it.isEnabled && it.action == RuleAction.FORWARD }.map { it.targetNumber }.distinct().forEach { Text(it) }
        } },
        confirmButton = { TextButton(onClick = { consent = false; onEnable() }) { Text(stringResource(R.string.forward_enable)) } },
        dismissButton = { TextButton(onClick = { consent = false }) { Text(stringResource(R.string.forward_cancel)) } })
}

@Composable
fun ForwardingBanner(enabled: Boolean, onOpen: () -> Unit, onStop: () -> Unit) {
    if (!enabled) return
    Surface(color = MaterialTheme.colorScheme.secondaryContainer) {
        Row(Modifier.fillMaxWidth().statusBarsPadding().clickable(onClick = onOpen).padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(stringResource(R.string.forward_active), Modifier.weight(1f), style = MaterialTheme.typography.labelLarge)
            TextButton(onClick = onStop) { Text(stringResource(R.string.forward_stop)) }
        }
    }
}

@Composable
fun ForwardingRuleEditor(initial: ForwardingRule, onSave: (ForwardingRule) -> Unit, onDismiss: () -> Unit) {
    var rule by remember(initial) { mutableStateOf(initial) }
    var priority by remember(initial) { mutableStateOf(initial.priority.toString()) }
    AlertDialog(onDismissRequest = onDismiss, title = { Text(stringResource(R.string.forward_edit)) }, text = {
        Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(rule.name, { rule = rule.copy(name = it.take(64)) }, label = { Text(stringResource(R.string.forward_name)) }, singleLine = true)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(stringResource(R.string.forward_rule_on), Modifier.weight(1f))
                Switch(rule.isEnabled, { rule = rule.copy(isEnabled = it) })
            }
            OutlinedTextField(priority, { priority = it }, label = { Text(stringResource(R.string.forward_priority)) },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), singleLine = true, isError = priority.toIntOrNull() == null)
            ForwardingChoice(stringResource(R.string.forward_match), MatchType.entries.map { stringResource(matchLabel(it)) }, rule.matchType.ordinal) {
                rule = rule.copy(matchType = MatchType.entries[it])
            }
            if (rule.matchType != MatchType.ALL) OutlinedTextField(rule.matchValue, { rule = rule.copy(matchValue = it.take(512)) },
                label = { Text(stringResource(R.string.forward_match_value)) })
            ForwardingChoice(stringResource(R.string.forward_action), RuleAction.entries.map { stringResource(actionLabel(it)) }, rule.action.ordinal) {
                rule = rule.copy(action = RuleAction.entries[it])
            }
            if (rule.action == RuleAction.FORWARD) {
                OutlinedTextField(rule.targetNumber, { rule = rule.copy(targetNumber = it.trim()) }, label = { Text(stringResource(R.string.forward_target)) },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone), singleLine = true)
                ForwardingChoice(stringResource(R.string.forward_outgoing_sim),
                    listOf(stringResource(R.string.forward_same_sim)) + (1..8).map { stringResource(R.string.forward_sim, it) }, rule.outgoingSimSlot + 1) {
                    rule = rule.copy(outgoingSimSlot = it - 1)
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(stringResource(R.string.forward_transform), Modifier.weight(1f))
                    Switch(rule.modifyBody, { rule = rule.copy(modifyBody = it) })
                }
                if (rule.modifyBody) {
                    Text(stringResource(R.string.forward_placeholders), style = MaterialTheme.typography.bodySmall)
                    OutlinedTextField(rule.bodyPrefix, { rule = rule.copy(bodyPrefix = it.take(256)) }, label = { Text(stringResource(R.string.forward_prefix)) })
                    OutlinedTextField(rule.bodySuffix, { rule = rule.copy(bodySuffix = it.take(256)) }, label = { Text(stringResource(R.string.forward_suffix)) })
                }
            }
            ForwardingChoice(stringResource(R.string.forward_incoming_sim),
                listOf(stringResource(R.string.forward_all_sim)) + (1..8).map { stringResource(R.string.forward_sim, it) }, rule.applyToSimSlot + 1) {
                rule = rule.copy(applyToSimSlot = it - 1)
            }
            Text(stringResource(R.string.forward_validation), style = MaterialTheme.typography.bodySmall)
        }
    }, confirmButton = {
        TextButton(onClick = { onSave(rule.copy(priority = priority.toInt())) }, enabled = RuleEngine.valid(rule) && priority.toIntOrNull() != null) {
            Text(stringResource(R.string.forward_save))
        }
    }, dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.forward_cancel)) } })
}

@Composable
internal fun ForwardingChoice(label: String, choices: List<String>, selected: Int, onSelect: (Int) -> Unit) {
    var open by remember { mutableStateOf(false) }
    Box {
        OutlinedButton(onClick = { open = true }) { Text("$label: ${choices[selected]}") }
        DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            choices.forEachIndexed { index, text -> DropdownMenuItem(text = { Text(text) }, onClick = { open = false; onSelect(index) }) }
        }
    }
}

@Composable
fun ForwardingPreset(onSave: (List<ForwardingRule>) -> Unit, onDismiss: () -> Unit) {
    var excluded by remember { mutableStateOf("") }
    var target by remember { mutableStateOf("") }
    val keep = ForwardingRule(1, stringResource(R.string.forward_excluded_rule), priority = 100, matchType = MatchType.SENDER_EXACT, matchValue = excluded.trim())
    val forward = ForwardingRule(2, stringResource(R.string.forward_all_rule), action = RuleAction.FORWARD, targetNumber = target.trim())
    AlertDialog(onDismissRequest = onDismiss, title = { Text(stringResource(R.string.forward_preset)) }, text = {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(stringResource(R.string.forward_preset_hint))
            OutlinedTextField(excluded, { excluded = it }, label = { Text(stringResource(R.string.forward_excluded)) }, singleLine = true)
            OutlinedTextField(target, { target = it }, label = { Text(stringResource(R.string.forward_target)) }, singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone))
        }
    }, confirmButton = {
        TextButton(onClick = { onSave(listOf(keep, forward)) }, enabled = RuleEngine.valid(keep) && RuleEngine.valid(forward) &&
            RuleEngine.numberIdentity(excluded) != RuleEngine.numberIdentity(target)) { Text(stringResource(R.string.forward_save)) }
    }, dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.forward_cancel)) } })
}

private fun matchLabel(type: MatchType): Int = when (type) {
    MatchType.ALL -> R.string.forward_match_all
    MatchType.SENDER_EXACT -> R.string.forward_match_exact
    MatchType.SENDER_CONTAINS -> R.string.forward_match_sender
    MatchType.BODY_CONTAINS -> R.string.forward_match_body
    MatchType.REGEX -> R.string.forward_match_regex
}
private fun actionLabel(action: RuleAction): Int = when (action) {
    RuleAction.FORWARD -> R.string.forward_action_copy
    RuleAction.KEEP_LOCAL -> R.string.forward_action_keep
}
private fun statusLabel(status: ForwardStatus): Int = when (status) {
    ForwardStatus.RESERVED -> R.string.forward_status_reserved
    ForwardStatus.SUBMITTED -> R.string.forward_status_submitted
    ForwardStatus.SENT -> R.string.forward_status_sent
    ForwardStatus.FAILED -> R.string.forward_status_failed
    ForwardStatus.UNKNOWN -> R.string.forward_status_unknown
    ForwardStatus.RATE_LIMITED -> R.string.forward_status_limit
    ForwardStatus.LOOP_BLOCKED -> R.string.forward_status_loop
}
