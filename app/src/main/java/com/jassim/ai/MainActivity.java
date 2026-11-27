package com.jassim.ai;

import android.app.Activity;
import android.app.AlertDialog;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.graphics.Color;
import android.graphics.Typeface;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.InputMethodManager;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.view.inputmethod.EditorInfo;
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
    private Button sendButton;
    private Button stopButton;
    private volatile HttpURLConnection activeChatConnection;
    private volatile boolean cancelRequested;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final Runnable discoveryRetry = () -> {
        if (!isFinishing() && baseUrl().isEmpty()) autoConnect();
    };

    private void scheduleDiscoveryRetry() {
        mainHandler.removeCallbacks(discoveryRetry);
        mainHandler.postDelayed(discoveryRetry, 30000L);
    }
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
        // Discover a private endpoint only when the owner explicitly publishes one.
        status.setText("● جارٍ اكتشاف عنوان الخادم...");
        status.setTextColor(0xFFFFC36B);
        autoConnect();
    }

    // Optional discovery registry. Publishing is disabled by default in Colab.
    // The registry contains an endpoint only after explicit owner opt-in.
    private static final String DISCOVERY_URL =
        "https://stevennpllk-crypto.github.io/-JASSIM-AI-Android/dashboard/connection.json";

    private void autoConnect() {
        executor.execute(() -> {
            String discovered = "";
            HttpURLConnection discovery = null;
            try {
                discovery = (HttpURLConnection) new URL(DISCOVERY_URL + "?t=" + System.currentTimeMillis()).openConnection();
                discovery.setRequestMethod("GET");
                discovery.setConnectTimeout(12000);
                discovery.setReadTimeout(12000);
                discovery.setRequestProperty("Accept", "application/json");
                discovery.setRequestProperty("Cache-Control", "no-cache");
                int code = discovery.getResponseCode();
                if (code == 200) {
                    StringBuilder body = new StringBuilder();
                    try (BufferedReader reader = new BufferedReader(
                            new InputStreamReader(discovery.getInputStream(), StandardCharsets.UTF_8))) {
                        String line;
                        while ((line = reader.readLine()) != null) body.append(line);
                    }
                    JSONObject registry = new JSONObject(body.toString());
                    String candidate = registry.optString("url", "").trim();
                    if ("online".equals(registry.optString("status", "")) &&
                            candidate.startsWith("https://") &&
                            candidate.length() <= 300) {
                        discovered = candidate;
                    }
                }
            } catch (Exception ignored) {
                // Retain the last manually configured or previously discovered private endpoint.
            } finally {
                if (discovery != null) discovery.disconnect();
            }

            // A session token is scoped to the server that issued it. Never forward
            // credentials to a newly discovered host when the registry URL changes.
            if (!discovered.isEmpty() && !discovered.equals(baseUrl())) {
                try {
                    if (!readApiToken().isEmpty()) saveApiToken("");
                    prefs.edit().putString("endpoint", discovered).apply();
                } catch (Exception ignored) {
                    // Fail closed: keep the previous endpoint if its token cannot be cleared.
                    discovered = "";
                }
            }
            if (!discovered.isEmpty()) {
                prefs.edit().putString("endpoint_source", "discovery").apply();
            }
            final String endpoint = discovered;
            runOnUiThread(() -> {
                if (baseUrl().isEmpty()) {
                    if (messages.getChildCount() == 0) {
                        addMessage("JASSIM AI", "لم يتم العثور على خادم JASSIM الخاص بعد. سيعيد التطبيق البحث تلقائياً كل 30 ثانية. لن تُرسل رسائلك إلى أي مزوّد خارجي.");
                    }
                    status.setText("● الخادم الخاص غير متصل — إعادة المحاولة تلقائياً");
                    status.setTextColor(0xFFFF7777);
                    scheduleDiscoveryRetry();
                } else {
                    mainHandler.removeCallbacks(discoveryRetry);
                    status.setText(endpoint.isEmpty()
                        ? "● تعذر تحديث الرابط — نجرب آخر عنوان محفوظ"
                        : "● تم اكتشاف الخادم تلقائياً — جارٍ الاتصال...");
                    checkHealth();
                    if (readApiToken().isEmpty()) {
                        status.setText("● أنشئ حساباً أو سجّل الدخول للبدء");
                        status.setTextColor(0xFFFFC36B);
                        accountDialog();
                    } else {
                        loadHistory();
                    }
                }
            });
        });
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

    private int dp(float value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    private android.graphics.drawable.GradientDrawable rounded(int color, int radiusDp) {
        android.graphics.drawable.GradientDrawable shape =
            new android.graphics.drawable.GradientDrawable();
        shape.setColor(color);
        shape.setCornerRadius(dp(radiusDp));
        return shape;
    }

    private Button actionButton(String label, String description, Runnable action) {
        Button button = new Button(this);
        button.setText(label);
        button.setTextColor(0xFFE8ECFF);
        button.setTextSize(12);
        button.setAllCaps(false);
        button.setMinWidth(0);
        button.setMinimumWidth(0);
        button.setMinHeight(dp(38));
        button.setMinimumHeight(dp(38));
        button.setPadding(dp(8), 0, dp(8), 0);
        button.setBackground(rounded(0xFF252B42, 12));
        button.setContentDescription(description);
        button.setOnClickListener(v -> action.run());
        return button;
    }

    private void buildUi() {
        final int surface = 0xFF171D30;
        final int muted = 0xFF9BA8C8;
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);
        root.setPadding(dp(14), dp(14), dp(14), dp(12));
        root.setBackgroundColor(0xFF0B1020);

        LinearLayout header = new LinearLayout(this);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setPadding(0, 0, 0, dp(12));

        TextView logo = new TextView(this);
        logo.setText("J");
        logo.setTextColor(Color.WHITE);
        logo.setTextSize(25);
        logo.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        logo.setGravity(Gravity.CENTER);
        android.graphics.drawable.GradientDrawable logoBg =
            new android.graphics.drawable.GradientDrawable(
                android.graphics.drawable.GradientDrawable.Orientation.TL_BR,
                new int[] { 0xFF248BFF, 0xFF7548E8 });
        logoBg.setCornerRadius(dp(16));
        logo.setBackground(logoBg);
        header.addView(logo, new LinearLayout.LayoutParams(dp(46), dp(46)));

        LinearLayout brand = new LinearLayout(this);
        brand.setOrientation(LinearLayout.VERTICAL);
        brand.setPadding(dp(10), 0, dp(6), 0);
        TextView title = new TextView(this);
        title.setText("JASSIM AI");
        title.setTextColor(Color.WHITE);
        title.setTextSize(19);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        TextView tagline = new TextView(this);
        tagline.setText("مساعدك الذكي");
        tagline.setTextColor(muted);
        tagline.setTextSize(11);
        brand.addView(title);
        brand.addView(tagline);
        header.addView(brand, new LinearLayout.LayoutParams(0, -2, 1));

        Button accountButton = actionButton("حساب", "تسجيل الدخول أو إنشاء حساب", () -> accountDialog());
        header.addView(accountButton, new LinearLayout.LayoutParams(-2, dp(38)));
        Button historyButton = actionButton("السجل", "سجل المحادثات", () -> showConversations());
        header.addView(historyButton, new LinearLayout.LayoutParams(-2, dp(38)));
        Button newChat = actionButton("+", "محادثة جديدة", () -> newConversation());
        LinearLayout.LayoutParams newLp = new LinearLayout.LayoutParams(dp(40), dp(38));
        newLp.setMargins(dp(5), 0, 0, 0);
        header.addView(newChat, newLp);
        Button settings = actionButton("⚙", "إعدادات الاتصال", () -> endpointDialog());
        LinearLayout.LayoutParams settingsLp = new LinearLayout.LayoutParams(dp(40), dp(38));
        settingsLp.setMargins(dp(5), 0, 0, 0);
        header.addView(settings, settingsLp);
        root.addView(header);

        status = new TextView(this);
        status.setText("● جارٍ فحص الاتصال...");
        status.setTextColor(0xFFFFC36B);
        status.setTextSize(12);
        status.setGravity(Gravity.CENTER_VERTICAL);
        status.setPadding(dp(13), dp(9), dp(13), dp(9));
        status.setBackground(rounded(0xFF20263A, 13));
        LinearLayout.LayoutParams statusLp = new LinearLayout.LayoutParams(-1, -2);
        statusLp.setMargins(0, 0, 0, dp(12));
        root.addView(status, statusLp);

        scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setClipToPadding(false);
        messages = new LinearLayout(this);
        messages.setOrientation(LinearLayout.VERTICAL);
        messages.setPadding(0, dp(3), 0, dp(12));
        scroll.addView(messages, new ScrollView.LayoutParams(-1, -2));
        root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));

        LinearLayout composerShell = new LinearLayout(this);
        composerShell.setOrientation(LinearLayout.HORIZONTAL);
        composerShell.setGravity(Gravity.CENTER_VERTICAL);
        composerShell.setPadding(dp(7), dp(6), dp(7), dp(6));
        composerShell.setBackground(rounded(surface, 20));
        LinearLayout.LayoutParams shellLp = new LinearLayout.LayoutParams(-1, -2);
        shellLp.setMargins(0, dp(10), 0, 0);

        input = new EditText(this);
        input.setSingleLine(false);
        input.setMaxLines(4);
        input.setMinLines(1);
        input.setHint("اكتب رسالتك هنا...");
        input.setTextColor(Color.WHITE);
        input.setHintTextColor(0xFF8995B2);
        input.setTextSize(14);
        input.setBackgroundColor(Color.TRANSPARENT);
        input.setPadding(dp(10), dp(8), dp(10), dp(8));
        input.setTextDirection(View.TEXT_DIRECTION_RTL);
        input.setGravity(Gravity.RIGHT | Gravity.CENTER_VERTICAL);
        input.setImeOptions(EditorInfo.IME_ACTION_SEND);
        input.setOnEditorActionListener((view, actionId, event) -> {
            if (actionId == EditorInfo.IME_ACTION_SEND) {
                sendMessage();
                return true;
            }
            return false;
        });
        composerShell.addView(input, new LinearLayout.LayoutParams(0, -2, 1));

        stopButton = new Button(this);
        stopButton.setText("إيقاف");
        stopButton.setTextSize(11);
        stopButton.setTextColor(0xFFFFB7B7);
        stopButton.setAllCaps(false);
        stopButton.setMinWidth(0);
        stopButton.setMinimumWidth(0);
        stopButton.setMinHeight(dp(38));
        stopButton.setMinimumHeight(dp(38));
        stopButton.setPadding(dp(5), 0, dp(5), 0);
        stopButton.setBackground(rounded(0xFF3A2635, 12));
        stopButton.setEnabled(false);
        stopButton.setOnClickListener(v -> stopGeneration());
        composerShell.addView(stopButton);

        sendButton = new Button(this);
        sendButton.setText("إرسال");
        sendButton.setTextSize(12);
        sendButton.setTextColor(Color.WHITE);
        sendButton.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        sendButton.setAllCaps(false);
        sendButton.setMinWidth(0);
        sendButton.setMinimumWidth(0);
        sendButton.setMinHeight(dp(40));
        sendButton.setMinimumHeight(dp(40));
        sendButton.setPadding(dp(12), 0, dp(12), 0);
        android.graphics.drawable.GradientDrawable sendBg =
            new android.graphics.drawable.GradientDrawable(
                android.graphics.drawable.GradientDrawable.Orientation.LEFT_RIGHT,
                new int[] { 0xFF267EFF, 0xFF7048E8 });
        sendBg.setCornerRadius(dp(14));
        sendButton.setBackground(sendBg);
        sendButton.setOnClickListener(v -> sendMessage());
        LinearLayout.LayoutParams sendLp = new LinearLayout.LayoutParams(-2, dp(40));
        sendLp.setMargins(dp(5), 0, 0, 0);
        composerShell.addView(sendButton, sendLp);
        root.addView(composerShell, shellLp);

        TextView footer = new TextView(this);
        footer.setText("JASSIM AI  •  محادثاتك تبدأ من هنا");
        footer.setTextColor(0xFF687492);
        footer.setTextSize(10);
        footer.setGravity(Gravity.CENTER);
        footer.setPadding(0, dp(7), 0, 0);
        root.addView(footer);
        setContentView(root);
    }

    private TextView addMessage(String who, String text) {
        boolean isUser = "أنت".equals(who);
        TextView bubble = new TextView(this);
        bubble.setText(who + "\\n" + text);
        bubble.setTextColor(0xFFF1F4FF);
        bubble.setTextSize(14);
        bubble.setTextDirection(View.TEXT_DIRECTION_RTL);
        bubble.setGravity(Gravity.RIGHT);
        bubble.setLineSpacing(dp(2), 1.0f);
        bubble.setPadding(dp(14), dp(11), dp(14), dp(11));
        bubble.setMaxWidth((int)(getResources().getDisplayMetrics().widthPixels * 0.82f));
        bubble.setBackground(rounded(isUser ? 0xFF263C69 : 0xFF1B2338, 17));
        bubble.setOnLongClickListener(v -> {
            ClipboardManager clipboard = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            if (clipboard != null) {
                clipboard.setPrimaryClip(ClipData.newPlainText("JASSIM AI", text));
                Toast.makeText(this, "تم نسخ الرسالة", Toast.LENGTH_SHORT).show();
            }
            return true;
        });
        bubble.setContentDescription(who + ": " + text + " — اضغط مطولاً للنسخ");
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-2, -2);
        lp.gravity = isUser ? Gravity.RIGHT : Gravity.LEFT;
        lp.setMargins(0, dp(4), 0, dp(4));
        messages.addView(bubble, lp);
        if (scroll != null) scroll.post(() -> scroll.fullScroll(View.FOCUS_DOWN));
        return bubble;
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
        final String checkedEndpoint = baseUrl();
        status.setText("● نفحص اتصال الخادم...");
        executor.execute(() -> {
            HttpURLConnection connection = null;
            try {
                connection = openConnection("/health", "GET");
                JSONObject result = readJsonResponse(connection);
                boolean ok = result.optBoolean("ok", false);
                boolean modelReady = result.optBoolean("model_ready", false);
                boolean ready = modelReady;
                String engine = result.optString("model", result.optString("engine", "غير معروف"));
                runOnUiThread(() -> {
                    status.setText(!ok ? "● الخادم غير جاهز"
                        : modelReady ? "● الخادم متصل — النموذج المحلي جاهز"
                        : "● الخادم متصل — النموذج غير جاهز (" + engine + ")");
                    status.setTextColor(!ok ? 0xFFFF7777 : ready ? 0xFF62DCA8 : 0xFFFFC36B);
                });
            } catch (Exception e) {
                String error = e.getMessage() == null ? "تعذر فحص الخادم" : e.getMessage();
                runOnUiThread(() -> {
                    status.setText("● فشل الاتصال: " + error);
                    status.setTextColor(0xFFFF7777);
                    // Only discard a stale endpoint that came from public discovery.
                    // Keep manually configured endpoints and never forward their token elsewhere.
                    if (checkedEndpoint.equals(baseUrl())
                            && "discovery".equals(prefs.getString("endpoint_source", ""))) {
                        prefs.edit().remove("endpoint").apply();
                        status.setText("● عنوان الخادم المكتشف لا يستجيب — سنبحث عن خادم آخر تلقائياً");
                        scheduleDiscoveryRetry();
                    }
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

    private void stopGeneration() {
        cancelRequested = true;
        HttpURLConnection connection = activeChatConnection;
        if (connection != null) connection.disconnect();
        if (stopButton != null) stopButton.setEnabled(false);
        status.setText("● جارٍ إيقاف التوليد...");
        status.setTextColor(0xFFFFC36B);
    }

    private void sendMessage() {
        String message = input.getText().toString().trim();
        if (message.isEmpty()) return;
        if (baseUrl().isEmpty()) {
            status.setText("● اربط خادم JASSIM الخاص أولاً؛ لم تُرسل رسالتك إلى أي خدمة خارجية.");
            status.setTextColor(0xFFFF7777);
            Toast.makeText(this, "الخادم الخاص غير مُعدّ. لم نرسل رسالتك خارجياً.", Toast.LENGTH_LONG).show();
            return;
        }
        input.setText("");
        ((InputMethodManager)getSystemService(Context.INPUT_METHOD_SERVICE))
            .hideSoftInputFromWindow(input.getWindowToken(), 0);

        addMessage("أنت", message);
        final TextView responseBubble = addMessage("JASSIM AI", "...");
        cancelRequested = false;
        if (sendButton != null) sendButton.setEnabled(false);
        if (stopButton != null) stopButton.setEnabled(false);
        status.setText("● جارٍ الاتصال بـ JASSIM AI...");
        status.setTextColor(0xFFFFC36B);
        String conversationId = ensureConversationId();

        executor.execute(() -> {
            HttpURLConnection connection = null;
            StringBuilder answer = new StringBuilder();
            try {
                connection = openConnection("/api/chat/stream", "POST");
                activeChatConnection = connection;
                connection.setReadTimeout(300000);
                runOnUiThread(() -> {
                    if (stopButton != null) stopButton.setEnabled(true);
                    status.setText("● JASSIM AI يكتب الآن...");
                    status.setTextColor(0xFFFFC36B);
                });
                connection.setDoOutput(true);
                connection.setRequestProperty("Accept", "text/event-stream");
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                JSONObject body = new JSONObject();
                body.put("message", message);
                body.put("conversation_id", conversationId);
                try (OutputStream out = connection.getOutputStream()) {
                    out.write(body.toString().getBytes(StandardCharsets.UTF_8));
                }
                int responseCode = connection.getResponseCode();
                if (responseCode < 200 || responseCode >= 300) {
                    readJsonResponse(connection);
                    throw new IOException("HTTP " + responseCode);
                }
                String engine = "ollama";
                boolean completed = false;
                try (BufferedReader reader = new BufferedReader(
                        new InputStreamReader(connection.getInputStream(), StandardCharsets.UTF_8))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        if (!line.startsWith("data: ")) continue;
                        JSONObject event = new JSONObject(line.substring(6));
                        String type = event.optString("type", "");
                        if ("token".equals(type)) {
                            answer.append(event.optString("token", ""));
                            final String partial = answer.toString();
                            runOnUiThread(() -> responseBubble.setText("JASSIM AI\n" + partial));
                        } else if ("done".equals(type)) {
                            engine = event.optString("engine", "ollama");
                            completed = true;
                            break;
                        } else if ("error".equals(type)) {
                            throw new IOException("تعذر إكمال التوليد على الخادم");
                        }
                    }
                }
                if (cancelRequested) return;
                if (!completed || answer.length() == 0) {
                    throw new IOException("انتهى اتصال البث قبل اكتمال الإجابة");
                }
                final String result = answer.toString();
                final String finalEngine = engine;
                runOnUiThread(() -> {
                    responseBubble.setText("JASSIM AI\n" + result);
                    status.setText("● متصل بالخادم — " + finalEngine);
                    status.setTextColor(0xFF62DCA8);
                });
            } catch (Exception e) {
                if (cancelRequested) {
                    runOnUiThread(() -> {
                        if (answer.length() == 0) {
                            responseBubble.setText("JASSIM AI\nتم إيقاف التوليد قبل وصول الإجابة.");
                        }
                        status.setText("● تم إيقاف عرض الإجابة");
                        status.setTextColor(0xFFFFC36B);
                    });
                } else {
                    final String error = e.getMessage() == null ? "خطأ اتصال" : e.getMessage();
                    runOnUiThread(() -> {
                        status.setText("● فشل الاتصال — يمكنك إعادة المحاولة");
                        status.setTextColor(0xFFFF7777);
                        responseBubble.setText("JASSIM AI\nتعذر إكمال الطلب: " + error
                            + "\nاحتفظت برسالتك لتتمكن من إعادة إرسالها.");
                        if (input.getText().toString().trim().isEmpty()) {
                            input.setText(message);
                            input.setSelection(input.length());
                        }
                    });
                }
            } finally {
                if (connection != null) connection.disconnect();
                activeChatConnection = null;
                runOnUiThread(() -> {
                    if (sendButton != null) sendButton.setEnabled(true);
                    if (stopButton != null) stopButton.setEnabled(false);
                });
            }
        });
    }

    private void accountDialog() {
        LinearLayout fields = new LinearLayout(this);
        fields.setOrientation(LinearLayout.VERTICAL);
        int pad = dp(18);
        fields.setPadding(pad, pad / 2, pad, 0);

        EditText emailField = new EditText(this);
        emailField.setSingleLine(true);
        emailField.setHint("البريد الإلكتروني");
        emailField.setInputType(android.text.InputType.TYPE_CLASS_TEXT
            | android.text.InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS);
        fields.addView(emailField);

        EditText passwordField = new EditText(this);
        passwordField.setSingleLine(true);
        passwordField.setHint("كلمة المرور (10 أحرف على الأقل)");
        passwordField.setInputType(android.text.InputType.TYPE_CLASS_TEXT
            | android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD);
        fields.addView(passwordField);

        AlertDialog dialog = new AlertDialog.Builder(this)
            .setTitle("حساب JASSIM AI")
            .setMessage("أنشئ حساباً خاصاً بك أو سجّل الدخول. لا تحتاج إلى رمز الخادم.")
            .setView(fields)
            .setNegativeButton("إغلاق", null)
            .setPositiveButton("دخول", null)
            .setNeutralButton("إنشاء حساب", null)
            .create();
        dialog.setOnShowListener(ignored -> {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v ->
                authenticateAccount(emailField.getText().toString(),
                    passwordField.getText().toString(), false, dialog));
            dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(v ->
                authenticateAccount(emailField.getText().toString(),
                    passwordField.getText().toString(), true, dialog));
        });
        dialog.show();
        dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v ->
            authenticateAccount(emailField.getText().toString(),
                passwordField.getText().toString(), false, dialog));
        dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(v ->
            authenticateAccount(emailField.getText().toString(),
                passwordField.getText().toString(), true, dialog));

        if (readApiToken().startsWith("jss_")) {
            Button logout = new Button(this);
            logout.setText("تسجيل الخروج");
            logout.setAllCaps(false);
            fields.addView(logout);
            logout.setOnClickListener(v -> logoutAccount(dialog));
        }
    }

    private void authenticateAccount(String email, String password, boolean register, AlertDialog dialog) {
        final String cleanEmail = email == null ? "" : email.trim();
        if (cleanEmail.isEmpty() || password == null || password.length() < 10) {
            Toast.makeText(this, "أدخل بريداً صحيحاً وكلمة مرور من 10 أحرف على الأقل", Toast.LENGTH_LONG).show();
            return;
        }
        executor.execute(() -> {
            HttpURLConnection connection = null;
            try {
                URL url = new URL(baseUrl() + (register ? "/api/auth/register" : "/api/auth/login"));
                connection = (HttpURLConnection) url.openConnection();
                connection.setRequestMethod("POST");
                connection.setConnectTimeout(15000);
                connection.setReadTimeout(20000);
                connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                JSONObject payload = new JSONObject();
                payload.put("email", cleanEmail);
                payload.put("password", password);
                try (OutputStream output = connection.getOutputStream()) {
                    output.write(payload.toString().getBytes(StandardCharsets.UTF_8));
                }
                int code = connection.getResponseCode();
                InputStream stream = code >= 400 ? connection.getErrorStream() : connection.getInputStream();
                StringBuilder raw = new StringBuilder();
                if (stream != null) {
                    try (BufferedReader reader = new BufferedReader(
                            new InputStreamReader(stream, StandardCharsets.UTF_8))) {
                        String line;
                        while ((line = reader.readLine()) != null) raw.append(line);
                    }
                }
                JSONObject result = new JSONObject(raw.toString());
                if (code < 200 || code >= 300) {
                    throw new IOException(result.optString("error", "تعذر تسجيل الدخول") + " (HTTP " + code + ")");
                }
                String token = result.optString("token", "");
                if (!token.startsWith("jss_")) throw new IOException("لم يُرجع الخادم رمز جلسة صالحاً");
                saveApiToken(token);
                runOnUiThread(() -> {
                    dialog.dismiss();
                    newConversation();
                    status.setText("● تم تسجيل الدخول إلى حسابك");
                    status.setTextColor(0xFF62DCA8);
                    loadHistory();
                    Toast.makeText(this, register ? "تم إنشاء حسابك بنجاح" : "مرحباً بعودتك", Toast.LENGTH_SHORT).show();
                });
            } catch (Exception error) {
                String message = error.getMessage() == null ? "تعذر الاتصال بالخادم" : error.getMessage();
                runOnUiThread(() -> Toast.makeText(this, message, Toast.LENGTH_LONG).show());
            } finally {
                if (connection != null) connection.disconnect();
            }
        });
    }

    private void logoutAccount(AlertDialog dialog) {
        executor.execute(() -> {
            HttpURLConnection connection = null;
            try {
                connection = openConnection("/api/auth/logout", "POST");
                connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type", "application/json");
                try (OutputStream output = connection.getOutputStream()) {
                    output.write("{}".getBytes(StandardCharsets.UTF_8));
                }
                readJsonResponse(connection);
                saveApiToken("");
                runOnUiThread(() -> {
                    dialog.dismiss();
                    newConversation();
                    status.setText("● تم تسجيل الخروج");
                    status.setTextColor(0xFFFFC36B);
                    Toast.makeText(this, "تم تسجيل الخروج من حسابك", Toast.LENGTH_SHORT).show();
                    accountDialog();
                });
            } catch (Exception error) {
                String message = error.getMessage() == null ? "تعذر تسجيل الخروج" : error.getMessage();
                runOnUiThread(() -> Toast.makeText(this, message, Toast.LENGTH_LONG).show());
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
        tokenField.setHint("رمز إداري قديم (اختياري للمطور)");
        tokenField.setInputType(android.text.InputType.TYPE_CLASS_TEXT
            | android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD);
        // Never prefill the account session token into the legacy developer-token field.
        tokenField.setText("");
        fields.addView(tokenField);

        new AlertDialog.Builder(this)
            .setTitle("اتصال خادم JASSIM AI")
            .setMessage("المستخدم العادي لا يحتاج رمز API؛ استخدم زر حساب لتسجيل الدخول. هذا الحقل اختياري للمطور فقط.")
            .setView(fields)
            .setNegativeButton("إلغاء", null)
            .setPositiveButton("حفظ وفحص", (d, w) -> {
                String value = field.getText().toString().trim();
                String token = tokenField.getText().toString().trim();
                if (!value.isEmpty() && !value.startsWith("https://")) {
                    Toast.makeText(this, "الحماية مفعّلة: يجب استخدام رابط HTTPS فقط", Toast.LENGTH_LONG).show();
                    return;
                }
                if (value.isEmpty()) {
                    Toast.makeText(this, "أدخل رابط الخادم", Toast.LENGTH_LONG).show();
                    return;
                }
                try {
                    String normalizedEndpoint = value;
                    while (normalizedEndpoint.endsWith("/")) {
                        normalizedEndpoint = normalizedEndpoint.substring(0, normalizedEndpoint.length() - 1);
                    }
                    boolean endpointChanged = !normalizedEndpoint.equals(baseUrl());
                    // Bearer session tokens belong to one server; never forward them to a newly configured host.
                    if (endpointChanged) saveApiToken("");
                    if (!token.isEmpty()) saveApiToken(token);
                    prefs.edit()
                        .putString("endpoint", normalizedEndpoint)
                        .putString("endpoint_source", "manual")
                        .apply();
                    checkHealth();
                    if (readApiToken().isEmpty()) {
                        d.dismiss();
                        status.setText("● تم تغيير الخادم — سجّل الدخول مجدداً");
                        status.setTextColor(0xFFFFC36B);
                        accountDialog();
                    } else {
                        loadHistory();
                    }
                } catch (Exception e) {
                    Toast.makeText(this, "تعذر حفظ الرمز بأمان على هذا الجهاز", Toast.LENGTH_LONG).show();
                }
            }).show();
    }

    @Override protected void onDestroy() {
        mainHandler.removeCallbacks(discoveryRetry);
        super.onDestroy();
        executor.shutdown();
    }
}