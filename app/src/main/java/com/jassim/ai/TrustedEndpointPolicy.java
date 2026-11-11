package com.jassim.ai;

import java.net.URL;
import java.util.Locale;

/** Validates endpoints read from the public automatic-discovery registry. */
final class TrustedEndpointPolicy {
    private static final String PRODUCTION_HOST =
        "jassim-ai-core-final-production.up.railway.app";

    private TrustedEndpointPolicy() {}

    static boolean isTrusted(String candidate) {
        if (candidate == null || candidate.isEmpty() || candidate.length() > 300) {
            return false;
        }
        try {
            URL url = new URL(candidate);
            String host = url.getHost().toLowerCase(Locale.ROOT);
            boolean trustedHost = PRODUCTION_HOST.equals(host)
                || host.endsWith(".trycloudflare.com");
            String path = url.getPath();
            return "https".equalsIgnoreCase(url.getProtocol())
                && trustedHost
                && url.getUserInfo() == null
                && (url.getPort() == -1 || url.getPort() == 443)
                && (path.isEmpty() || "/".equals(path))
                && url.getQuery() == null
                && url.getRef() == null;
        } catch (Exception ignored) {
            return false;
        }
    }
}
