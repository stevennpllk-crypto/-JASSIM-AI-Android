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

    @Test public void trustsOnlyExplicitPrivateLocalEngineIdentity() {
        assertTrue(ServerHealthPolicy.isPrivateLocalEngine("jassim-private-local-only"));
        assertTrue(ServerHealthPolicy.isPrivateLocalEngine("JASSIM-PRIVATE-LOCAL-ONLY"));
        assertFalse(ServerHealthPolicy.isPrivateLocalEngine(""));
        assertFalse(ServerHealthPolicy.isPrivateLocalEngine(null));
        assertFalse(ServerHealthPolicy.isPrivateLocalEngine("adaptive-router"));
        assertFalse(ServerHealthPolicy.isPrivateLocalEngine("ollama"));
        assertFalse(ServerHealthPolicy.isPrivateLocalEngine("memory"));
    }

    @Test public void explicitExternalFlagAlwaysWins() {
        assertTrue(ServerHealthPolicy.isExternalRoute(true, "local", "ollama"));
    }
}
