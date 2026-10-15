package com.anindra.messages.forwarding

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.Mac
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

internal object ForwardingCrypto {
    @Synchronized
    private fun key(hmac: Boolean): SecretKey {
        val alias = if (hmac) "messages_forwarding_hmac_v1" else "messages_forwarding_aes_v1"
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getEntry(alias, null) as? KeyStore.SecretKeyEntry)?.let { return it.secretKey }
        val algorithm = if (hmac) KeyProperties.KEY_ALGORITHM_HMAC_SHA256 else KeyProperties.KEY_ALGORITHM_AES
        val purposes = if (hmac) KeyProperties.PURPOSE_SIGN or KeyProperties.PURPOSE_VERIFY
            else KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
        val spec = KeyGenParameterSpec.Builder(alias, purposes).apply {
            if (hmac) setDigests(KeyProperties.DIGEST_SHA256)
            else {
                setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                setKeySize(256)
            }
        }.build()
        return KeyGenerator.getInstance(algorithm, "AndroidKeyStore").apply { init(spec) }.generateKey()
    }

    fun encrypt(text: String): ByteArray {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key(false))
        cipher.updateAAD("messages-forwarding-v1".toByteArray())
        return cipher.iv + cipher.doFinal(text.toByteArray(Charsets.UTF_8))
    }

    fun decrypt(bytes: ByteArray): String {
        require(bytes.size >= 28)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key(false), GCMParameterSpec(128, bytes.copyOfRange(0, 12)))
        cipher.updateAAD("messages-forwarding-v1".toByteArray())
        return cipher.doFinal(bytes.copyOfRange(12, bytes.size)).toString(Charsets.UTF_8)
    }

    fun hash(value: String): String = Mac.getInstance("HmacSHA256").run {
        init(key(true))
        doFinal(value.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it.toInt() and 255) }
    }
}
