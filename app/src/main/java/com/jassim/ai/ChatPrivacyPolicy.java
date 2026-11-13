package com.jassim.ai;

/** Enforces private-local inference only on the Android client. */
final class ChatPrivacyPolicy {
    private ChatPrivacyPolicy() {}

    static boolean canSend(boolean healthChecked, boolean localModelReady,
                           boolean externalProviderReady) {
        return healthChecked && localModelReady && !externalProviderReady;
    }
}
