package com.mashiro.czunet;

import android.annotation.SuppressLint;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.ConnectivityManager;
import android.net.NetworkCapabilities;
import android.net.NetworkInfo;
import android.os.Bundle;
import android.webkit.*;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {
    private WebView webView;
    private SharedPreferences prefs;
    private static final String LOGIN_URL = "http://172.19.0.1/";

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        prefs = getSharedPreferences("campus_login", MODE_PRIVATE);
        String user = prefs.getString("user", null);
        String pass = prefs.getString("pass", null);
        String isp = prefs.getString("isp", null);

        // 检查保存的账号信息
        if (user == null || pass == null || isp == null) {
            startActivity(new Intent(this, SettingsActivity.class));
            finish();
            return;
        }

        // ===== 网络状态检查 =====
        if (!isWifiConnected()) {
            Toast.makeText(this, "请打开Wi-Fi连接至校园网", Toast.LENGTH_LONG).show();
            finishAffinity();
            return;
        }
        if (isMobileDataEnabled()) {
            Toast.makeText(this, "请暂时关闭移动数据", Toast.LENGTH_LONG).show();
            finishAffinity();
            return;
        }

        // ===== 开始加载登录页 =====
        setContentView(R.layout.activity_main);
        webView = findViewById(R.id.webview);
        webView.getSettings().setJavaScriptEnabled(true);
        webView.getSettings().setDomStorageEnabled(true);
        webView.getSettings().setJavaScriptCanOpenWindowsAutomatically(true);
        webView.getSettings().setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);

        webView.setWebViewClient(new WebViewClient() {
            public void onPageFinished(WebView view, String url) {
                injectLoginScript(user, pass, isp);
            }
        });

        webView.loadUrl(LOGIN_URL);
    }

    private void injectLoginScript(String user, String pass, String isp) {
        // 根据运营商拼接 ISP value
        String ispValue = "";
        switch (isp) {
            case "中国移动":
                ispValue = "@cmcc";
                break;
            case "中国联通":
                ispValue = "@unicom";
                break;
            case "中国电信":
                ispValue = "@telecom";
                break;
            case "校园网":
            default:
                ispValue = "";
                break;
        }

        // 自动填充用户名、密码，并选择运营商
        String js = "javascript:(function(){"
                + "var u=document.getElementsByName('DDDDD')[0]; if(u) u.value='" + user + "';" // <-- 只填学号
                + "var p=document.getElementsByName('upass')[0]; if(p) p.value='" + pass + "';"
                + "var s=document.getElementsByName('ISP_select')[0];"
                + "if(s){ for(var i=0;i<s.options.length;i++){ if(s.options[i].value=='" + ispValue + "'){ s.selectedIndex=i; }}}"
                + "var btn=document.getElementsByName('0MKKey')[0]; if(btn) btn.click();"
                + "})();";
        webView.evaluateJavascript(js, null);

        // 延迟检查是否登录成功
        webView.postDelayed(() -> webView.evaluateJavascript(
                "(function(){return document.body.innerText.includes('成功登录');})();",
                value -> {
                    if ("true".equals(value)) {
                        Toast.makeText(this, "登录成功，即将退出", Toast.LENGTH_SHORT).show();
                        finishAffinity();
                    }
                }), 450);
    }


    /** 检查 Wi-Fi 是否连接 */
    private boolean isWifiConnected() {
        ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
        if (cm == null) return false;
        NetworkInfo info = cm.getActiveNetworkInfo();
        return info != null && info.isConnected() && info.getType() == ConnectivityManager.TYPE_WIFI;
    }

    /** 检查移动数据是否开启 */
    private boolean isMobileDataEnabled() {
        ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
        if (cm == null) return false;

        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.M) {
            NetworkCapabilities caps = cm.getNetworkCapabilities(cm.getActiveNetwork());
            return caps != null && caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR);
        } else {
            NetworkInfo info = cm.getNetworkInfo(ConnectivityManager.TYPE_MOBILE);
            return info != null && info.isConnected();
        }
    }
}
