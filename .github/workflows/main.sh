#!/usr/bin/env bash
# ============================================================
#  create_stalker_player.sh
#  Generates the complete Stalker Player Android project
#  (Kotlin + ExoPlayer/FFmpeg + GitHub Actions CI) as a zip.
#  Works on: Linux / macOS / WSL / Termux (pkg install zip)
#  Requires: bash, zip (gradle optional)
# ============================================================
set -e

ROOT="stalker-player"

rm -rf "$ROOT"
mkdir -p "$ROOT/.github/workflows" \
         "$ROOT/gradle/wrapper" \
         "$ROOT/app/src/main/res/values" \
         "$ROOT/app/src/main/res/layout" \
         "$ROOT/app/src/main/java/com/example/stalker"

cd "$ROOT"

# ------------------------------------------------------------ main.yml
# If the local wrapper jar is generated below, CI runs ./gradlew directly.
# Otherwise CI generates the wrapper itself (GRADLE_WRAPPER_CI marker).
cat > .github/workflows/main.yml <<'EOF'
name: Build Stalker Player APK

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up JDK 17
        uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: '17'

      - name: Setup Gradle
        uses: gradle/actions/setup-gradle@v3

      # GRADLE_WRAPPER_CI: generate wrapper on the runner if not committed
      - name: Generate Gradle wrapper (if missing)
        run: |
          if [ ! -f gradlew ]; then
            gradle wrapper --gradle-version 8.7
          fi

      - name: Grant execute permission to gradlew
        run: chmod +x gradlew

      - name: Build debug APK (ExoPlayer + FFmpeg)
        run: ./gradlew assembleDebug --stacktrace

      - name: Upload APK artifact
        uses: actions/upload-artifact@v4
        with:
          name: StalkerPlayer-debug-apk
          path: app/build/outputs/apk/debug/app-debug.apk

      - name: Release on tag
        if: startsWith(github.ref, 'refs/tags/')
        uses: softprops/action-gh-release@v2
        with:
          files: app/build/outputs/apk/debug/app-debug.apk
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
EOF

# ------------------------------------------------------------ root gradle files
cat > settings.gradle.kts <<'EOF'
pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }
dependencyResolutionManagement { repositories { google(); mavenCentral() } }
rootProject.name = "StalkerPlayer"
include(":app")
EOF

cat > build.gradle.kts <<'EOF'
plugins {
    id("com.android.application") version "8.5.2" apply false
    id("org.jetbrains.kotlin.android") version "1.9.24" apply false
}
EOF

cat > gradle.properties <<'EOF'
org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
android.useAndroidX=true
android.nonTransitiveRClass=true
EOF

cat > gradle/wrapper/gradle-wrapper.properties <<'EOF'
distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\://services.gradle.org/distributions/gradle-8.7-bin.zip
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
EOF

# ------------------------------------------------------------ app/build.gradle.kts
cat > app/build.gradle.kts <<'EOF'
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.example.stalker"
    compileSdk = 34
    defaultConfig {
        applicationId = "com.example.stalker"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.recyclerview:recyclerview:1.3.2")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")

    // Built-in player: ExoPlayer (Media3) + FFmpeg audio decoders
    implementation("androidx.media3:media3-exoplayer:1.4.1")
    implementation("androidx.media3:media3-ui:1.4.1")
    implementation("androidx.media3:media3-exoplayer-hls:1.4.1")
    implementation("androidx.media3:media3-exoplayer-ffmpeg:1.4.1")
}
EOF

# ------------------------------------------------------------ manifest
cat > app/src/main/AndroidManifest.xml <<'EOF'
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET"/>
    <application
        android:label="@string/app_name"
        android:usesCleartextTraffic="true"
        android:theme="@style/AppTheme">
        <activity android:name=".MainActivity" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
        <activity android:name=".PlayerActivity"
            android:configChanges="orientation|screenSize|keyboardHidden"
            android:exported="false"/>
    </application>
</manifest>
EOF

# ------------------------------------------------------------ res/values
cat > app/src/main/res/values/strings.xml <<'EOF'
<resources>
    <string name="app_name">Stalker Player</string>
</resources>
EOF

cat > app/src/main/res/values/themes.xml <<'EOF'
<resources>
    <style name="AppTheme" parent="@android:style/Theme.Material.Light.NoActionBar"/>
</resources>
EOF

