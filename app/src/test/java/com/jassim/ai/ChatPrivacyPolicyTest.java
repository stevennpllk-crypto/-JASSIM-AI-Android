package com.jassim.ai;

import org.junit.Test;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

public class ChatPrivacyPolicyTest {
    @Test
    public void blocksBeforeHealthCheck() {
        assertFalse(ChatPrivacyPolicy.canSend(false, true, false));
    }

    @Test
    public void blocksWhenLocalModelIsUnavailable() {
        assertFalse(ChatPrivacyPolicy.canSend(true, false, false));
    }

    @Test
    public void blocksWheneverExternalProviderRouteIsReady() {
        assertFalse(ChatPrivacyPolicy.canSend(true, true, true));
    }

    @Test
    public void allowsOnlyVerifiedPrivateLocalInference() {
        assertTrue(ChatPrivacyPolicy.canSend(true, true, false));
    }
}
