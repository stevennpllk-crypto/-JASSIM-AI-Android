package com.jassim.ai;

import java.nio.charset.StandardCharsets;

/** Small, deterministic helpers for exporting assistant replies as UTF-8 text. */
final class ReplyExport {
    static final int MAX_CHARACTERS = 100000;

    private ReplyExport() { }

    static String extractBody(String bubbleText) {
        if (bubbleText == null) return "";
        int newline = bubbleText.indexOf('\n');
        String body = newline >= 0 ? bubbleText.substring(newline + 1) : bubbleText;
        return body.trim();
    }

    static byte[] toUtf8(String content) {
        if (content == null || content.trim().isEmpty()) {
            throw new IllegalArgumentException("Export content is empty");
        }
        if (content.length() > MAX_CHARACTERS) {
            throw new IllegalArgumentException("Export content exceeds the character limit");
        }
        return content.getBytes(StandardCharsets.UTF_8);
    }
}
