package com.jassim.ai;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.Dialog;
import android.os.Bundle;
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
    private static final String KEY_ALIAS = "jassim_api_token_v1";
    private static final String DEFAULT_SERVER_URL =
        "https://jassim-ai-core-final-production.up.railway.app";

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
            transientSessionToken = "";
            prefs.edit().remove("api_token").remove("api_token_enc").remove("api_token_iv").apply();
            return;
        }
        if (!rememberSession) {
            transientSessionToken = token;
            prefs.edit().remove("api_token").remove("api_token_enc").remove("api_token_iv").apply();
            return;
        }
        transientSessionToken = "";
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
        if (transientSessionToken != null && !transientSessionToken.isEmpty()) return transientSessionToken;
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
        // Discover the current Colab tunnel from the stable GitHub Pages registry.
        status.setText("● جارٍ اكتشاف عنوان الخادم...");
        status.setTextColor(0xFFFFC36B);
        autoConnect();
    }

    // Stable discovery URL: Colab updates this small public JSON file whenever
    // its temporary Cloudflare tunnel starts or changes. It contains no API token.
    private static final String DISCOVERY_URL =
        "https://stevennpllk-crypto.github.io/-JASSIM-AI-Android/connection.json";

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
                // Use the last known endpoint if the discovery service is temporarily unavailable.
            } finally {
                if (discovery != null) discovery.disconnect();
            }

            final String endpoint = discovered;
            if (!endpoint.isEmpty()) {
                prefs.edit().putString("endpoint", endpoint).apply();
            }
            runOnUiThread(() -> {
                if (baseUrl().isEmpty()) {
                    addMessage("Mahdia AI", "الخادم الخاص غير متصل الآن. يمكنك متابعة المحادثة عبر خدمة ذكاء اصطناعي عامة مجانية؛ قد تتغير سرعتها وحدودها.");
                    status.setText("● الخادم الخاص غير متصل — الخدمة الاحتياطية متاحة");
                    status.setTextColor(0xFFFFC36B);
                } else {
                    status.setText(endpoint.isEmpty()
                        ? "● تعذر تحديث الرابط — نجرب آخر عنوان محفوظ"
                        : "● تم اكتشاف الخادم تلقائياً — جارٍ الاتصال...");
                    checkHealth();
                    if (!readApiToken().isEmpty()) {
                        loadHistory();
                    }
                }
                // Always show account access on first launch, even when the private
                // backend is offline; login UI must not depend on server discovery.
                if (readApiToken().isEmpty()) {
                    status.setText("● أنشئ حساباً أو سجّل الدخول للبدء");
                    status.setTextColor(0xFFFFC36B);
                    accountDialog();
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
        addMessage("Mahdia AI", "بدأنا محادثة جديدة. رسائلك الجديدة ستحفظ في سجل مستقل.");
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

        // Use two compact rows so the header remains usable on narrow phones.
        LinearLayout header = new LinearLayout(this);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setOrientation(LinearLayout.VERTICAL);
        header.setPadding(0, 0, 0, dp(12));

        LinearLayout brandRow = new LinearLayout(this);
        brandRow.setGravity(Gravity.CENTER_VERTICAL);
        brandRow.setOrientation(LinearLayout.HORIZONTAL);

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
        brandRow.addView(logo, new LinearLayout.LayoutParams(dp(46), dp(46)));

        LinearLayout brand = new LinearLayout(this);
        brand.setOrientation(LinearLayout.VERTICAL);
        brand.setPadding(dp(10), 0, dp(6), 0);
        TextView title = new TextView(this);
        title.setText("Mahdia AI");
        title.setTextColor(Color.WHITE);
        title.setTextSize(19);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        TextView tagline = new TextView(this);
        tagline.setText(uiText("ذكاء اصطناعي ... بإبداع تونسي", "Artificial intelligence ... Tunisian creativity", "Intelligence artificielle ... créativité tunisienne"));
        tagline.setTextColor(muted);
        tagline.setTextSize(11);
        brand.addView(title);
        brand.addView(tagline);
        brandRow.addView(brand, new LinearLayout.LayoutParams(0, -2, 1));
        header.addView(brandRow, new LinearLayout.LayoutParams(-1, dp(46)));

        LinearLayout actionsRow = new LinearLayout(this);
        actionsRow.setGravity(Gravity.CENTER_VERTICAL);
        actionsRow.setOrientation(LinearLayout.HORIZONTAL);
        LinearLayout.LayoutParams actionsLp = new LinearLayout.LayoutParams(-1, dp(38));
        actionsLp.setMargins(0, dp(8), 0, 0);

        Button accountButton = actionButton("حساب", "تسجيل الدخول أو إنشاء حساب", () -> accountDialog());
        LinearLayout.LayoutParams accountLp = new LinearLayout.LayoutParams(0, dp(38), 1);
        accountLp.setMargins(0, 0, dp(4), 0);
        actionsRow.addView(accountButton, accountLp);

        Button historyButton = actionButton("السجل", "سجل المحادثات", () -> showConversations());
        LinearLayout.LayoutParams historyLp = new LinearLayout.LayoutParams(0, dp(38), 1);
        historyLp.setMargins(0, 0, dp(4), 0);
        actionsRow.addView(historyButton, historyLp);

        Button newChat = actionButton("+", "محادثة جديدة", () -> newConversation());
        LinearLayout.LayoutParams newLp = new LinearLayout.LayoutParams(dp(40), dp(38));
        newLp.setMargins(0, 0, dp(4), 0);
        actionsRow.addView(newChat, newLp);

        Button improve = actionButton("⚡", "اختبار وتحسين الخادم", () -> runProviderEvaluation());
        LinearLayout.LayoutParams improveLp = new LinearLayout.LayoutParams(dp(40), dp(38));
        improveLp.setMargins(0, 0, dp(4), 0);
        actionsRow.addView(improve, improveLp);

        Button settings = actionButton("⚙", "إعدادات الاتصال", () -> endpointDialog());
        actionsRow.addView(settings, new LinearLayout.LayoutParams(dp(40), dp(38)));
        header.addView(actionsRow, actionsLp);
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
        footer.setText("Mahdia AI  •  محادثاتك تبدأ من هنا");
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
        bubble.setText(who + "\n" + text);
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
                clipboard.setPrimaryClip(ClipData.newPlainText("Mahdia AI", text));
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
        if (endpoint.isEmpty()) endpoint = DEFAULT_SERVER_URL;
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
                boolean adaptiveReady = result.optBoolean("external_provider_ready", false);
                boolean ready = modelReady || adaptiveReady;
                String engine = result.optString("model", result.optString("engine", "غير معروف"));
                runOnUiThread(() -> {
                    status.setText(!ok ? "● الخادم غير جاهز"
                        : modelReady ? "● الخادم متصل — النموذج المحلي جاهز"
                        : adaptiveReady ? "● الخادم متصل — التوجيه الذكي جاهز"
                        : "● الخادم متصل — النموذج غير جاهز (" + engine + ")");
                    status.setTextColor(!ok ? 0xFFFF7777 : ready ? 0xFF62DCA8 : 0xFFFFC36B);
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
                        addMessage("Mahdia AI", "أهلاً بك! أنا Mahdia AI. اكتب رسالتك لبدء المحادثة.");
                        return;
                    }
                    for (int i = 0; i < saved.length(); i++) {
                        JSONObject item = saved.optJSONObject(i);
                        if (item == null) continue;
                        String role = item.optString("role", "");
                        String content = item.optString("content", "");
                        if (content.isEmpty()) continue;
                        addMessage("assistant".equals(role) ? "Mahdia AI" : "أنت", content);
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
                    addMessage("Mahdia AI", "لم أتمكن من استرجاع السجل من الخادم: " + error);
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

    // Build a short in-memory transcript for public fallback providers.
    // The pending assistant bubble is excluded; the current user message is included.
    private JSONArray buildFallbackHistory(TextView pendingBubble) {
        JSONArray history = new JSONArray();
        java.util.ArrayList<JSONObject> recent = new java.util.ArrayList<>();
        for (int i = 0; i < messages.getChildCount(); i++) {
            View child = messages.getChildAt(i);
            if (!(child instanceof TextView) || child == pendingBubble) continue;
            String value = ((TextView) child).getText().toString();
            int newline = value.indexOf('\n');
            if (newline < 0) continue;
            String header = value.substring(0, newline).trim();
            String content = value.substring(newline + 1).trim();
            if (content.isEmpty()) continue;
            String role;
            if ("أنت".equals(header)) role = "user";
            else if ("Mahdia AI".equals(header)) role = "assistant";
            else continue;
            try {
                JSONObject item = new JSONObject();
                item.put("role", role);
                item.put("content", content);
                recent.add(item);
            } catch (Exception ignored) { }
        }
        int start = Math.max(0, recent.size() - 16);
        for (int i = start; i < recent.size(); i++) history.put(recent.get(i));
        return history;
    }

    private void sendMessage() {
        String message = input.getText().toString().trim();
        if (message.isEmpty()) return;
        input.setText("");
        ((InputMethodManager)getSystemService(Context.INPUT_METHOD_SERVICE))
            .hideSoftInputFromWindow(input.getWindowToken(), 0);
        if (baseUrl().isEmpty()) {
            addMessage("أنت", message);
            final TextView fallbackBubble = addMessage("Mahdia AI", "جارٍ الاتصال بالخدمة الاحتياطية...");
            final JSONArray fallbackHistory = buildFallbackHistory(fallbackBubble);
            cancelRequested = false;
            if (sendButton != null) sendButton.setEnabled(false);
            if (stopButton != null) stopButton.setEnabled(false);
            status.setText("● نتصل بخدمة الذكاء الاصطناعي الاحتياطية...");
            status.setTextColor(0xFFFFC36B);
            executor.execute(() -> sendAnonymousFallback(fallbackHistory, fallbackBubble, message));
            return;
        }

        addMessage("أنت", message);
        final TextView responseBubble = addMessage("Mahdia AI", "...");
        cancelRequested = false;
        if (sendButton != null) sendButton.setEnabled(false);
        if (stopButton != null) stopButton.setEnabled(false);
        status.setText("● جارٍ الاتصال بـ Mahdia AI...");
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
                    status.setText("● Mahdia AI يكتب الآن...");
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
                            runOnUiThread(() -> responseBubble.setText("Mahdia AI\n" + partial));
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
                    responseBubble.setText("Mahdia AI\n" + result);
                    status.setText("● متصل بالخادم — " + finalEngine);
                    status.setTextColor(0xFF62DCA8);
                });
            } catch (Exception e) {
                if (cancelRequested) {
                    runOnUiThread(() -> {
                        if (answer.length() == 0) {
                            responseBubble.setText("Mahdia AI\nتم إيقاف التوليد قبل وصول الإجابة.");
                        }
                        status.setText("● تم إيقاف عرض الإجابة");
                        status.setTextColor(0xFFFFC36B);
                    });
                } else {
                    final String error = e.getMessage() == null ? "خطأ اتصال" : e.getMessage();
                    runOnUiThread(() -> {
                        status.setText("● فشل الاتصال — يمكنك إعادة المحاولة");
                        status.setTextColor(0xFFFF7777);
                        responseBubble.setText("Mahdia AI\nتعذر إكمال الطلب: " + error
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

    // Public, keyless fallback. The user's private JASSIM token is never sent here.
    // Requests go to a third-party gateway; users should not submit sensitive information.
    private String requestAnonymousProvider(String endpoint, String model, JSONArray history,
                                            TextView responseBubble) throws Exception {
        HttpURLConnection connection = null;
        StringBuilder answer = new StringBuilder();
        try {
            URL url = new URL(endpoint);
            connection = (HttpURLConnection) url.openConnection();
            activeChatConnection = connection;
            connection.setRequestMethod("POST");
            connection.setConnectTimeout(25000);
            connection.setReadTimeout(180000);
            connection.setDoOutput(true);
            connection.setRequestProperty("Accept", "text/event-stream");
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");

            JSONArray chatMessages = new JSONArray();
            JSONObject system = new JSONObject();
            system.put("role", "system");
            system.put("content", "أنت Mahdia AI، مساعد عربي مفيد ودقيق. أجب بالعربية الواضحة، وافهم اللهجة التونسية. لا تختلق معلومات، واذكر حدود معرفتك.");
            chatMessages.put(system);
            if (history != null) {
                for (int i = 0; i < history.length(); i++) {
                    JSONObject item = history.optJSONObject(i);
                    if (item == null) continue;
                    String role = item.optString("role", "");
                    String content = item.optString("content", "");
                    if (("user".equals(role) || "assistant".equals(role)) && !content.isEmpty()) {
                        chatMessages.put(item);
                    }
                }
            }

            JSONObject body = new JSONObject();
            body.put("model", model);
            body.put("messages", chatMessages);
            body.put("stream", true);
            body.put("max_tokens", 1200);
            try (OutputStream out = connection.getOutputStream()) {
                out.write(body.toString().getBytes(StandardCharsets.UTF_8));
            }

            int code = connection.getResponseCode();
            if (code < 200 || code >= 300) {
                InputStream err = connection.getErrorStream();
                StringBuilder detail = new StringBuilder();
                if (err != null) {
                    try (BufferedReader reader = new BufferedReader(
                            new InputStreamReader(err, StandardCharsets.UTF_8))) {
                        String line;
                        while ((line = reader.readLine()) != null) detail.append(line);
                    }
                }
                throw new IOException("HTTP " + code + ": " + detail);
            }

            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(connection.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    if (cancelRequested) break;
                    if (!line.startsWith("data:")) continue;
                    String data = line.substring(5).trim();
                    if (data.isEmpty()) continue;
                    if ("[DONE]".equals(data)) break;
                    JSONObject event = new JSONObject(data);
                    JSONArray choices = event.optJSONArray("choices");
                    if (choices == null || choices.length() == 0) continue;
                    JSONObject choice = choices.optJSONObject(0);
                    if (choice == null) continue;
                    JSONObject delta = choice.optJSONObject("delta");
                    if (delta == null) continue;
                    String token = delta.optString("content", "");
                    if (!token.isEmpty()) {
                        answer.append(token);
                        final String partial = answer.toString();
                        runOnUiThread(() -> responseBubble.setText("Mahdia AI\n" + partial));
                    }
                }
            }
            if (cancelRequested) return "";
            if (answer.length() == 0) throw new IOException("لم تُرجع الخدمة أي نص");
            return answer.toString();
        } finally {
            if (connection != null) connection.disconnect();
            if (activeChatConnection == connection) activeChatConnection = null;
        }
    }

    private void sendAnonymousFallback(JSONArray history, TextView responseBubble, String userMessage) {
        try {
            runOnUiThread(() -> {
                if (stopButton != null) stopButton.setEnabled(true);
                status.setText("● نجرب مزود الذكاء الاصطناعي الأول...");
                status.setTextColor(0xFFFFC36B);
            });
            String result;
            String provider;
            try {
                result = requestAnonymousProvider(
                    "https://api.jarvisclaw.ai/v1/chat/completions",
                    "auto/free", history, responseBubble);
                provider = "JarvisClaw";
            } catch (Exception firstError) {
                if (cancelRequested) return;
                runOnUiThread(() -> {
                    responseBubble.setText("Mahdia AI\nتعذر الوصول إلى المزود الأول؛ نجرب خادماً احتياطياً آخر...");
                    status.setText("● نجرب OVHcloud كخيار ثانٍ...");
                });
                try {
                    result = requestAnonymousProvider(
                        "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/chat/completions",
                        "Meta-Llama-3_3-70B-Instruct", history, responseBubble);
                    provider = "OVHcloud";
                } catch (Exception secondError) {
                    throw new IOException("لم يستجب أي من المزودين المجانيين. الأول: "
                        + firstError.getMessage() + " | الثاني: " + secondError.getMessage());
                }
            }
            if (cancelRequested) {
                runOnUiThread(() -> status.setText("● تم إيقاف الإجابة"));
                return;
            }
            final String answer = result;
            final String usedProvider = provider;
            runOnUiThread(() -> {
                responseBubble.setText("Mahdia AI\n" + answer);
                status.setText("● متصل عبر " + usedProvider + " — الخدمة العامة المجانية");
                status.setTextColor(0xFFFFC36B);
            });
        } catch (Exception e) {
            if (!cancelRequested) {
                String error = e.getMessage() == null ? "تعذر الاتصال بالخدمات الاحتياطية" : e.getMessage();
                runOnUiThread(() -> {
                    responseBubble.setText("Mahdia AI\nتعذر الاتصال بالخدمات الاحتياطية: " + error
                        + "\nاحتفظت برسالتك؛ يمكنك إعادة المحاولة لاحقاً.");
                    status.setText("● تعذر الاتصال بالخدمات الاحتياطية");
                    status.setTextColor(0xFFFF7777);
                    if (input.getText().toString().trim().isEmpty()) {
                        input.setText(userMessage);
                        input.setSelection(input.length());
                    }
                });
            }
        } finally {
            activeChatConnection = null;
            runOnUiThread(() -> {
                if (sendButton != null) sendButton.setEnabled(true);
                if (stopButton != null) stopButton.setEnabled(false);
            });
        }
    }

    private void runProviderEvaluation() {
        if (readApiToken().trim().isEmpty()) {
            Toast.makeText(this, "أدخل رمز الخادم أولاً من الإعدادات", Toast.LENGTH_LONG).show();
            endpointDialog();
            return;
        }
        status.setText("● يختبر الخادم مزودي الذكاء الاصطناعي...");
        status.setTextColor(0xFFFFC36B);
        executor.execute(() -> {
            HttpURLConnection connection = null;
            try {
                connection = openConnection("/api/admin/evaluate", "POST");
                JSONObject result = readJsonResponse(connection);
                JSONArray ranking = result.optJSONArray("ranking");
                StringBuilder report = new StringBuilder("اكتمل الاختبار باستخدام أسئلة تجريبية فقط.\n");
                if (ranking != null) {
                    for (int i = 0; i < ranking.length(); i++) {
                        JSONObject item = ranking.optJSONObject(i);
                        if (item == null) continue;
                        report.append(i + 1).append(") ")
                            .append(item.optString("name", item.optString("id", "مزود")))
                            .append(" — جودة ")
                            .append(item.optDouble("quality_score", 0))
                            .append(" — سرعة ")
                            .append(item.optInt("average_latency_ms", 0)).append(" ms\n");
                    }
                }
                final String message = report.toString();
                runOnUiThread(() -> {
                    addMessage("Mahdia AI", message);
                    status.setText("● انتهى الاختبار — تم تحديث ترتيب الخوادم");
                    status.setTextColor(0xFF62DCA8);
                });
            } catch (Exception e) {
                String error = e.getMessage() == null ? "تعذر إجراء الاختبار" : e.getMessage();
                runOnUiThread(() -> {
                    addMessage("Mahdia AI", "لم يكتمل اختبار الخوادم: " + error);
                    status.setText("● تعذر تحديث ترتيب الخوادم");
                    status.setTextColor(0xFFFF7777);
                });
            } finally {
                if (connection != null) connection.disconnect();
            }
        });
    }

    private String transientSessionToken = "";
    private boolean rememberSession = true;

    private String uiText(String arabic, String english, String french) {
        String language = prefs.getString("ui_language", "ar");
        if ("en".equals(language)) return english;
        if ("fr".equals(language)) return french;
        return arabic;
    }

    private String uiLanguageLabel() {
        return uiText("العربية", "English", "Français");
    }

    private void chooseUiLanguage(Dialog currentDialog) {
        String[] languages = {"العربية", "English", "Français"};
        new AlertDialog.Builder(this)
            .setTitle(uiText("اختر لغة شاشة الحساب", "Choose account screen language", "Choisir la langue de connexion"))
            .setItems(languages, (picker, which) -> {
                String selected = which == 1 ? "en" : which == 2 ? "fr" : "ar";
                prefs.edit().putString("ui_language", selected).apply();
                currentDialog.dismiss();
                accountDialog();
            })
            .setNegativeButton(uiText("إلغاء", "Cancel", "Annuler"), null)
            .show();
    }

    private void accountDialog() {
        Dialog dialog = new Dialog(this);
        dialog.requestWindowFeature(android.view.Window.FEATURE_NO_TITLE);

        ScrollView scrollView = new ScrollView(this);
        scrollView.setFillViewport(true);
        LinearLayout page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setPadding(dp(22), dp(24), dp(22), dp(22));
        android.graphics.drawable.GradientDrawable pageBg =
            new android.graphics.drawable.GradientDrawable(
                android.graphics.drawable.GradientDrawable.Orientation.TL_BR,
                new int[] { 0xFF050B25, 0xFF101A48, 0xFF090D29 });
        page.setBackground(pageBg);

        LinearLayout top = new LinearLayout(this);
        top.setGravity(Gravity.CENTER_VERTICAL);
        Button language = actionButton(uiLanguageLabel() + "  ▾", uiText("تغيير لغة شاشة الحساب", "Change account screen language", "Changer la langue de connexion"), () ->
            chooseUiLanguage(dialog));
        top.addView(language, new LinearLayout.LayoutParams(0, dp(42), 1));
        Button settings = actionButton("⚙", uiText("إعدادات الاتصال", "Connection settings", "Paramètres de connexion"), () -> {
            dialog.dismiss();
            endpointDialog();
        });
        top.addView(settings, new LinearLayout.LayoutParams(dp(48), dp(42)));
        page.addView(top);

        ImageView mascot = new ImageView(this);
        mascot.setImageResource(R.drawable.mahdia_hero_v2);
        mascot.setScaleType(ImageView.ScaleType.FIT_CENTER);
        mascot.setAdjustViewBounds(true);
        mascot.setContentDescription(uiText("روبوت Mahdia AI وقلعة المهدية", "Mahdia AI robot and Mahdia fortress", "Robot Mahdia AI et fort de Mahdia"));
        LinearLayout.LayoutParams mascotLp = new LinearLayout.LayoutParams(-1, dp(112));
        mascotLp.setMargins(0, dp(8), 0, dp(4));
        page.addView(mascot, mascotLp);

        TextView brand = new TextView(this);
        brand.setText("Mahdia AI");
        brand.setTextColor(Color.WHITE);
        brand.setTextSize(36);
        brand.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        brand.setGravity(Gravity.CENTER);
        page.addView(brand);

        TextView tagline = new TextView(this);
        tagline.setText(uiText("ذكاء اصطناعي ... بإبداع تونسي", "Artificial intelligence ... Tunisian creativity", "Intelligence artificielle ... créativité tunisienne"));
        tagline.setTextColor(0xFFE1E8FF);
        tagline.setTextSize(16);
        tagline.setGravity(Gravity.CENTER);
        tagline.setPadding(0, 0, 0, dp(18));
        page.addView(tagline);

        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(18), dp(20), dp(18), dp(18));
        android.graphics.drawable.GradientDrawable cardBg =
            new android.graphics.drawable.GradientDrawable(
                android.graphics.drawable.GradientDrawable.Orientation.TL_BR,
                new int[] { 0xEE111A43, 0xF20A1538 });
        cardBg.setCornerRadius(dp(26));
        cardBg.setStroke(dp(2), 0xFF7654F5);
        card.setBackground(cardBg);

        TextView heading = new TextView(this);
        heading.setText(uiText("مرحباً بك في Mahdia AI", "Welcome to Mahdia AI", "Bienvenue sur Mahdia AI"));
        heading.setTextColor(Color.WHITE);
        heading.setTextSize(24);
        heading.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        heading.setGravity(Gravity.CENTER);
        card.addView(heading);

        TextView subheading = new TextView(this);
        subheading.setText(uiText("سجّل الدخول إلى حسابك للمتابعة", "Sign in to your account to continue", "Connectez-vous pour continuer"));
        subheading.setTextColor(0xFFD2D9F4);
        subheading.setTextSize(15);
        subheading.setGravity(Gravity.CENTER);
        subheading.setPadding(0, dp(6), 0, dp(16));
        card.addView(subheading);

        EditText emailField = new EditText(this);
        emailField.setSingleLine(true);
        emailField.setHint(uiText("البريد الإلكتروني", "Email address", "Adresse e-mail"));
        emailField.setHintTextColor(0xFFB6C2E5);
        emailField.setTextColor(Color.WHITE);
        emailField.setTextSize(16);
        emailField.setInputType(android.text.InputType.TYPE_CLASS_TEXT
            | android.text.InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS);
        emailField.setPadding(dp(15), dp(12), dp(15), dp(12));
        emailField.setBackground(loginFieldBackground());
        LinearLayout.LayoutParams fieldLp = new LinearLayout.LayoutParams(-1, dp(58));
        fieldLp.setMargins(0, dp(10), 0, 0);
        card.addView(emailField, fieldLp);

        LinearLayout passwordRow = new LinearLayout(this);
        passwordRow.setGravity(Gravity.CENTER_VERTICAL);
        passwordRow.setBackground(loginFieldBackground());
        EditText passwordField = new EditText(this);
        passwordField.setSingleLine(true);
        passwordField.setHint(uiText("كلمة المرور", "Password", "Mot de passe"));
        passwordField.setHintTextColor(0xFFB6C2E5);
        passwordField.setTextColor(Color.WHITE);
        passwordField.setTextSize(16);
        passwordField.setInputType(android.text.InputType.TYPE_CLASS_TEXT
            | android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD);
        passwordField.setBackgroundColor(Color.TRANSPARENT);
        passwordField.setPadding(dp(15), dp(10), dp(8), dp(10));
        passwordRow.addView(passwordField, new LinearLayout.LayoutParams(0, -1, 1));
        final Button[] revealHolder = new Button[1];
        Button reveal = actionButton("◉", uiText("إظهار أو إخفاء كلمة المرور", "Show or hide password", "Afficher ou masquer le mot de passe"), () -> {
            boolean visible = (passwordField.getInputType() & 0xFFF)
                == (android.text.InputType.TYPE_CLASS_TEXT
                    | android.text.InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD);
            int cursor = passwordField.getSelectionStart();
            passwordField.setInputType(android.text.InputType.TYPE_CLASS_TEXT
                | (visible ? android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD
                           : android.text.InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD));
            passwordField.setSelection(Math.max(0, Math.min(cursor, passwordField.length())));
            revealHolder[0].setText(visible ? "◉" : "⊘");
        });
        revealHolder[0] = reveal;
        passwordRow.addView(reveal, new LinearLayout.LayoutParams(dp(48), -1));
        LinearLayout.LayoutParams passwordLp = new LinearLayout.LayoutParams(-1, dp(58));
        passwordLp.setMargins(0, dp(12), 0, 0);
        card.addView(passwordRow, passwordLp);

        LinearLayout options = new LinearLayout(this);
        options.setGravity(Gravity.CENTER_VERTICAL);
        CheckBox remember = new CheckBox(this);
        remember.setText(uiText("تذكّرني", "Remember me", "Se souvenir de moi"));
        remember.setTextColor(Color.WHITE);
        remember.setButtonTintList(android.content.res.ColorStateList.valueOf(0xFF9B5CFF));
        remember.setChecked(prefs.getBoolean("remember_session", true));
        rememberSession = remember.isChecked();
        options.addView(remember, new LinearLayout.LayoutParams(0, dp(48), 1));
        remember.setOnCheckedChangeListener((button, checked) -> {
            rememberSession = checked;
            prefs.edit().putBoolean("remember_session", checked).apply();
            if (!checked && readApiToken().startsWith("jss_")) {
                transientSessionToken = readApiToken();
                prefs.edit().remove("api_token_enc").remove("api_token_iv").remove("api_token").apply();
            }
        });
        Button forgot = actionButton(uiText("نسيت كلمة المرور؟", "Forgot password?", "Mot de passe oublié ?"), uiText("استعادة كلمة المرور", "Password recovery", "Récupération du mot de passe"), () ->
            new AlertDialog.Builder(this)
                .setTitle(uiText("استعادة كلمة المرور", "Password recovery", "Récupération du mot de passe"))
                .setMessage(uiText("استعادة كلمة المرور عبر البريد الإلكتروني غير مفعّلة على الخادم حالياً. لن نرسل رابطاً وهمياً.", "Email password recovery is not configured on the server yet. No fake link will be sent.", "La récupération par e-mail n'est pas encore configurée sur le serveur. Aucun faux lien ne sera envoyé."))
                .setPositiveButton(uiText("حسناً", "OK", "OK"), null).show());
        options.addView(forgot);
        card.addView(options);

        Button login = actionButton(uiText("دخول   ➜", "Sign in   ➜", "Connexion   ➜"), uiText("تسجيل الدخول", "Sign in", "Connexion"), () ->
            authenticateAccount(emailField.getText().toString(),
                passwordField.getText().toString(), false, dialog));
        login.setTextSize(18);
        login.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        login.setBackground(loginGradient());
        LinearLayout.LayoutParams loginLp = new LinearLayout.LayoutParams(-1, dp(58));
        loginLp.setMargins(0, dp(8), 0, dp(12));
        card.addView(login, loginLp);

        TextView or = new TextView(this);
        or.setText(uiText("أو", "OR", "OU"));
        or.setTextColor(Color.WHITE);
        or.setTextSize(15);
        or.setGravity(Gravity.CENTER);
        card.addView(or);

        Button google = actionButton("G   " + uiText("الدخول عبر Google", "Continue with Google", "Continuer avec Google"), uiText("تسجيل الدخول عبر Google", "Sign in with Google", "Connexion avec Google"), () ->
            new AlertDialog.Builder(this)
                .setTitle("Google")
                .setMessage(uiText("تسجيل Google غير مهيأ بعد: يتطلب إعداد OAuth موثوقاً في الخادم. لم نضع زرّاً وهمياً.", "Google sign-in is not configured yet; secure server-side OAuth setup is required.", "La connexion Google n'est pas encore configurée ; une configuration OAuth sécurisée côté serveur est nécessaire."))
                .setPositiveButton(uiText("حسناً", "OK", "OK"), null).show());
        google.setTextSize(16);
        google.setBackground(loginOutline());
        LinearLayout.LayoutParams googleLp = new LinearLayout.LayoutParams(-1, dp(54));
        googleLp.setMargins(0, dp(10), 0, dp(12));
        card.addView(google, googleLp);

        Button register = actionButton(uiText("إنشاء حساب جديد", "Create new account", "Créer un compte"), uiText("إنشاء حساب", "Create account", "Créer un compte"), () ->
            authenticateAccount(emailField.getText().toString(),
                passwordField.getText().toString(), true, dialog));
        register.setTextColor(0xFFD58BFF);
        card.addView(register);

        TextView secure = new TextView(this);
        secure.setText(uiText("◈ تسجيل آمن وخصوصي", "◈ Secure and private sign-in", "◈ Connexion sécurisée et privée"));
        secure.setTextColor(0xFFD7E2FF);
        secure.setGravity(Gravity.CENTER);
        secure.setPadding(0, dp(14), 0, 0);
        card.addView(secure);

        if (readApiToken().startsWith("jss_")) {
            Button logout = actionButton(uiText("تسجيل الخروج", "Sign out", "Se déconnecter"), uiText("تسجيل الخروج من الحساب", "Sign out of account", "Se déconnecter du compte"), () ->
                logoutAccount(new AlertDialog.Builder(this).create()));
            card.addView(logout);
        }

        page.addView(card);
        TextView footer = new TextView(this);
        footer.setText(uiText("Mahdia AI  •  شريكك الذكي في عالم المعرفة  ♥", "Mahdia AI  •  Your smart knowledge partner  ♥", "Mahdia AI  •  Votre partenaire intelligent du savoir  ♥"));
        footer.setTextColor(0xFFC49AFF);
        footer.setTextSize(13);
        footer.setGravity(Gravity.CENTER);
        footer.setPadding(0, dp(18), 0, dp(8));
        page.addView(footer);

        scrollView.addView(page);
        dialog.setContentView(scrollView);
        android.view.Window window = dialog.getWindow();
        if (window != null) {
            window.setBackgroundDrawableResource(android.R.color.transparent);
            window.setLayout(-1, -1);
        }
        dialog.show();
        if (dialog.getWindow() != null) dialog.getWindow().setLayout(-1, -1);
    }

    private android.graphics.drawable.Drawable loginFieldBackground() {
        android.graphics.drawable.GradientDrawable shape = new android.graphics.drawable.GradientDrawable();
        shape.setColor(0xFF101A3A);
        shape.setCornerRadius(dp(17));
        shape.setStroke(dp(1), 0xFF635AC0);
        return shape;
    }

    private android.graphics.drawable.Drawable loginGradient() {
        android.graphics.drawable.GradientDrawable shape =
            new android.graphics.drawable.GradientDrawable(
                android.graphics.drawable.GradientDrawable.Orientation.LEFT_RIGHT,
                new int[] { 0xFF8D22F7, 0xFF4E55FF, 0xFF00C9EF });
        shape.setCornerRadius(dp(30));
        return shape;
    }

    private android.graphics.drawable.Drawable loginOutline() {
        android.graphics.drawable.GradientDrawable shape = new android.graphics.drawable.GradientDrawable();
        shape.setColor(0x00101838);
        shape.setCornerRadius(dp(28));
        shape.setStroke(dp(2), 0xFF9878FF);
        return shape;
    }

    private void authenticateAccount(String email, String password, boolean register, Dialog dialog) {
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

    private void logoutAccount(Dialog dialog) {
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
        field.setText(prefs.getString("endpoint", DEFAULT_SERVER_URL));
        fields.addView(field);

        EditText tokenField = new EditText(this);
        tokenField.setSingleLine(true);
        tokenField.setHint("رمز إداري قديم (اختياري للمطور)");
        tokenField.setInputType(android.text.InputType.TYPE_CLASS_TEXT
            | android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD);
        tokenField.setText(readApiToken());
        fields.addView(tokenField);

        AlertDialog connectionDialog = new AlertDialog.Builder(this)
            .setTitle("اتصال خادم Mahdia AI")
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
                    if (!token.isEmpty()) saveApiToken(token);
                    prefs.edit().putString("endpoint", value).apply();
                    checkHealth();
                    if (!readApiToken().isEmpty()) {
                        loadHistory();
                    } else {
                        status.setText("● الخادم جاهز — سجّل الدخول للمتابعة");
                        status.setTextColor(0xFFFFC36B);
                    }
                } catch (Exception e) {
                    Toast.makeText(this, "تعذر حفظ الرمز بأمان على هذا الجهاز", Toast.LENGTH_LONG).show();
                }
            }).create();
        connectionDialog.setOnDismissListener(d -> {
            if (readApiToken().isEmpty() && !isFinishing()) accountDialog();
        });
        connectionDialog.show();
    }

    @Override protected void onDestroy() {
        super.onDestroy();
        executor.shutdown();
    }
}