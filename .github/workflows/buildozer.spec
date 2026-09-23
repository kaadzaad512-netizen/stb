[app]
title = IPTV Player
package.name = iptvplayer
package.domain = org.iptvplayer
source.dir = .
source.include_exts = py
version = 4.3

# requests = your portal client, pyjnius = launch VLC/mpv via Android Intent
requirements = python3,kivy==2.3.0,requests,pyjnius

orientation = portrait
fullscreen = 0

android.permissions = INTERNET
android.api = 34
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
