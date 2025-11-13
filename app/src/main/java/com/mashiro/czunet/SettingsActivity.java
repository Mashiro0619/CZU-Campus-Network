package com.mashiro.czunet;


import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.widget.*;
import androidx.appcompat.app.AppCompatActivity;

public class SettingsActivity extends AppCompatActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_settings);

        EditText user = findViewById(R.id.user);
        EditText pass = findViewById(R.id.pass);
        Spinner isp = findViewById(R.id.isp);
        Button save = findViewById(R.id.save);

        save.setOnClickListener(v -> {
            SharedPreferences.Editor editor = getSharedPreferences("campus_login", MODE_PRIVATE).edit();
            editor.putString("user", user.getText().toString().trim());
            editor.putString("pass", pass.getText().toString().trim());
            editor.putString("isp", isp.getSelectedItem().toString());
            editor.apply();

            startActivity(new Intent(this, MainActivity.class));
            finish();
        });
    }
}
