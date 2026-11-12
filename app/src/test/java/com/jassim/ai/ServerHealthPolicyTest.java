package com.jassim.ai;

import org.junit.Test;
import static org.junit.Assert.*;

public class ServerHealthPolicyTest {
    @Test public void recognizesOnlineHealthContract() {
        assertTrue(ServerHealthPolicy.isHealthy(false, "online"));
    }

    @Test public void detectsAnonymousPublicFallback() {
        assertTrue(ServerHealthPolicy.isExternalRoute(
            false, "best_effort_public_fallback", "pollinations-anonymous-fallback"));
    }

    @Test public void detectsCredentialedExternalProvider() {
        assertTrue(ServerHealthPolicy.isExternalRoute(false, "credentialed", "openrouter"));
    }

    @Test public void trustsOnlyKnownLocalEngines() {
        assertFalse(ServerHealthPolicy.isExternalRoute(false, "local", "ollama"));
        assertFalse(ServerHealthPolicy.isExternalRoute(false, "", "memory"));
    }

    @Test public void explicitExternalFlagAlwaysWins() {
        assertTrue(ServerHealthPolicy.isExternalRoute(true, "local", "ollama"));
    }
}
