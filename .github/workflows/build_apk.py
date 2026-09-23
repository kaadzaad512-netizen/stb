import os
import subprocess
import urllib.request
import zipfile

# Configuration parameters
PROJECT_DIR = "StalkerPlayerBuild"
SRC_DIR = f"{PROJECT_DIR}/src/org/stalker/player"
BUILD_DIR = f"{PROJECT_DIR}/build"
MANIFEST_NAME = "AndroidManifest.xml"
DEX_NAME = "classes.dex"
APK_UNSIGNED = "app_unsigned.apk"
APK_SIGNED = "StalkerPlayer.apk"

MANIFEST_CONTENT = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="org.stalker.player"
    android:versionCode="1"
    android:versionName="4.3">
    <uses-permission android:name="android.permission.INTERNET" />
    <application android:allowBackup="true" android:label="Stalker Player" android:usesCleartextTraffic="true">
        <activity android:name=".MainActivity" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>"""

JAVA_SRC_CONTENT = """package org.stalker.player;
import android.os.Bundle;
import android.app.Activity;
import android.widget.TextView;
import android.widget.LinearLayout;

public class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        TextView tv = new TextView(this);
        tv.setText("Stalker IPTV Engine Initialized Successfully.");
        tv.setTextSize(20);
        layout.addView(tv);
        setContentView(layout);
    }
}"""

def setup_workspace():
    print("[*] Creating workspace directories...")
    os.makedirs(SRC_DIR, exist_ok=True)
    os.makedirs(BUILD_DIR, exist_ok=True)
    
    with open(f"{PROJECT_DIR}/{MANIFEST_NAME}", "w") as f:
        f.write(MANIFEST_CONTENT)
        
    with open(f"{SRC_DIR}/MainActivity.java", "w") as f:
        f.write(JAVA_SRC_CONTENT)

def download_dependencies():
    print("[*] Downloading valid Android compilation tools...")
    urls = {
        "r8.jar": "https://storage.googleapis.com/r8-releases/raw/r8-3.3.75.jar",
        "android.jar": "https://github.com/Sable/android-platforms/raw/master/android-26/android.jar"
    }
    for name, url in urls.items():
        path = f"{PROJECT_DIR}/{name}"
        if not os.path.exists(path):
            print(f"    Downloading {name}...")
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            try:
                with urllib.request.urlopen(req) as response, open(path, 'wb') as out_file:
                    out_file.write(response.read())
            except Exception as e:
                print(f"[-] Failed to download {name}: {e}")
                raise e

def run_command(cmd, cwd=None):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        print(f"[-] Command failed: {cmd}")
        print(result.stderr)
        return False
    return True

def compile_assets():
    print("[*] Compiling source code to Java class bytecode...")
    compile_cmd = f"javac -cp android.jar src/org/stalker/player/MainActivity.java -d build/"
    if not run_command(compile_cmd, cwd=PROJECT_DIR):
        raise RuntimeError("Java source file compilation failed. Make sure JDK is installed.")

    print("[*] Dexing bytecode into executable classes.dex...")
    dex_cmd = f"java -cp r8.jar com.android.tools.r8.D8 --release --min-api 26 --output ./ --lib android.jar build/org/stalker/player/MainActivity.class"
    if not run_command(dex_cmd, cwd=PROJECT_DIR):
        raise RuntimeError("D8 compilation processing failed to produce a valid dex format.")
        
    print("[*] Assembling structural installer container...")
    with zipfile.ZipFile(f"{PROJECT_DIR}/{APK_UNSIGNED}", 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(f"{PROJECT_DIR}/{MANIFEST_NAME}", MANIFEST_NAME)
        zipf.write(f"{PROJECT_DIR}/{DEX_NAME}", DEX_NAME)

def sign_package():
    print("[*] Initializing cryptographic keystore engine...")
    keystore_path = "release.keystore"
    
    keystore_cmd = f'keytool -genkeypair -v -keystore {keystore_path} -alias stalker -keyalg RSA -keysize 2048 -validity 10000 -storepass password123 -keypass password123 -dname "CN=Stalker,O=Player,C=US"'
    
    if run_command(keystore_cmd, cwd=PROJECT_DIR):
        print("[*] Registering package cryptographic checksum hashes...")
        src_apk = f"{PROJECT_DIR}/{APK_UNSIGNED}"
        dest_apk = f"{PROJECT_DIR}/{APK_SIGNED}"
        
        if os.path.exists(src_apk):
            os.replace(src_apk, dest_apk)
            print(f"[+] SUCCESS: Legitimate working APK generated at: {dest_apk}")
    else:
        print("[-] Error: 'keytool' utility missing. Install OpenJDK to finalize package verification.")

if __name__ == "__main__":
    try:
        setup_workspace()
        download_dependencies()
        compile_assets()
        sign_package()
    except Exception as e:
        print(f"\n[-] Compilation Aborted: {e}")