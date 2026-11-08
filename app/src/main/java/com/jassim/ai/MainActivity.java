package com.jassim.ai;

import android.app.Activity;
import android.app.AlertDialog;
import android.os.Bundle;
import android.graphics.Color;
import android.graphics.Typeface;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.InputMethodManager;
import android.content.Context;
import android.content.SharedPreferences;
import android.widget.*;
import org.json.JSONObject;
import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private final int bg = Color.rgb(15, 17, 29);
    private final int panel = Color.rgb(27, 30, 47);
    private final int accent = Color.rgb(124, 92, 255);
    private LinearLayout messages;
    private EditText input;
    private ScrollView scroll;
    private TextView status;
    private SharedPreferences prefs;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        prefs = getSharedPreferences("jassim", MODE_PRIVATE);
        buildUi();
        addMessage("JASSIM AI", "أهلاً بك! أنا JASSIM AI. اربطني بخادم الذكاء الاصطناعي من زر الإعدادات لبدء المحادثة الذكية.");
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(18, 18, 18, 12);
        root.setBackgroundColor(bg);

        LinearLayout header = new LinearLayout(this);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setOrientation(LinearLayout.HORIZONTAL);

        TextView title = new TextView(this);
        title.setText("JASSIM AI");
        title.setTextColor(Color.WHITE);
        title.setTextSize(23);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        header.addView(title, new LinearLayout.LayoutParams(0, -2, 1));

        Button settings = new Button(this);
        settings.setText("الإعدادات");
        settings.setOnClickListener(v -> endpointDialog());
        header.addView(settings);
        root.addView(header);

        status = new TextView(this);
        status.setText("● غير متصل بالخادم");
        status.setTextColor(0xFFFFC36B);
        status.setPadding(0, 8, 0, 10);
        root.addView(status);

        scroll = new ScrollView(this);
        messages = new LinearLayout(this);
        messages.setOrientation(LinearLayout.VERTICAL);
        scroll.addView(messages);
        root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));

        LinearLayout composer = new LinearLayout(this);
        composer.setGravity(Gravity.CENTER_VERTICAL);
        composer.setOrientation(LinearLayout.HORIZONTAL);

        input = new EditText(this);
        input.setSingleLine(false);
        input.setMaxLines(3);
        input.setHint("اكتب رسالتك...");
        input.setTextColor(Color.WHITE);
        input.setHintTextColor(0xFF9DA3B8);
        input.setBackgroundColor(panel);
        input.setPadding(14, 8, 14, 8);
        input.setTextDirection(View.TEXT_DIRECTION_RTL);
        composer.addView(input, new LinearLayout.LayoutParams(0, -2, 1));

        Button send = new Button(this);
        send.setText("إرسال");
        send.setOnClickListener(v -> sendMessage());
        composer.addView(send);
        root.addView(composer);
        setContentView(root);
    }

    private void addMessage(String who, String text) {
        TextView bubble = new TextView(this);
        bubble.setText(who + "\n" + text);
        bubble.setTextColor(Color.WHITE);
        bubble.setTextSize(15);
        bubble.setTextDirection(View.TEXT_DIRECTION_RTL);
        bubble.setGravity(Gravity.RIGHT);
        bubble.setPadding(14, 12, 14, 12);
        bubble.setBackgroundColor(panel);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
        lp.setMargins(0, 7, 0, 7);
        messages.addView(bubble, lp);
        if (scroll != null) scroll.post(() -> scroll.fullScroll(View.FOCUS_DOWN));
    }

    private void sendMessage() {
        String message = input.getText().toString().trim();
        if (message.isEmpty()) return;
        input.setText("");
        ((InputMethodManager)getSystemService(Context.INPUT_METHOD_SERVICE))
            .hideSoftInputFromWindow(input.getWindowToken(), 0);
        addMessage("أنت", message);

        String endpoint = prefs.getString("endpoint", "").trim();
        if (endpoint.isEmpty()) {
            addMessage("JASSIM AI", "لم يتم إعداد رابط الخادم بعد. اضغط «الإعدادات» وأدخل عنوان API الخاص بخادمك الذي يوفر المسار /api/chat.");
            return;
        }
        status.setText("● جارٍ الاتصال...");
        executor.execute(() -> {
            HttpURLConnection connection = null;
            try {
                String base = endpoint.endsWith("/") ? endpoint.substring(0, endpoint.length()-1) : endpoint;
                URL url = new URL(base + "/api/chat");
                connection = (HttpURLConnection) url.openConnection();
                connection.setRequestMethod("POST");
                connection.setConnectTimeout(15000);
                connection.setReadTimeout(60000);
                connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                JSONObject body = new JSONObject();
                body.put("message", message);
                try (OutputStream out = connection.getOutputStream()) {
                    out.write(body.toString().getBytes(StandardCharsets.UTF_8));
                }
                int code = connection.getResponseCode();
                InputStream stream = code >= 200 && code < 300 ? connection.getInputStream() : connection.getErrorStream();
                StringBuilder response = new StringBuilder();
                try (BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
                    String line;
                    while ((line = reader.readLine()) != null) response.append(line);
                }
                JSONObject json = new JSONObject(response.toString());
                String answer = json.optString("answer", json.optString("reply", ""));
                if (answer.isEmpty()) answer = "وصل رد من الخادم لكن لم أجد الحقل answer أو reply.";
                final String result = answer;
                runOnUiThread(() -> {
                    status.setText("● متصل بالخادم");
                    addMessage("JASSIM AI", result);
                });
            } catch (Exception e) {
                final String error = e.getMessage() == null ? "خطأ اتصال" : e.getMessage();
                runOnUiThread(() -> {
                    status.setText("● فشل الاتصال");
                    addMessage("JASSIM AI", "تعذر الاتصال بالخادم: " + error);
                });
            } finally {
                if (connection != null) connection.disconnect();
            }
        });
    }

    private void endpointDialog() {
        EditText field = new EditText(this);
        field.setSingleLine(true);
        field.setHint("https://your-server.example");
        field.setText(prefs.getString("endpoint", ""));
        new AlertDialog.Builder(this)
            .setTitle("رابط خادم JASSIM AI")
            .setMessage("أدخل رابط الخادم دون /api/chat في النهاية.")
            .setView(field)
            .setNegativeButton("إلغاء", null)
            .setPositiveButton("حفظ", (d, w) -> {
                String value = field.getText().toString().trim();
                prefs.edit().putString("endpoint", value).apply();
                status.setText(value.isEmpty() ? "● غير متصل بالخادم" : "● تم حفظ رابط الخادم");
            }).show();
    }

    @Override protected void onDestroy() {
        super.onDestroy();
        executor.shutdown();
    }
}
