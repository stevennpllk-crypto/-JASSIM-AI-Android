package com.jassim.ai;

import java.net.URL;
import java.util.Locale;

/** Separates public-registry trust from an endpoint explicitly chosen by the user. */
final class TrustedEndpointPolicy {
    private static final String PRODUCTION_HOST =
        "jassim-ai-core-final-production.up.railway.app";
    private static final String DNS_HOST =
        "(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\\.)+[A-Za-z]{2,63}";

    private TrustedEndpointPolicy() {}

    /** Public discovery is deliberately pinned to our canonical production origin. */
    static boolean isTrusted(String candidate) {
        return isSafeHttpsOrigin(candidate)
            && PRODUCTION_HOST.equalsIgnoreCase(hostOf(candidate));
    }

    /**
     * A custom host is accepted only after the user enters it in Connection
     * Settings. Never use this broader check for an unauthenticated public
     * discovery document.
     */
    static boolean isUserConfigured(String candidate) {
        if (!isSafeHttpsOrigin(candidate)) return false;
        String host = hostOf(candidate);
        return host != null && host.matches(DNS_HOST)
            && !host.equalsIgnoreCase("localhost");
    }

    private static boolean isSafeHttpsOrigin(String candidate) {
        if (candidate == null || candidate.isEmpty() || candidate.length() > 300) {
            return false;
        }
        try {
            URL url = new URL(candidate);
            String host = url.getHost();
            String path = url.getPath();
            return "https".equalsIgnoreCase(url.getProtocol())
                && host != null && !host.isEmpty()
                && url.getUserInfo() == null
                && (url.getPort() == -1 || url.getPort() == 443)
                && (path.isEmpty() || "/".equals(path))
                && url.getQuery() == null
                && url.getRef() == null
                && !host.endsWith(".");
        } catch (Exception ignored) {
            return false;
        }
    }

    private static String hostOf(String candidate) {
        try {
            return new URL(candidate).getHost().toLowerCase(Locale.ROOT);
        } catch (Exception ignored) {
            return null;
        }
    }
}