# ------------------------------------------------------------ res/layout
cat > app/src/main/res/layout/activity_main.xml <<'EOF'
<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:orientation="vertical"
    android:padding="16dp">
    <EditText android:id="@+id/portal_input"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:hint="Portal URL (http://host:8080/c)" android:inputType="textUri"/>
    <EditText android:id="@+id/mac_input"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:hint="MAC (00:1A:79:D1:FC:C2)" android:inputType="textCapCharacters"/>
    <Button android:id="@+id/connect_btn"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="Connect"/>
    <TextView android:id="@+id/status"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:paddingTop="8dp"/>
    <EditText android:id="@+id/search_input"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:hint="Search channels…" android:inputType="text"/>
    <androidx.recyclerview.widget.RecyclerView
        android:id="@+id/channel_list"
        android:layout_width="match_parent" android:layout_height="0dp"
        android:layout_weight="1"/>
</LinearLayout>
EOF

cat > app/src/main/res/layout/item_channel.xml <<'EOF'
<?xml version="1.0" encoding="utf-8"?>
<TextView xmlns:android="http://schemas.android.com/apk/res/android"
    android:id="@+id/channel_name"
    android:layout_width="match_parent" android:layout_height="wrap_content"
    android:padding="12dp" android:textSize="16sp"/>
EOF

cat > app/src/main/res/layout/activity_player.xml <<'EOF'
<?xml version="1.0" encoding="utf-8"?>
<FrameLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent" android:layout_height="match_parent">
    <androidx.media3.ui.PlayerView
        android:id="@+id/player_view"
        android:layout_width="match_parent" android:layout_height="match_parent"/>
</FrameLayout>
EOF

# ------------------------------------------------------------ StalkerClient.kt
cat > app/src/main/java/com/example/stalker/StalkerClient.kt <<'EOF'
package com.example.stalker

import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import org.json.JSONObject
import java.net.URLEncoder
import java.util.concurrent.TimeUnit

data class Channel(val id: String, val name: String, val num: String, val genreId: String)

class StalkerClient(portalBase: String, macRaw: String) {

    companion object {
        private val UA = "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 " +
                "(KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3"
        private const val XUA = "Model: MAG250; Link: WiFi"
    }

    val mac: String = normalizeMac(macRaw) ?: throw IllegalArgumentException("Invalid MAC")

    private val portalCandidates: List<String>
    var portal: String = ""
        private set
    private var token: String? = null

    private val http = OkHttpClient.Builder()
        .connectTimeout(12, TimeUnit.SECONDS)
        .readTimeout(12, TimeUnit.SECONDS)
        .build()

    init {
        val raw = portalBase.trim().trimEnd('/')
        portalCandidates = if (raw.endsWith("/portal.php")) listOf(raw)
        else if (raw.endsWith("/c")) listOf(
            "$raw/portal.php",
            raw.removeSuffix("/c").trimEnd('/') + "/portal.php")
        else listOf("$raw/c/portal.php", "$raw/portal.php", "$raw/server/portal.php")
        portal = portalCandidates.first()
    }

    private fun normalizeMac(raw: String): String? {
        val d = raw.uppercase().filter { it in "0123456789ABCDEF" }
        if (d.length != 12) return null
        return d.chunked(2).joinToString(":")
    }

    private fun get(vararg params: String): JSONObject {
        val qs = params.joinToString("&") {
            val i = it.indexOf('=')
            URLEncoder.encode(it.substring(0, i), "UTF-8") + "=" +
                    URLEncoder.encode(it.substring(i + 1), "UTF-8")
        }
        val urls = if (token != null) listOf(portal) else portalCandidates
        var lastErr: Exception? = null
        for (url in urls) {
            try {
                val b = Request.Builder().url("$url?$qs")
                    .header("User-Agent", UA)
                    .header("X-User-Agent", XUA)
                    .header("Referer", "http://localhost/stalker_portal/c/")
                    .header("Cookie", "mac=$mac; stb_lang=en; timezone=Europe/London")
                token?.let { b.header("Authorization", "Bearer $it") }
                http.newCall(b.build()).execute().use { r ->
                    if (r.code != 200) throw RuntimeException("HTTP ${r.code} from $url")
                    val body = r.body?.string() ?: ""
                    if (body.isBlank()) throw RuntimeException("empty body from $url")
                    portal = url
                    return JSONObject(body)
                }
            } catch (e: Exception) { lastErr = e }
        }
        throw RuntimeException("Portal request failed: ${lastErr?.message}")
    }

    fun handshake(): String {
        val tok = get("type=stb", "action=handshake", "JsHttpRequest=1-xml")
            .optJSONObject("js")?.optString("token")?.split("~")?.first() ?: ""
        require(tok.isNotEmpty()) { "handshake ok but no token" }
        token = tok
        return tok
    }

