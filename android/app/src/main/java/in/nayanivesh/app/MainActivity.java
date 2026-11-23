package in.nayanivesh.app;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Naya Nivesh: the IPO app runs from assets/index.html in a full-screen WebView.
 * The page refreshes its own data: it asks this activity (through the "NayaNivesh"
 * bridge) to download public IPO pages, then parses them itself and saves the result
 * on the phone. No server, website or account is involved.
 */
public class MainActivity extends Activity {
    private static final String[] ALLOWED_HOSTS = {"www.gmpipowatch.in", "gmpipowatch.in", "ipowatch.in", "www.ipowatch.in"};
    private WebView web;
    private final ExecutorService pool = Executors.newFixedThreadPool(3);

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Color.parseColor("#0f1a2a"));
        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);   // saved IPO data + your applications live here
        s.setAllowFileAccess(true);
        web.addJavascriptInterface(new Bridge(), "NayaNivesh");
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                Uri u = r.getUrl();
                if ("file".equals(u.getScheme())) return false;
                startActivity(new Intent(Intent.ACTION_VIEW, u)); // registrar / BSE / NSE links open in the browser
                return true;
            }
        });
        if (state != null) web.restoreState(state);
        else web.loadUrl("file:///android_asset/index.html");
        setContentView(web);
    }

    @Override protected void onSaveInstanceState(Bundle out) { super.onSaveInstanceState(out); web.saveState(out); }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack(); else super.onBackPressed();
    }

    @Override protected void onDestroy() { pool.shutdownNow(); super.onDestroy(); }

    private static boolean allowed(String url) {
        try {
            URL u = new URL(url);
            if (!"https".equals(u.getProtocol())) return false;
            for (String h : ALLOWED_HOSTS) if (h.equalsIgnoreCase(u.getHost())) return true;
        } catch (Exception ignored) { }
        return false;
    }

    private static String download(String url) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(15000);
        c.setReadTimeout(20000);
        c.setInstanceFollowRedirects(true);
        c.setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36");
        c.setRequestProperty("Accept-Language", "en-IN,en;q=0.9");
        try {
            if (c.getResponseCode() != 200) return null;
            try (InputStream in = c.getInputStream(); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
                byte[] buf = new byte[16384];
                int n, total = 0;
                while ((n = in.read(buf)) > 0 && total < 4_000_000) { out.write(buf, 0, n); total += n; }
                return out.toString(StandardCharsets.UTF_8.name());
            }
        } finally { c.disconnect(); }
    }

    class Bridge {
        /** Downloads a public IPO page in the background and hands its HTML back to the page. */
        @JavascriptInterface
        public void fetch(final String id, final String url) {
            pool.execute(() -> {
                String body = null;
                if (allowed(url)) {
                    try { body = download(url); } catch (Exception ignored) { }
                }
                final String js = "window.__nnCb(" + JSONObject.quote(id) + "," + (body != null) + ","
                        + JSONObject.quote(body == null ? "" : body) + ")";
                web.post(() -> web.evaluateJavascript(js, null));
            });
        }
    }
}
