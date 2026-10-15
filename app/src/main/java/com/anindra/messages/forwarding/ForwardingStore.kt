package com.anindra.messages.forwarding

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

internal class ForwardingStore(context: Context, name: String = "forwarding.db") : SQLiteOpenHelper(context, name, null, 1) {
    private val state = MutableStateFlow(ForwardingConfig())
    val config = state.asStateFlow()

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("CREATE TABLE config (id INTEGER PRIMARY KEY CHECK(id=1), value BLOB NOT NULL)")
        db.execSQL("""CREATE TABLE forward_log (
            token TEXT PRIMARY KEY, sender_hash TEXT NOT NULL, timestamp INTEGER NOT NULL,
            rule_id INTEGER NOT NULL, status TEXT NOT NULL, parts INTEGER NOT NULL DEFAULT 0)""")
        db.execSQL("CREATE INDEX forward_log_time ON forward_log(timestamp)")
        db.execSQL("CREATE TABLE part_result (token TEXT NOT NULL, part INTEGER NOT NULL, ok INTEGER NOT NULL, PRIMARY KEY(token,part))")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) = Unit

    @Synchronized
    fun load(): ForwardingConfig {
        val loaded = readableDatabase.rawQuery("SELECT value FROM config WHERE id=1", null).use {
            if (it.moveToFirst()) ForwardingCodec.decode(ForwardingCrypto.decrypt(it.getBlob(0))) else ForwardingConfig()
        }
        state.value = loaded
        return loaded
    }

    @Synchronized
    fun save(config: ForwardingConfig) {
        require(RuleEngine.valid(config))
        val value = ContentValues().apply {
            put("id", 1); put("value", ForwardingCrypto.encrypt(ForwardingCodec.encode(config)))
        }
        check(writableDatabase.insertWithOnConflict("config", null, value, SQLiteDatabase.CONFLICT_REPLACE) != -1L)
        state.value = config
    }

    @Synchronized
    fun reserve(token: String, senderHash: String, ruleId: Long, now: Long, loop: Boolean): Boolean {
        val db = writableDatabase
        db.beginTransaction()
        try {
            if (db.rawQuery("SELECT 1 FROM forward_log WHERE token=?", arrayOf(token)).use { it.moveToFirst() }) return false
            val count = db.rawQuery("SELECT COUNT(*) FROM forward_log WHERE timestamp>=? AND status NOT IN ('LOOP_BLOCKED','RATE_LIMITED')",
                arrayOf((now - 3_600_000L).toString())).use { it.moveToFirst(); it.getInt(0) }
            val status = when { loop -> ForwardStatus.LOOP_BLOCKED; count >= 30 -> ForwardStatus.RATE_LIMITED; else -> ForwardStatus.RESERVED }
            db.insertOrThrow("forward_log", null, ContentValues().apply {
                put("token", token); put("sender_hash", senderHash); put("timestamp", now)
                put("rule_id", ruleId); put("status", status.name)
            })
            db.setTransactionSuccessful()
            return status == ForwardStatus.RESERVED
        } finally { db.endTransaction() }
    }

    @Synchronized
    fun submitted(token: String, parts: Int) {
        writableDatabase.update("forward_log", ContentValues().apply {
            put("status", ForwardStatus.SUBMITTED.name); put("parts", parts)
        }, "token=? AND status='RESERVED'", arrayOf(token))
    }

    @Synchronized
    fun failed(token: String) {
        writableDatabase.update("forward_log", ContentValues().apply { put("status", ForwardStatus.FAILED.name) }, "token=?", arrayOf(token))
    }

    @Synchronized
    fun completePart(token: String, part: Int, ok: Boolean) {
        val db = writableDatabase
        db.beginTransaction()
        try {
            val parts = db.rawQuery("SELECT parts FROM forward_log WHERE token=? AND status IN ('SUBMITTED','UNKNOWN')", arrayOf(token)).use {
                if (it.moveToFirst()) it.getInt(0) else return
            }
            if (part !in 0 until parts) return
            db.insertWithOnConflict("part_result", null, ContentValues().apply {
                put("token", token); put("part", part); put("ok", if (ok) 1 else 0)
            }, SQLiteDatabase.CONFLICT_IGNORE)
            val status = db.rawQuery("SELECT COUNT(*), MIN(ok) FROM part_result WHERE token=?", arrayOf(token)).use {
                it.moveToFirst()
                when { it.getInt(1) == 0 -> ForwardStatus.FAILED
                    it.getInt(0) == parts -> ForwardStatus.SENT
                    else -> ForwardStatus.SUBMITTED }
            }
            db.update("forward_log", ContentValues().apply { put("status", status.name) }, "token=?", arrayOf(token))
            db.setTransactionSuccessful()
        } finally { db.endTransaction() }
    }

    @Synchronized
    fun maintain(now: Long = System.currentTimeMillis()) {
        val db = writableDatabase
        db.beginTransaction()
        try {
            db.execSQL("UPDATE forward_log SET status='UNKNOWN' WHERE status IN ('RESERVED','SUBMITTED') AND timestamp<?", arrayOf(now - 600_000L))
            db.delete("forward_log", "timestamp<?", arrayOf((now - 7 * 86_400_000L).toString()))
            db.execSQL("DELETE FROM part_result WHERE token NOT IN (SELECT token FROM forward_log)")
            db.setTransactionSuccessful()
        } finally { db.endTransaction() }
    }

    @Synchronized
    fun logs(): List<ForwardLog> = readableDatabase.rawQuery(
        "SELECT token,sender_hash,timestamp,rule_id,status FROM forward_log ORDER BY timestamp DESC LIMIT 100", null
    ).use { cursor -> buildList {
        while (cursor.moveToNext()) add(ForwardLog(cursor.getString(0), cursor.getString(1), cursor.getLong(2),
            cursor.getLong(3), ForwardStatus.valueOf(cursor.getString(4))))
    } }
}
