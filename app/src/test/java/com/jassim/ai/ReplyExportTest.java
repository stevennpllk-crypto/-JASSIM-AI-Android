package com.jassim.ai;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertThrows;

import java.nio.charset.StandardCharsets;
import org.junit.Test;

public class ReplyExportTest {
    @Test public void extractsOnlyReplyBodyFromBubble() {
        assertEquals("مرحبا بالعالم", ReplyExport.extractBody("JASSIM AI\nمرحبا بالعالم"));
    }

    @Test public void handlesNullAndEmptyBubble() {
        assertEquals("", ReplyExport.extractBody(null));
        assertEquals("", ReplyExport.extractBody("JASSIM AI\n   "));
    }

    @Test public void exportsArabicAsUtf8WithoutCorruption() {
        String arabic = "أهلاً بك — هذه إجابة JASSIM AI";
        byte[] bytes = ReplyExport.toUtf8(arabic);
        assertArrayEquals(arabic.getBytes(StandardCharsets.UTF_8), bytes);
        assertEquals(arabic, new String(bytes, StandardCharsets.UTF_8));
    }

    @Test public void rejectsEmptyAndOversizedContent() {
        assertThrows(IllegalArgumentException.class, () -> ReplyExport.toUtf8("  "));
        assertThrows(IllegalArgumentException.class,
            () -> ReplyExport.toUtf8("ا".repeat(ReplyExport.MAX_CHARACTERS + 1)));
    }
}
