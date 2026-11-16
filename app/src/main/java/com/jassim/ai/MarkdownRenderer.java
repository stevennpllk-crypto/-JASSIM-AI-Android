package com.jassim.ai;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.graphics.Typeface;
import android.text.SpannableStringBuilder;
import android.text.Spanned;
import android.text.TextPaint;
import android.text.style.BackgroundColorSpan;
import android.text.style.ClickableSpan;
import android.text.style.ForegroundColorSpan;
import android.text.style.StyleSpan;
import android.text.style.TypefaceSpan;
import android.widget.Toast;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Lightweight, dependency-free Markdown renderer for chat messages. */
final class MarkdownRenderer {
    private static final Pattern FENCED_CODE =
        Pattern.compile("```([A-Za-z0-9_+.-]*)[ \\t]*\\r?\\n(.*?)```", Pattern.DOTALL);
    private static final Pattern INLINE =
        Pattern.compile("(\\*\\*(.+?)\\*\\*|(?<!\\*)\\*([^*\\n]+)\\*(?!\\*)|`([^`]+)`)");

    private MarkdownRenderer() { }

    static CharSequence render(Context context, String markdown) {
        String source = markdown == null ? "" : markdown;
        SpannableStringBuilder output = new SpannableStringBuilder();
        Matcher blocks = FENCED_CODE.matcher(source);
        int cursor = 0;
        while (blocks.find()) {
            appendText(output, source.substring(cursor, blocks.start()));
            String language = blocks.group(1) == null ? "" : blocks.group(1).trim();
            String code = blocks.group(2) == null ? "" : blocks.group(2);
            if (output.length() > 0 && output.charAt(output.length() - 1) != '\n') output.append("\n");
            int labelStart = output.length();
            output.append(language.isEmpty() ? "الكود" : "الكود · " + language);
            output.setSpan(new StyleSpan(Typeface.BOLD), labelStart, output.length(),
                Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
            output.append("\n");
            int codeStart = output.length();
            output.append(code.endsWith("\n") ? code.substring(0, code.length() - 1) : code);
            int codeEnd = output.length();
            if (codeEnd > codeStart) {
                output.setSpan(new TypefaceSpan("monospace"), codeStart, codeEnd,
                    Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
                output.setSpan(new BackgroundColorSpan(0xFF101827), codeStart, codeEnd,
                    Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
                output.setSpan(new ForegroundColorSpan(0xFFB9D7FF), codeStart, codeEnd,
                    Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
            }
            output.append("\n");
            int copyStart = output.length();
            output.append("⧉ نسخ الكود");
            output.setSpan(new ClickableSpan() {
                @Override public void onClick(android.view.View widget) {
                    ClipboardManager clipboard =
                        (ClipboardManager) context.getSystemService(Context.CLIPBOARD_SERVICE);
                    if (clipboard != null) {
                        clipboard.setPrimaryClip(ClipData.newPlainText("JASSIM AI code", code));
                        Toast.makeText(context, "تم نسخ الكود", Toast.LENGTH_SHORT).show();
                    }
                }
                @Override public void updateDrawState(TextPaint paint) {
                    paint.setColor(0xFF8FB8FF);
                    paint.setUnderlineText(true);
                }
            }, copyStart, output.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
            output.append("\n");
            cursor = blocks.end();
        }
        appendText(output, source.substring(cursor));
        return output;
    }

    private static void appendText(SpannableStringBuilder out, String text) {
        Matcher matcher = INLINE.matcher(text);
        int cursor = 0;
        while (matcher.find()) {
            out.append(text, cursor, matcher.start());
            String bold = matcher.group(2);
            String italic = matcher.group(3);
            String code = matcher.group(4);
            if (bold != null) {
                int start = out.length();
                out.append(bold);
                out.setSpan(new StyleSpan(Typeface.BOLD), start, out.length(),
                    Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
            } else if (italic != null) {
                int start = out.length();
                out.append(italic);
                out.setSpan(new StyleSpan(Typeface.ITALIC), start, out.length(),
                    Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
            } else if (code != null) {
                int start = out.length();
                out.append(code);
                out.setSpan(new TypefaceSpan("monospace"), start, out.length(),
                    Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
                out.setSpan(new BackgroundColorSpan(0xFF101827), start, out.length(),
                    Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
                out.setSpan(new ForegroundColorSpan(0xFFB9D7FF), start, out.length(),
                    Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
            }
            cursor = matcher.end();
        }
        out.append(text, cursor, text.length());
    }
}
