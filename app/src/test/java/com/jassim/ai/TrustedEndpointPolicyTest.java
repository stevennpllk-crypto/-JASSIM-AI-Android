package com.jassim.ai;

import org.junit.Test;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

public class TrustedEndpointPolicyTest {
    @Test
    public void acceptsProductionApiHostForDiscoveryAndManualSettings() {
        String endpoint = "https://jassim-ai-core-final-production.up.railway.app";
        assertTrue(TrustedEndpointPolicy.isTrusted(endpoint));
        assertTrue(TrustedEndpointPolicy.isUserConfigured(endpoint));
    }

    @Test
    public void discoveryRemainsPinnedToProductionHost() {
        assertFalse(TrustedEndpointPolicy.isTrusted("https://my-private-jassim.example.com"));
        assertFalse(TrustedEndpointPolicy.isTrusted("https://abc-123.trycloudflare.com"));
        assertFalse(TrustedEndpointPolicy.isTrusted("https://attacker.example"));
    }

    @Test
    public void manualSettingsAcceptsExplicitPrivateHttpsDomain() {
        assertTrue(TrustedEndpointPolicy.isUserConfigured("https://ai.example.com"));
        assertTrue(TrustedEndpointPolicy.isUserConfigured("https://my-jassim-server.example.org:443"));
    }

    @Test
    public void rejectsUnsafeCustomOrigins() {
        assertFalse(TrustedEndpointPolicy.isUserConfigured("http://ai.example.com"));
        assertFalse(TrustedEndpointPolicy.isUserConfigured("https://user:pass@ai.example.com"));
        assertFalse(TrustedEndpointPolicy.isUserConfigured("https://ai.example.com:8443"));
        assertFalse(TrustedEndpointPolicy.isUserConfigured("https://ai.example.com/api"));
        assertFalse(TrustedEndpointPolicy.isUserConfigured("https://ai.example.com/?next=evil"));
        assertFalse(TrustedEndpointPolicy.isUserConfigured("https://ai.example.com/#fragment"));
        assertFalse(TrustedEndpointPolicy.isUserConfigured("https://localhost"));
        assertFalse(TrustedEndpointPolicy.isUserConfigured("https://ai.example.com."));
        assertFalse(TrustedEndpointPolicy.isUserConfigured("https://127.0.0.1"));
    }

    @Test
    public void rejectsLookalikeAndUnsafeProductionUrls() {
        String host = "jassim-ai-core-final-production.up.railway.app";
        assertFalse(TrustedEndpointPolicy.isTrusted("https://" + host + ".attacker.example"));
        assertFalse(TrustedEndpointPolicy.isTrusted("https://user:pass@" + host));
        assertFalse(TrustedEndpointPolicy.isTrusted("https://" + host + ":8443"));
        assertFalse(TrustedEndpointPolicy.isTrusted("https://" + host + "/api"));
        assertFalse(TrustedEndpointPolicy.isTrusted("https://" + host + "/?next=evil"));
        assertFalse(TrustedEndpointPolicy.isTrusted("https://" + host + "/#fragment"));
    }

    @Test
    public void rejectsEmptyMalformedAndOversizedValues() {
        assertFalse(TrustedEndpointPolicy.isTrusted(null));
        assertFalse(TrustedEndpointPolicy.isTrusted(""));
        assertFalse(TrustedEndpointPolicy.isUserConfigured(null));
        assertFalse(TrustedEndpointPolicy.isUserConfigured("not a URL"));
        assertFalse(TrustedEndpointPolicy.isUserConfigured("https://" + "a".repeat(301) + ".example.com"));
    }
}
