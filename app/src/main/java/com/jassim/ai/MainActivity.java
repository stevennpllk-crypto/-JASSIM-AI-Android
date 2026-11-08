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
import org.json.JSONArray;
import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import android.util.Base64;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
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
    private static final String KEY_ALIAS = "jassim_api_token_v1";

    private SecretKey getOrCreateSecretKey() throws Exception {
        KeyStore keyStore = KeyStore.getInstance("AndroidKeyStore");
        keyStore.load(null);
        java.security.Key key = keyStore.getKey(KEY_ALIAS, null);
        if (key instanceof SecretKey) return (SecretKey) key;
        KeyGenerator generator = KeyGenerator.getInstance(
            android.security.keystore.KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new android.security.keystore.KeyGenParameterSpec.Builder(
            KEY_ALIAS,
            android.security.keystore.KeyProperties.PURPOSE_ENCRYPT
                | android.security.keystore.KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(android.security.keystore.KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(android.security.keystore.KeyProperties.ENCRYPTION_PADDING_NONE)
            .setRandomizedEncryptionRequired(true)
            .build());
        return generator.generateKey();
    }

    private void saveApiToken(String token) throws Exception {
        if (token == null || token.isEmpty()) {
            prefs.edit().remove("api_token").remove("api_token_enc").remove("api_token_iv").apply();
            return;
        }
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateSecretKey());
        byte[] encrypted = cipher.doFinal(token.getBytes(StandardCharsets.UTF_8));
        prefs.edit()
            .putString("api_token_enc", Base64.encodeToString(encrypted, Base64.NO_WRAP))
            .putString("api_token_iv", Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP))
            .remove("api_token")
            .apply();
    }

    private String readApiToken() {
        try {
            String encrypted = prefs.getString("api_token_enc", "");
            String iv = prefs.getString("api_token_iv", "");
            if (encrypted.isEmpty() || iv.isEmpty()) {
                String legacy = prefs.getString("api_token", "");
                if (!legacy.isEmpty()) saveApiToken(legacy);
                return legacy;
            }
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, getOrCreateSecretKey(),
                new GCMParameterSpec(128, Base64.decode(iv, Base64.NO_WRAP)));
            return new String(cipher.doFinal(Base64.decode(encrypted, Base64.NO_WRAP)), StandardCharsets.UTF_8);
        } catch (Exception e) {
            return "";
        }
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        prefs = getSharedPreferences("jassim", MODE_PRIVATE);
        ensureConversationId();
        buildUi();
        // Always open directly into the chat. Server setup must never block the
        // primary conversation screen.
        addMessage("JASSIM AI", "أهلاً بك! أنا JASSIM AI. اكتب رسالتك وسأكون جاهزاً لمساعدتك.");
        if (!prefs.getString("endpoint", "").trim().isEmpty()) {
            checkHealth();
            loadHistory();
        } else {
            status.setText("● المحادثة جاهزة — بانتظار تهيئة خدمة الذكاء الاصطناعي");
            status.setTextColor(0xFFFFC36B);
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
        messages.removeAllViews();
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

        Button historyButton = new Button(this);
        historyButton.setText("السجل");
        historyButton.setOnClickListener(v -> showConversations());
        header.addView(historyButton);

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
        if (!"https".equalsIgnoreCase(url.getProtocol()) || url.getHost().isEmpty()) {
            throw new IOException("الاتصال الآمن HTTPS فقط مسموح به");
        }
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setRequestMethod(method);
        connection.setConnectTimeout(20000);
        connection.setReadTimeout(180000);
        connection.setRequestProperty("Accept", "application/json");
        String token = readApiToken().trim();
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
                boolean modelReady = result.optBoolean("model_ready", false);
                String engine = result.optString("model", result.optString("engine", "غير معروف"));
                runOnUiThread(() -> {
                    status.setText(!ok ? "● الخادم غير جاهز"
                        : modelReady ? "● الخادم متصل — النموذج جاهز"
                        : "● الخادم متصل — النموذج غير جاهز (" + engine + ")");
                    status.setTextColor(!ok ? 0xFFFF7777 : modelReady ? 0xFF62DCA8 : 0xFFFFC36B);
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

    private void loadHistory() {
        if (baseUrl().isEmpty()) return;
        final String conversationId = ensureConversationId();
        status.setText("● جارٍ تحميل سجل المحادثة...");
        executor.execute(() -> {
            HttpURLConnection connection = null;
            try {
                connection = openConnection(
                    "/api/history?conversation_id=" + java.net.URLEncoder.encode(conversationId, "UTF-8"),
                    "GET");
                JSONObject json = readJsonResponse(connection);
                JSONArray saved = json.optJSONArray("messages");
                runOnUiThread(() -> {
                    if (!conversationId.equals(prefs.getString("conversation_id", ""))) return;
                    // Do not overwrite a message the user sent while history was loading.
                    if (messages.getChildCount() > 0) return;
                    messages.removeAllViews();
                    if (saved == null || saved.length() == 0) {
                        addMessage("JASSIM AI", "أهلاً بك! أنا JASSIM AI. اكتب رسالتك لبدء المحادثة.");
                        return;
                    }
                    for (int i = 0; i < saved.length(); i++) {
                        JSONObject item = saved.optJSONObject(i);
                        if (item == null) continue;
                        String role = item.optString("role", "");
                        String content = item.optString("content", "");
                        if (content.isEmpty()) continue;
                        addMessage("assistant".equals(role) ? "JASSIM AI" : "أنت", content);
                    }
                    status.setText("● تم تحميل سجل المحادثة");
                    status.setTextColor(0xFF62DCA8);
                });
            } catch (Exception e) {
                final String error = e.getMessage() == null ? "تعذر تحميل السجل" : e.getMessage();
                runOnUiThread(() -> {
                    if (!conversationId.equals(prefs.getString("conversation_id", ""))) return;
                    status.setText("● تعذر تحميل سجل المحادثة");
                    status.setTextColor(0xFFFFC36B);
                    addMessage("JASSIM AI", "لم أتمكن من استرجاع السجل من الخادم: " + error);
                });
            } finally {
                if (connection != null) connection.disconnect();
            }
        });
    }


    private void showConversations() {
        if (baseUrl().isEmpty()) {
            Toast.makeText(this, "اربط التطبيق بالخادم أولاً", Toast.LENGTH_LONG).show();
            return;
        }
        status.setText("● جارٍ تحميل قائمة المحادثات...");
        executor.execute(() -> {
            HttpURLConnection connection = null;
            try {
                connection = openConnection("/api/conversations?limit=50", "GET");
                JSONObject response = readJsonResponse(connection);
                JSONArray items = response.optJSONArray("conversations");
                if (items == null || items.length() == 0) {
                    runOnUiThread(() -> {
                        status.setText("● لا توجد محادثات محفوظة بعد");
                        status.setTextColor(0xFFFFC36B);
                        Toast.makeText(this, "ستظهر محادثاتك هنا بعد إرسال الرسائل", Toast.LENGTH_LONG).show();
                    });
                    return;
                }
                String[] labels = new String[items.length()];
                String[] ids = new String[items.length()];
                for (int i = 0; i < items.length(); i++) {
                    JSONObject item = items.optJSONObject(i);
                    if (item == null) item = new JSONObject();
                    ids[i] = item.optString("conversation_id", "");
                    String title = item.optString("title", "محادثة");
                    int count = item.optInt("message_count", 0);
                    labels[i] = title + "  ·  " + count + " رسالة";
                    if (ids[i].equals(prefs.getString("conversation_id", ""))) {
                        labels[i] = "✓ " + labels[i];
                    }
                }
                runOnUiThread(() -> new AlertDialog.Builder(this)
                    .setTitle("محادثاتك الأخيرة")
                    .setItems(labels, (dialog, which) -> {
                        String selectedId = ids[which];
                        if (selectedId == null || selectedId.isEmpty()) return;
                        new AlertDialog.Builder(this)
                            .setTitle("إدارة المحادثة")
                            .setItems(new String[]{"فتح المحادثة", "حذف المحادثة"}, (choiceDialog, action) -> {
                                if (action == 0) {
                                    prefs.edit().putString("conversation_id", selectedId).apply();
                                    messages.removeAllViews();
                                    loadHistory();
                                } else {
                                    new AlertDialog.Builder(this)
                                        .setTitle("تأكيد الحذف")
                                        .setMessage("سيتم حذف جميع رسائل هذه المحادثة نهائياً من الخادم. لا يمكن التراجع.")
                                        .setNegativeButton("إلغاء", null)
                                        .setPositiveButton("حذف", (confirmDialog, confirm) -> deleteConversation(selectedId))
                                        .show();
                                }
                            })
                            .setNegativeButton("إلغاء", null)
                            .show();
                    })
                    .setNegativeButton("إغلاق", null)
                    .show());
            } catch (Exception e) {
                final String error = e.getMessage() == null ? "تعذر تحميل المحادثات" : e.getMessage();
                runOnUiThread(() -> {
                    status.setText("● تعذر تحميل قائمة المحادثات");
                    status.setTextColor(0xFFFF7777);
                    Toast.makeText(this, error, Toast.LENGTH_LONG).show();
                });
            } finally {
                if (connection != null) connection.disconnect();
            }
        });
    }

    private void deleteConversation(String conversationId) {
        executor.execute(() -> {
            HttpURLConnection connection = null;
            try {
                String encodedId = java.net.URLEncoder.encode(conversationId, "UTF-8");
                connection = openConnection("/api/conversations?conversation_id=" + encodedId, "DELETE");
                JSONObject result = readJsonResponse(connection);
                boolean deleted = result.optBoolean("deleted", false);
                runOnUiThread(() -> {
                    if (!deleted) {
                        Toast.makeText(this, "لم يتم حذف المحادثة", Toast.LENGTH_LONG).show();
                        return;
                    }
                    if (conversationId.equals(prefs.getString("conversation_id", ""))) {
                        newConversation();
                    }
                    status.setText("● تم حذف المحادثة");
                    status.setTextColor(0xFF62DCA8);
                    Toast.makeText(this, "حُذفت المحادثة ورسائلها من الخادم", Toast.LENGTH_LONG).show();
                });
            } catch (Exception e) {
                String error = e.getMessage() == null ? "تعذر حذف المحادثة" : e.getMessage();
                runOnUiThread(() -> Toast.makeText(this, error, Toast.LENGTH_LONG).show());
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
            addMessage("JASSIM AI", "وصلت رسالتك إلى واجهة المحادثة. خدمة النموذج السحابي لم تُهيأ بعد على هذا الإصدار؛ لن أختلق إجابة أو أدّعي أنني اتصلت بالخادم. احتفظ برسالتك، وسيتم تفعيل الردود الذكية عند نشر نقطة الخدمة الآمنة.");
            status.setText("● وضع المحادثة — خدمة النموذج غير مهيأة");
            status.setTextColor(0xFFFFC36B);
            if (input.getText().toString().trim().isEmpty()) {
                input.setText(message);
                input.setSelection(input.length());
            }
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
                    status.setText("● فشل الاتصال — يمكنك إعادة المحاولة");
                    status.setTextColor(0xFFFF7777);
                    addMessage("JASSIM AI", "تعذر إكمال الطلب: " + error
                        + "\nتحقق من أن جلسة Colab والنفق ما زالا يعملان. احتفظت برسالتك لتتمكن من إعادة إرسالها.");
                    // Restore the failed prompt only when the user has not started
                    // composing another message while the network request was running.
                    if (input.getText().toString().trim().isEmpty()) {
                        input.setText(message);
                        input.setSelection(input.length());
                    }
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
        tokenField.setText(readApiToken());
        fields.addView(tokenField);

        new AlertDialog.Builder(this)
            .setTitle("اتصال خادم JASSIM AI")
            .setMessage("أدخل رابط HTTPS ورمز API. لا تستخدم روابط HTTP ولا تشارك الرمز مع أحد.")
            .setView(fields)
            .setNegativeButton("إلغاء", null)
            .setPositiveButton("حفظ وفحص", (d, w) -> {
                String value = field.getText().toString().trim();
                String token = tokenField.getText().toString().trim();
                if (!value.isEmpty() && !value.startsWith("https://")) {
                    Toast.makeText(this, "الحماية مفعّلة: يجب استخدام رابط HTTPS فقط", Toast.LENGTH_LONG).show();
                    return;
                }
                if (value.isEmpty() || token.isEmpty()) {
                    Toast.makeText(this, "أدخل رابط الخادم ورمز API معاً", Toast.LENGTH_LONG).show();
                    return;
                }
                try {
                    saveApiToken(token);
                    prefs.edit().putString("endpoint", value).apply();
                    checkHealth();
                    loadHistory();
                } catch (Exception e) {
                    Toast.makeText(this, "تعذر حفظ الرمز بأمان على هذا الجهاز", Toast.LENGTH_LONG).show();
                }
            }).show();
    }

    @Override protected void onDestroy() {
        super.onDestroy();
        executor.shutdown();
    }
}
