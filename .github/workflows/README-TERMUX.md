# Stalker IPTV Player — Android project

Built from the uploaded Python Stalker Portal player as a native Kotlin/Android app.

Included:
- Portal URL + authorized manual MAC entry
- Stalker handshake/token
- get_profile and account_info/get_main_info
- itv/get_genres and itv/get_all_channels
- itv/create_link
- Channel search
- Android Media3 playback

The Python script's automatic MAC-generation/brute-force feature is not included. Use a MAC address you are authorized to use.

## Build in Termux

Install Java and Gradle:
    pkg update
    pkg install openjdk-17 gradle

You also need Android SDK command-line tools, with:
    ANDROID_HOME=$HOME/android-sdk
    PATH=$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH

Then install:
    sdkmanager "platform-tools" "platforms;android-35" "build-tools;35.0.0"

From this project:
    gradle assembleDebug

APK:
    app/build/outputs/apk/debug/app-debug.apk

This ZIP is build-ready source, not a precompiled APK.
