package com.anindra.messages.forwarding

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.util.UUID

@RunWith(AndroidJUnit4::class)
class ForwardingIntegrationTest {
    private val context = ApplicationProvider.getApplicationContext<Context>()
    private val name = "forwarding-test-${UUID.randomUUID()}.db"
    private lateinit var store: ForwardingStore
    private lateinit var inbox: SQLiteDatabase
    private lateinit var runtime: ForwardingRuntime
    private val sent = mutableListOf<ForwardDecision>()
    private var ready = true
    private val sms = IncomingSms("+15551234567", "Private test body", 1000, 7, 1)
    private val rules = listOf(
        ForwardingRule(1, "Exclude", priority = 100, matchType = MatchType.SENDER_EXACT, matchValue = sms.sender),
        ForwardingRule(2, "Copy", action = RuleAction.FORWARD, targetNumber = "+15559876543")
    )

    @Before fun setup() {
        store = ForwardingStore(context, name)
        inbox = SQLiteDatabase.create(null)
        inbox.execSQL("CREATE TABLE messages(body TEXT)")
        runtime = ForwardingRuntime(context, store, SmsCopySender { _, decision, _, submitted ->
            assertEquals(1, inboxCount())
            sent += decision
            submitted(1)
        }, { ready }, {}, {})
        runtime.save(ForwardingConfig(true, rules))
    }

    @After fun cleanup() {
        store.close()
        inbox.close()
        context.deleteDatabase(name)
    }

    private fun deliver(sms: IncomingSms, isDefault: Boolean = true) = IncomingSmsPipeline.deliver(isDefault,
        persist = { inbox.execSQL("INSERT INTO messages(body) VALUES(?)", arrayOf(sms.body)) },
        forward = { runtime.incoming(sms) })

    private fun inboxCount() = inbox.rawQuery("SELECT COUNT(*) FROM messages", null).use { it.moveToFirst(); it.getInt(0) }

    @Test fun excludedSenderIsRetainedAndNotForwarded() {
        assertTrue(deliver(sms)); assertEquals(1, inboxCount()); assertTrue(sent.isEmpty())
    }
    @Test fun otherSenderIsRetainedAndCopiedToConfirmedTarget() {
        assertTrue(deliver(sms.copy(sender = "+15551112222")))
        assertEquals(1, inboxCount()); assertEquals("+15559876543", sent.single().rule.targetNumber)
        assertEquals(ForwardStatus.SUBMITTED, store.logs().single().status)
    }
    @Test fun nonDefaultDeliveryIsNoOp() {
        assertFalse(deliver(sms, false)); assertEquals(0, inboxCount()); assertTrue(sent.isEmpty())
    }
    @Test fun permissionRevocationDisablesForwardingWithoutDiscardingSms() {
        ready = false
        assertTrue(deliver(sms.copy(sender = "+15551112222")))
        assertEquals(1, inboxCount()); assertTrue(sent.isEmpty()); assertFalse(runtime.load().enabled)
    }
    @Test fun repeatedDeliveryDoesNotSendAgainAfterStoreReopen() {
        deliver(sms.copy(sender = "+15551112222"))
        store.close()
        store = ForwardingStore(context, name)
        runtime = ForwardingRuntime(context, store, SmsCopySender { _, _, _, _ -> fail("duplicate send") }, { true }, {}, {})
        runtime.incoming(sms.copy(sender = "+15551112222"))
        assertEquals(1, sent.size)
    }
    @Test fun callbacksRequireEveryPartAndIgnoreDuplicates() {
        store.reserve("multipart", "hash", 2, System.currentTimeMillis(), false)
        store.submitted("multipart", 2)
        store.completePart("multipart", 0, true)
        store.completePart("multipart", 0, true)
        assertEquals(ForwardStatus.SUBMITTED, store.logs().single().status)
        store.completePart("multipart", 1, true)
        assertEquals(ForwardStatus.SENT, store.logs().single().status)
    }
    @Test fun partialFailureIsNeverReportedAsSuccess() {
        store.reserve("multipart", "hash", 2, System.currentTimeMillis(), false)
        store.submitted("multipart", 2)
        store.completePart("multipart", 0, false)
        store.completePart("multipart", 1, true)
        assertEquals(ForwardStatus.FAILED, store.logs().single().status)
    }
    @Test fun hourlyLimitIsAtomicAndPersistent() {
        val now = System.currentTimeMillis()
        repeat(30) { assertTrue(store.reserve("token$it", "hash", 2, now, false)) }
        assertFalse(store.reserve("over-limit", "hash", 2, now, false))
        assertTrue(store.logs().any { it.status == ForwardStatus.RATE_LIMITED })
    }
    @Test fun staleSubmissionBecomesUnknownWithoutRetry() {
        store.reserve("stale", "hash", 2, 1000, false)
        store.submitted("stale", 1)
        store.maintain(700_000)
        assertEquals(ForwardStatus.UNKNOWN, store.logs().single().status)
        assertFalse(store.reserve("stale", "hash", 2, 700_001, false))
    }
    @Test fun rulePayloadIsAuthenticatedAndNotStoredAsPlainText() {
        val bytes = store.readableDatabase.rawQuery("SELECT value FROM config", null).use { it.moveToFirst(); it.getBlob(0) }
        assertFalse(bytes.toString(Charsets.UTF_8).contains(rules[1].targetNumber))
        bytes[bytes.lastIndex] = (bytes.last().toInt() xor 1).toByte()
        assertThrows(Exception::class.java) { ForwardingCrypto.decrypt(bytes) }
    }
    @Test fun logSchemaHasNoBodyOrRawAddress() {
        val columns = store.readableDatabase.rawQuery("PRAGMA table_info(forward_log)", null).use { c ->
            buildList { while (c.moveToNext()) add(c.getString(1)) }
        }
        assertFalse(columns.contains("body")); assertFalse(columns.contains("sender")); assertFalse(columns.contains("target"))
    }
}