    fun getProfile(): JSONObject =
        get("type=stb", "action=get_profile", "JsHttpRequest=1-xml")
            .optJSONObject("js") ?: JSONObject()

    fun getMainInfo(): JSONObject {
        var js = get("type=account_info", "action=get_main_info", "JsHttpRequest=1-xml").opt("js")
        if (js is JSONArray && js.length() > 0) js = js.get(0)
        return js as? JSONObject ?: JSONObject()
    }

    fun getGenres(): Map<String, String> = try {
        val arr = get("type=itv", "action=get_genres", "JsHttpRequest=1-xml")
            .optJSONArray("js") ?: JSONArray()
        (0 until arr.length()).mapNotNull { i ->
            val g = arr.optJSONObject(i) ?: return@mapNotNull null
            g.optString("id") to g.optString("title")
        }.toMap()
    } catch (e: Exception) { emptyMap() }

    fun getAllChannels(onProgress: (Int, Int) -> Unit = { _, _ -> }): List<Channel> {
        val chans = mutableListOf<JSONObject>()
        try {
            val js = get("type=itv", "action=get_all_channels", "JsHttpRequest=1-xml").opt("js")
            val data = (js as? JSONObject)?.optJSONArray("data") ?: (js as? JSONArray) ?: JSONArray()
            (0 until data.length()).forEach { data.optJSONObject(it)?.let(chans::add) }
        } catch (_: Exception) {}
        if (chans.isEmpty()) {
            var page = 1
            while (true) {
                val js = try {
                    get("type=itv", "action=get_ordered_list", "JsHttpRequest=1-xml",
                        "type_itv=1", "p=$page").opt("js")
                } catch (_: Exception) { break }
                val data = (js as? JSONObject)?.optJSONArray("data") ?: (js as? JSONArray) ?: break
                if (data.length() == 0) break
                (0 until data.length()).forEach { data.optJSONObject(it)?.let(chans::add) }
                onProgress(page, chans.size)
                val maxPage = (js as? JSONObject)?.optInt("max_page", 1) ?: 1
                if (page >= maxPage) break
                page++
            }
        }
        val seen = HashSet<String>()
        return chans.mapNotNull { ch ->
            val id = ch.optString("id")
            if (id.isEmpty() || !seen.add(id)) return@mapNotNull null
            Channel(id, ch.optString("name", "?"), ch.opt("number")?.toString() ?: "",
                ch.optString("tv_genre_id", ""))
        }
    }

    fun createLink(channelId: String): String {
        val cmd = get("type=itv", "action=create_link", "JsHttpRequest=1-xml",
            "cmd=ffmpeg http://localhost/ch/$channelId")
            .optJSONObject("js")?.optString("cmd") ?: ""
        return cmd.removePrefix("ffmpeg ").removePrefix("vlc ").removePrefix("http ")
    }
}
EOF

# ------------------------------------------------------------ ChannelAdapter.kt
cat > app/src/main/java/com/example/stalker/ChannelAdapter.kt <<'EOF'
package com.example.stalker

import android.view.LayoutInflater
import android.view.ViewGroup
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView

class ChannelAdapter(
    private var channels: List<Channel>,
    private val onClick: (Channel) -> Unit
) : RecyclerView.Adapter<ChannelAdapter.VH>() {

    class VH(val tv: TextView) : RecyclerView.ViewHolder(tv)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) =
        VH(LayoutInflater.from(parent.context)
            .inflate(R.layout.item_channel, parent, false) as TextView)

    override fun onBindViewHolder(h: VH, pos: Int) {
        val ch = channels[pos]
        h.tv.text = "${ch.num}  ${ch.name}"
        h.tv.setOnClickListener { onClick(ch) }
    }

    override fun getItemCount() = channels.size

    fun update(newList: List<Channel>) {
        channels = newList
        notifyDataSetChanged()
    }
}
EOF

# ------------------------------------------------------------ MainActivity.kt
cat > app/src/main/java/com/example/stalker/MainActivity.kt <<'EOF'
package com.example.stalker

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.widget.*
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import kotlin.concurrent.thread

class MainActivity : Activity() {

    private lateinit var client: StalkerClient
    private var allChannels = listOf<Channel>()
    private lateinit var adapter: ChannelAdapter
    private lateinit var status: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        val portalEt = findViewById<EditText>(R.id.portal_input)
        val macEt = findViewById<EditText>(R.id.mac_input)
        val searchEt = findViewById<EditText>(R.id.search_input)
        status = findViewById(R.id.status)
        val list = findViewById<RecyclerView>(R.id.channel_list)

        adapter = ChannelAdapter(emptyList()) { ch -> playChannel(ch) }
        list.layoutManager = LinearLayoutManager(this)
        list.adapter = adapter

