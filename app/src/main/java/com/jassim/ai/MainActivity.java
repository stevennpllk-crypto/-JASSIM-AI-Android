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
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private final int bg = Color.rgb(15, 17, 29);
    private final int panel = Color.rgb(27, 30, 47);
    private LinearLayout messages;
    private EditText input;
    private ScrollView scroll;
    private TextView status;
    private SharedPreferences prefs;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        prefs = getSharedPreferences("jassim", MODE_PRIVATE);
        ensureConversationId();
        buildUi();
        addMessage("JASSIM AI", "أهلاً بك! أنا JASSIM AI. اربطني بخادم الذكاء الاصطناعي من زر الإعدادات لبدء المحادثة الذكية.");
        if (!prefs.getString("endpoint", "").trim().isEmpty()) {
            checkHealth();
        }
    }

    private String ensureConversationId() {
        String id = prefs.getString("conversation_id", "");
        if (id == null || id.trim().isEmpty()) {
            id = "android-" + UUID.randomUUID().toString();
            prefs.edit().putString("conversation_id", id).apply();
        }
        return id;
    }

    private void newConversation() {
        String id = "android-" + UUID.randomUUID().toString();
        prefs.edit().putString("conversation_id", id).apply();
        addMessage("JASSIM AI", "بدأنا محادثة جديدة. رسائلك الجديدة ستحفظ في سجل مستقل.");
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

        Button newChat = new Button(this);
        newChat.setText("محادثة جديدة");
        newChat.setOnClickListener(v -> newConversation());
        header.addView(newChat);

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

    private String baseUrl() {
        String endpoint = prefs.getString("endpoint", "").trim();
        while (endpoint.endsWith("/")) endpoint = endpoint.substring(0, endpoint.length() - 1);
        return endpoint;
    }

    private HttpURLConnection openConnection(String path, String method) throws Exception {
        URL url = new URL(baseUrl() + path);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setRequestMethod(method);
        connection.setConnectTimeout(20000);
        connection.setReadTimeout(180000);
        connection.setRequestProperty("Accept", "application/json");
        String token = prefs.getString("api_token", "").trim();
        if (!token.isEmpty()) connection.setRequestProperty("Authorization", "Bearer " + token);
        return connection;
    }

    private JSONObject readJsonResponse(HttpURLConnection connection) throws Exception {
        int code = connection.getResponseCode();
        InputStream stream = code >= 200 && code < 300
            ? connection.getInputStream() : connection.getErrorStream();
        if (stream == null) throw new IOException("HTTP " + code + " دون محتوى");
        StringBuilder response = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(stream, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) response.append(line);
        }
        JSONObject json = new JSONObject(response.toString());
        if (code < 200 || code >= 300) {
            String detail = json.optString("error", json.optString("detail", "طلب غير ناجح"));
            throw new IOException("HTTP " + code + ": " + detail);
        }
        return json;
    }

    private void checkHealth() {
        if (baseUrl().isEmpty()) {
            status.setText("● غير متصل بالخادم");
            status.setTextColor(0xFFFFC36B);
            return;
        }
        status.setText("● نفحص اتصال الخادم...");
        executor.execute(() -> {
            HttpURLConnection connection = null;
            try {
                connection = openConnection("/health", "GET");
                JSONObject result = readJsonResponse(connection);
                boolean ok = result.optBoolean("ok", false);
                String engine = result.optString("engine", "غير معروف");
                runOnUiThread(() -> {
                    status.setText(ok ? "● متصل بالخادم — " + engine : "● الخادم غير جاهز");
                    status.setTextColor(ok ? 0xFF62DCA8 : 0xFFFFC36B);
                });
            } catch (Exception e) {
                String error = e.getMessage() == null ? "تعذر فحص الخادم" : e.getMessage();
                runOnUiThread(() -> {
                    status.setText("● فشل الاتصال: " + error);
                    status.setTextColor(0xFFFF7777);
                });
            } finally {
                if (connection != null) connection.disconnect();
            }
        });
    }

    private void sendMessage() {
        String message = input.getText().toString().trim();
        if (message.isEmpty()) return;
        input.setText("");
        ((InputMethodManager)getSystemService(Context.INPUT_METHOD_SERVICE))
            .hideSoftInputFromWindow(input.getWindowToken(), 0);
        addMessage("أنت", message);

        if (baseUrl().isEmpty()) {
            addMessage("JASSIM AI", "لم يتم إعداد رابط الخادم بعد. اضغط «الإعدادات» وأدخل رابط HTTPS ورمز API.");
            return;
        }

        status.setText("● جارٍ إرسال الرسالة إلى JASSIM AI...");
        status.setTextColor(0xFFFFC36B);
        String conversationId = ensureConversationId();

        executor.execute(() -> {
            HttpURLConnection connection = null;
            try {
                connection = openConnection("/api/chat", "POST");
                connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                JSONObject body = new JSONObject();
                body.put("message", message);
                body.put("conversation_id", conversationId);
                try (OutputStream out = connection.getOutputStream()) {
                    out.write(body.toString().getBytes(StandardCharsets.UTF_8));
                }
                JSONObject json = readJsonResponse(connection);
                String answer = json.optString("answer", json.optString("reply", ""));
                if (answer.isEmpty()) answer = "وصل رد من الخادم لكن لم أجد الحقل answer أو reply.";
                final String result = answer;
                final String engine = json.optString("engine", "متصل");
                runOnUiThread(() -> {
                    status.setText("● متصل بالخادم — " + engine);
                    status.setTextColor(0xFF62DCA8);
                    addMessage("JASSIM AI", result);
                });
            } catch (Exception e) {
                final String error = e.getMessage() == null ? "خطأ اتصال" : e.getMessage();
                runOnUiThread(() -> {
                    status.setText("● فشل الاتصال");
                    status.setTextColor(0xFFFF7777);
                    addMessage("JASSIM AI", "تعذر إكمال الطلب: " + error
                        + "\nتحقق من أن جلسة Colab والنفق ما زالا يعملان.");
                });
            } finally {
                if (connection != null) connection.disconnect();
            }
        });
    }

    private void endpointDialog() {
        LinearLayout fields = new LinearLayout(this);
        fields.setOrientation(LinearLayout.VERTICAL);
        int pad = (int)(18 * getResources().getDisplayMetrics().density);
        fields.setPadding(pad, pad / 2, pad, 0);

        EditText field = new EditText(this);
        field.setSingleLine(true);
        field.setHint("https://your-server.trycloudflare.com");
        field.setText(prefs.getString("endpoint", ""));
        fields.addView(field);

        EditText tokenField = new EditText(this);
        tokenField.setSingleLine(true);
        tokenField.setHint("رمز الوصول API Token");
        tokenField.setInputType(android.text.InputType.TYPE_CLASS_TEXT
            | android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD);
        tokenField.setText(prefs.getString("api_token", ""));
        fields.addView(tokenField);

        new AlertDialog.Builder(this)
            .setTitle("اتصال خادم JASSIM AI")
            .setMessage("أدخل رابط HTTPS الظاهر في Colab ورمز API الخاص بالجلسة. لا تشارك الرمز مع أحد.")
            .setView(fields)
            .setNegativeButton("إلغاء", null)
            .setPositiveButton("حفظ وفحص", (d, w) -> {
                String value = field.getText().toString().trim();
                String token = tokenField.getText().toString().trim();
                if (!value.isEmpty() && !(value.startsWith("https://") || value.startsWith("http://"))) {
                    Toast.makeText(this, "يجب أن يبدأ الرابط بـ https://", Toast.LENGTH_LONG).show();
                    return;
                }
                prefs.edit().putString("endpoint", value).putString("api_token", token).apply();
                checkHealth();
            }).show();
    }

    @Override protected void onDestroy() {
        super.onDestroy();
        executor.shutdown();
    }
}
