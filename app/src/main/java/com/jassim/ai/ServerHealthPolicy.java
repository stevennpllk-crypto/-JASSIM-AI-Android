package com.jassim.ai;

/** Interprets health responses without ever treating public AI providers as local. */
final class ServerHealthPolicy {
    private ServerHealthPolicy() {}

    static boolean isHealthy(boolean explicitOk, String status) {
        return explicitOk || "online".equalsIgnoreCase(status)
            || "ok".equalsIgnoreCase(status) || "healthy".equalsIgnoreCase(status);
    }

    static boolean isExternalRoute(boolean explicitExternal, String providerMode,
                                   String providerName) {
        if (explicitExternal) return true;
        String mode = providerMode == null ? "" : providerMode.trim().toLowerCase(java.util.Locale.ROOT);
        String provider = providerName == null ? "" : providerName.trim().toLowerCase(java.util.Locale.ROOT);
        if (mode.contains("public") || mode.contains("external") || mode.contains("fallback")) {
            return true;
        }
        if (provider.isEmpty()) return false;
        return !provider.equals("ollama") && !provider.equals("local")
            && !provider.equals("memory") && !provider.equals("jassim-local");
    }
}