        searchEt.setOnEditorActionListener { _, _, _ ->
            val q = searchEt.text.toString().trim().lowercase()
            adapter.update(allChannels.filter { q in it.name.lowercase() })
            true
        }

        findViewById<Button>(R.id.connect_btn).setOnClickListener {
            status.text = "Connecting…"
            thread {
                try {
                    client = StalkerClient(portalEt.text.toString(), macEt.text.toString())
                    val token = client.handshake()
                    client.getProfile()
                    val acc = client.getMainInfo()
                    allChannels = client.getAllChannels().sortedBy {
                        it.num.toIntOrNull() ?: 999
                    }
                    val genres = client.getGenres()
                    runOnUiThread {
                        status.text = "Token: ${token.take(16)}…\n" +
                                "Expiry: ${acc.optString("phone", "n/a")}\n" +
                                "${allChannels.size} channels, ${genres.size} genres"
                        adapter.update(allChannels)
                    }
                } catch (e: Exception) {
                    runOnUiThread { status.text = "Connect failed: ${e.message}" }
                }
            }
        }
    }

    private fun playChannel(ch: Channel) {
        status.text = "Resolving ${ch.name}…"
        thread {
            try {
                val url = client.createLink(ch.id)
                if (url.isEmpty()) throw RuntimeException("No stream URL returned")
                runOnUiThread {
                    startActivity(Intent(this, PlayerActivity::class.java)
                        .putExtra("url", url))
                }
            } catch (e: Exception) {
                runOnUiThread {
                    Toast.makeText(this, "create_link failed: ${e.message}",
                        Toast.LENGTH_LONG).show()
                }
            }
        }
    }
}
EOF

# ------------------------------------------------------------ PlayerActivity.kt
cat > app/src/main/java/com/example/stalker/PlayerActivity.kt <<'EOF'
package com.example.stalker

import android.app.Activity
import android.content.pm.ActivityInfo
import android.os.Bundle
import android.widget.Toast
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.exoplayer.DefaultRenderersFactory
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.ui.PlayerView

class PlayerActivity : Activity() {

    private var player: ExoPlayer? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
        setContentView(R.layout.activity_player)

        val url = intent.getStringExtra("url") ?: run { finish(); return }

        // FFmpeg extension renderers, used when platform decoders can't handle a codec
        val renderers = DefaultRenderersFactory(this)
            .setEnableDecoderFallback(true)
            .setExtensionRendererMode(DefaultRenderersFactory.EXTENSION_RENDERER_MODE_ON)

        val httpFactory = DefaultHttpDataSource.Factory()
            .setUserAgent("Mozilla/5.0 (QtEmbedded; U; Linux; C) MAG200 stbapp")
            .setAllowCrossProtocolRedirects(true)

        player = ExoPlayer.Builder(this, renderers)
            .setMediaSourceFactory(DefaultMediaSourceFactory(httpFactory))
            .build()
            .also { p ->
                findViewById<PlayerView>(R.id.player_view).player = p
                p.setMediaItem(MediaItem.Builder()
                    .setUri(url)
                    .setMimeType(if (url.contains(".m3u8")) MimeTypes.APPLICATION_M3U8 else null)
                    .build())
                p.addListener(object : Player.Listener {
                    override fun onPlayerError(error: PlaybackException) {
                        Toast.makeText(this@PlayerActivity,
                            "Playback error: ${error.errorCodeName}",
                            Toast.LENGTH_LONG).show()
                    }
                })
                p.prepare()
                p.playWhenReady = true
            }
    }

    override fun onStop() {
        super.onStop()
        player?.release()
        player = null
    }
}
EOF

# ------------------------------------------------------------ generate wrapper locally if possible
if command -v gradle >/dev/null 2>&1; then
    echo "[*] Gradle found — generating wrapper locally..."
    gradle wrapper --gradle-version 8.7
else
    echo "[*] Gradle not found locally — CI will generate the wrapper (already handled in main.yml)."
fi

# ------------------------------------------------------------ zip it
cd ..
rm -f stalker-player.zip
zip -r stalker-player.zip stalker-player

echo ""
echo "=============================================="
echo " ✅ stalker-player.zip created"
echo " Next steps:"
echo "   1. Unzip:               unzip stalker-player.zip"
echo "   2. Push to GitHub:      cd stalker-player && git init && git add ."
echo "                           git commit -m 'init' && git push -u origin main"
echo "   3. GitHub Actions builds the APK automatically"
echo "   4. Download 'StalkerPlayer-debug-apk' from Actions artifacts"
echo "=============================================="
