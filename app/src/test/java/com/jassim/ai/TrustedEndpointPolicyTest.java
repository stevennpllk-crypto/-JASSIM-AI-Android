package com.jassim.ai;

import org.junit.Test;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

public class TrustedEndpointPolicyTest {
    @Test
    public void acceptsProductionApiHost() {
        assertTrue(TrustedEndpointPolicy.isTrusted(
            "https://jassim-ai-core-final-production.up.railway.app"));
    }

    @Test
    public void acceptsCloudflareQuickTunnelHosts() {
        assertTrue(TrustedEndpointPolicy.isTrusted("https://abc-123.trycloudflare.com"));
        assertTrue(TrustedEndpointPolicy.isTrusted("https://ABC-123.TRYCLOUDFLARE.COM"));
    }

    @Test
    public void rejectsUntrustedAndLookalikeHosts() {
        assertFalse(TrustedEndpointPolicy.isTrusted("https://attacker.example"));
        assertFalse(TrustedEndpointPolicy.isTrusted("https://trycloudflare.com"));
        assertFalse(TrustedEndpointPolicy.isTrusted("https://abc.trycloudflare.com.attacker.example"));
        assertFalse(TrustedEndpointPolicy.isTrusted("https://jassim-ai-core-final-production.up.railway.app.attacker.example"));
    }

    @Test
    public void rejectsUnsafeUrlComponents() {
        assertFalse(TrustedEndpointPolicy.isTrusted("http://abc.trycloudflare.com"));
        assertFalse(TrustedEndpointPolicy.isTrusted("https://user:pass@abc.trycloudflare.com"));
        assertFalse(TrustedEndpointPolicy.isTrusted("https://abc.trycloudflare.com:8443"));
        assertFalse(TrustedEndpointPolicy.isTrusted("https://abc.trycloudflare.com/api"));
        assertFalse(TrustedEndpointPolicy.isTrusted("https://abc.trycloudflare.com/?next=evil"));
        assertFalse(TrustedEndpointPolicy.isTrusted("https://abc.trycloudflare.com/#fragment"));
    }

    @Test
    public void rejectsEmptyMalformedAndOversizedValues() {
        assertFalse(TrustedEndpointPolicy.isTrusted(null));
        assertFalse(TrustedEndpointPolicy.isTrusted(""));
        assertFalse(TrustedEndpointPolicy.isTrusted("not a URL"));
        assertFalse(TrustedEndpointPolicy.isTrusted("https://" + "a".repeat(301) + ".trycloudflare.com"));
    }
}
