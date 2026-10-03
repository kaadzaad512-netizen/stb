#!/usr/bin/env python3
import os
import sys
import json
import time
import random
import threading
from datetime import datetime
from queue import Queue

# Core Kivy Framework
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.behaviors import ClickableBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty, ListProperty, BooleanProperty, NumericProperty
from kivy.clock import Clock
from kivy.core.window import Window

# UI Components from KivyMD
from kivymd.app import MDApp
from kivymd.uix.card import MDCard
from kivymd.uix.chip import MDChip
from kivymd.uix.list import OneLineListItem

# Networking & Backend Dependencies
import requests

# Set default window size for testing on desktop environments
Window.size = (400, 700)

# =========================================================================
# Kivy KV Layout String (Declares Widgets and Styles)
# =========================================================================
KV = """
ScreenManager:
    LoginScreen:
    MainScreen:
    VideoScreen:

<LoginScreen>:
    name: 'login'
    canvas.before:
        Color:
            rgba: 0.04, 0.06, 0.13, 1  # Deep Blue #0B1020
        Rectangle:
            pos: self.pos
            size: self.size

    BoxLayout:
        orientation: 'vertical'
        padding: dp(20)
        spacing: dp(15)

        MDLabel:
            text: "STB Player Pro"
            halign: "center"
            font_style: "H4"
            theme_text_color: "Custom"
            text_color: 0.13, 0.77, 0.37, 1  # Accent Green #22C55E
            size_hint_y: None
            height: dp(60)

        MDLabel:
            text: root.status_text
            halign: "center"
            font_style: "Caption"
            theme_text_color: "Secondary"
            size_hint_y: None
            height: dp(30)

        MDTextField:
            id: portal_url
            hint_text: "Portal URL (e.g. http://domain.com:8080/c)"
            text: "http://"
            mode: "rectangle"
            fill_color_normal: 0.06, 0.10, 0.20, 1
            line_color_normal: 0.2, 0.2, 0.4, 1

        BoxLayout:
            orientation: 'horizontal'
            spacing: dp(10)
            size_hint_y: None
            height: dp(56)
            
            MDTextField:
                id: mac_address
                hint_text: "MAC Address"
                mode: "rectangle"
                fill_color_normal: 0.06, 0.10, 0.20, 1
            
            MDRaisedButton:
                text: "Connect"
                md_bg_color: 0.13, 0.77, 0.37, 1
                size_hint_y: None
                height: dp(56)
                on_release: root.perform_connect()

        BoxLayout:
            orientation: 'horizontal'
            spacing: dp(10)
            size_hint_y: None
            height: dp(56)

            MDTextField:
                id: scan_prefix
                hint_text: "Prefix"
                text: "00:1A:79"
                mode: "rectangle"
                fill_color_normal: 0.06, 0.10, 0.20, 1

            MDTextField:
                id: scan_count
                hint_text: "Count"
                text: "50"
                mode: "rectangle"
                fill_color_normal: 0.06, 0.10, 0.20, 1

            MDRaisedButton:
                text: "Scan"
                md_bg_color: 0.5, 0.2, 0.6, 1
                size_hint_y: None
                height: dp(56)
                on_release: root.perform_scan()

        MDLabel:
            text: "Active Hits (Tap to Load):"
            font_style: "Subtitle2"
            theme_text_color: "Custom"
            text_color: 0.13, 0.77, 0.37, 1
            size_hint_y: None
            height: dp(25) if len(root.hit_list) > 0 else 0
            opacity: 1 if len(root.hit_list) > 0 else 0

        ScrollView:
            size_hint_y: 1
            MDSelectionList:
                id: hit_container

<MainScreen>:
    name: 'main'
    canvas.before:
        Color:
            rgba: 0.04, 0.06, 0.13, 1
        Rectangle:
            pos: self.pos
            size: self.size

    BoxLayout:
        orientation: 'vertical'
        padding: dp(14)
        spacing: dp(10)

        BoxLayout:
            orientation: 'horizontal'
            size_hint_y: None
            height: dp(40)
            
            MDLabel:
                text: "Channels"
                font_style: "H5"
                theme_text_color: "Custom"
                text_color: 0.13, 0.77, 0.37, 1
            
            MDIconButton:
                icon: "logout"
                pos_hint: {"center_y": .5}
                on_release: root.logout()

        MDLabel:
            text: root.session_info
            font_style: "Caption"
            theme_text_color: "Secondary"
            size_hint_y: None
            height: dp(20)

        BoxLayout:
            orientation: 'horizontal'
            spacing: dp(5)
            size_hint_y: None
            height: dp(40)
            
            MDChip:
                text: "Live"
                selected: root.current_tab == 0
                on_release: root.switch_tab(0)
            MDChip:
                text: "VOD"
                selected: root.current_tab == 1
                on_release: root.switch_tab(1)
            MDChip:
                text: "Series"
                selected: root.current_tab == 2
                on_release: root.switch_tab(2)

        MDTextField:
            id: search_bar
            hint_text: "Search by channel name..."
            mode: "rectangle"
            size_hint_y: None
            height: dp(45)
            on_text: root.filter_channels(self.text)

        ScrollView:
            MDList:
                id: channel_container

<VideoScreen>:
    name: 'video'
    BoxLayout:
        orientation: 'vertical'
        
        BoxLayout:
            size_hint_y: None
            height: dp(50)
            canvas.before:
                Color:
                    rgba: 0, 0, 0, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
            
            MDIconButton:
                icon: "arrow-left"
                theme_text_color: "Custom"
                text_color: 1, 1, 1, 1
                on_release: root.back_to_main()
            
            MDLabel:
                text: root.video_title
                theme_text_color: "Custom"
                text_color: 1, 1, 1, 1
                valign: "middle"

        BoxLayout:
            id: player_box
"""

# =========================================================================
# Shared Stalker Client Engine (Retained from Original Core Pipeline)
# =========================================================================
class StalkerClient:
    UA = ("Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 "
          "(KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3")
    XUA = "Model: MAG254; Link: Ethernet"

    def __init__(self, portal, mac):
        self.mac = self.normalize_mac(mac)
        if not self.mac:
            raise ValueError("Invalid MAC address")
        self.raw_portal = portal.strip().rstrip("/")
        base = self.raw_portal.removesuffix("/portal.php")
        if base != self.raw_portal:
            candidates = [self.raw_portal]
        elif base.endswith("/c"):
            candidates = [base + "/portal.php", base[:-2].rstrip("/") + "/portal.php"]
        else:
            candidates = [base + "/c/portal.php", base + "/portal.php", base + "/server/portal.php"]
        self.candidates, self.portal = candidates, candidates
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": self.UA, "X-User-Agent": self.XUA, "Accept": "*/*"})
        self.s.cookies.update({"mac": self.mac, "stb_lang": "en", "timezone": "UTC"})
        self.token = None
        self.account = {}

    def normalize_mac(self, raw):
        digits = "".join(ch for ch in raw.strip().upper() if ch in "0123456789ABCDEF")
        if len(digits) != 12:
            return None
        return ":".join(digits[i:i+2] for i in range(0, 12, 2))

    def _get(self, params):
        errors = []
        urls = [self.portal] if self.token else self.candidates
        for url in urls:
            try:
                r = self.s.get(url, params=params, timeout=10)
                if r.status_code != 200:
                    errors.append(f"{url} -> HTTP {r.status_code}")
                    continue
                if not r.text.strip():
                    errors.append(f"{url} -> empty body")
                    continue
                try:
                    data = r.json()
                except ValueError:
                    errors.append(f"{url} -> non-JSON parsing anomaly")
                    continue
                self.portal = url
                return data
            except Exception as e:
                errors.append(f"{url} -> {type(e).__name__}")
        raise RuntimeError("Portal connection failed:\n " + "\n ".join(errors))

    def handshake(self):
        js = self._get({"type": "stb", "action": "handshake", "JsHttpRequest": "1-xml"}).get("js", {})
        self.token = (js.get("token") or "").split("~")[0].strip()
        if not self.token:
            raise RuntimeError("Handshake failed to acquire access token.")
        self.s.headers["Authorization"] = f"Bearer {self.token}"
        return self.token

    def get_profile(self):
        return self._get({"type": "stb", "action": "get_profile", "JsHttpRequest": "1-xml"}).get("js", {})

    def get_main_info(self):
        js = self._get({"type": "account_info", "action": "get_main_info", "JsHttpRequest": "1-xml"}).get("js", {})
        if isinstance(js, list) and js: js = js[0]
        self.account = js or {}
        return self.account

    def get_channels(self, mode=0):
        # mode: 0 = live, 1 = vod, 2 = series
        action_map = {0: "get_all_channels", 1: "get_ordered_list", 2: "get_ordered_list"}
        type_map = {0: "itv", 1: "vod", 2: "series"}
        
        chans = []
        try:
            js = self._get({"type": type_map[mode], "action": action_map[mode], "JsHttpRequest": "1-xml", "force_all": "1"}).get("js", {})
            chans = js.get("data", []) if isinstance(js, dict) else (js or [])
        except Exception:
            pass

        if not chans and mode == 0:
            # Fallback configuration for paginated portals
            page = 1
            while page < 10:
                try:
                    js = self._get({"type": "itv", "action": "get_ordered_list", "JsHttpRequest": "1-xml", "p": str(page)}).get("js", {})
                    data = js.get("data", []) if isinstance(js, dict) else (js or [])
                    if not data: break
                    chans.extend(data)
                    page += 1
                except Exception:
                    break

        out = []
        seen = set()
        for ch in chans:
            cid = str(ch.get("id", ch.get("ch_id", "")))
            if cid and cid not in seen:
                seen.add(cid)
                out.append({
                    "id": cid,
                    "name": ch.get("name", ch.get("title", "Untitled channel")),
                    "cmd": ch.get("cmd", "")
                })
        return out

    def create_link(self, channel_id, mode=0):
        type_map = {0: "itv", 1: "vod", 2: "series"}
        js = self._get({
            "type": type_map[mode],
            "action": "create_link",
            "JsHttpRequest": "1-xml",
            "cmd": f"ffmpeg http://localhost/ch/{channel_id}"
        }).get("js", {})
        url = js.get("cmd", js.get("url", ""))
        for prefix in ("ffmpeg ", "vlc ", "mpv ", "http "):
            if url.startswith(prefix):
                url = url[len(prefix):]
        
        # Absolute rewriting algorithm
        if "://" in url and ("portal" in url or "127.0.0.1" in url):
            from urllib.parse import urlparse
            p_host = urlparse(self.portal).netloc
            url = url.replace("127.0.0.1", p_host).replace("portal", p_host)
        return url.strip()

# =========================================================================
# Interface Classes & Window Management
# =========================================================================
class ClickableItem(OneLineListItem, ClickableBehavior):
    pass

class LoginScreen(Screen):
    status_text = StringProperty("Status: Idle")
    hit_list = ListProperty([])

    def perform_connect(self):
        portal = self.ids.portal_url.text.strip()
        mac = self.ids.mac_address.text.strip()
        if not portal or not mac:
            self.status_text = "Error: Fields cannot be blank."
            return

        self.status_text = "Connecting to Server..."
        threading.Thread(target=self._connect_worker, args=(portal, mac), daemon=True).start()

    def _connect_worker(self, portal, mac):
        try:
            app = MDApp.get_running_app()
            app.client = StalkerClient(portal, mac)
            app.client.handshake()
            app.client.get_profile()
            acc = app.client.get_main_info()
            expiry = acc.get("phone", acc.get("expire_date", "Unlimited"))
            
            Clock.schedule_once(lambda dt: self._on_connect_success(expiry))
        except Exception as e:
            Clock.schedule_once(lambda dt: setattr(self, 'status_text', f"Error: {str(e)}"))

    def _on_connect_success(self, expiry):
        self.status_text = "Connection Successful!"
        main_screen = self.manager.get_screen('main')
        main_screen.session_info = f"MAC: {MDApp.get_running_app().client.mac}  |  Expires: {expiry}"
        main_screen.load_channels()
        self.manager.current = 'main'

    def perform_scan(self):
        portal = self.ids.portal_url.text.strip()
        prefix = self.ids.scan_prefix.text.strip()
        count_str = self.ids.scan_count.text.strip()
        
        if not portal or not prefix:
            self.status_text = "Error: Provide URL and target standard prefix."
            return
        
        try:
            count = int(count_str)
        except ValueError:
            count = 30

        self.status_text = "Scanner initialization active..."
        threading.Thread(target=self._scan_worker, args=(portal, prefix, count), daemon=True).start()

    def _scan_worker(self, portal, prefix, count):
        generated_macs = []
        for _ in range(count):
            generated_macs.append("{}:%02X:%02X:%02X".format(
                prefix, random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)
            ))

        for idx, mac in enumerate(generated_macs):
            Clock.schedule_once(lambda dt, m=mac: setattr(self, 'status_text', f"Scanning [{idx+1}/{count}]: {m}"))
            try:
                cli = StalkerClient(portal, mac)
                cli.handshake()
                acc = cli.get_main_info()
                expiry = acc.get("phone", acc.get("expire_date", "unknown"))
                Clock.schedule_once(lambda dt, m=mac, e=expiry: self._add_hit(m, e))
            except Exception:
                pass
        
        Clock.schedule_once(lambda dt: setattr(self, 'status_text', "Scan completed."))

    def _add_hit(self, mac, expiry):
        self.hit_list.append({"mac": mac, "expiry": expiry})
        item = ClickableItem(text=f"{mac} (Expires: {expiry})")
        item.bind(on_release=lambda x: self._apply_hit(mac))
        self.ids.hit_container.add_widget(item)

    def _apply_hit(self, mac):
        self.ids.mac_address.text = mac
        self.perform_connect()


class MainScreen(Screen):
    session_info = StringProperty("")
    current_tab = NumericProperty(0)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.all_channels = []

    def switch_tab(self, tab_idx):
        self.current_tab = tab_idx
        self.load_channels()

    def load_channels(self):
        self.ids.channel_container.clear_widgets()
        item = OneLineListItem(text="Fetching server listings...")
        self.ids.channel_container.add_widget(item)
        threading.Thread(target=self._channels_worker, daemon=True).start()

    def _channels_worker(self):
        try:
            app = MDApp.get_running_app()
            self.all_channels = app.client.get_channels(mode=self.current_tab)
            Clock.schedule_once(lambda dt: self.populate_list(self.all_channels))
        except Exception as e:
            Clock.schedule_once(lambda dt: self._show_error(str(e)))

    def _show_error(self, err_msg):
        self.ids.channel_container.clear_widgets()
        self.ids.channel_container.add_widget(OneLineListItem(text=f"Failure: {err_msg}"))

    def populate_list(self, channel_list):
        self.ids.channel_container.clear_widgets()
        if not channel_list:
            self.ids.channel_container.add_widget(OneLineListItem(text="No media instances found."))
            return

        for ch in channel_list:
            item = ClickableItem(text=ch['name'])
            item.bind(on_release=lambda x, c=ch: self.resolve_and_play(c))
            self.ids.channel_container.add_widget(item)

    def filter_channels(self, query):
        filtered = [c for c in self.all_channels if query.lower() in c['name'].lower()]
        self.populate_list(filtered)

    def resolve_and_play(self, channel_obj):
        threading.Thread(target=self._play_worker, args=(channel_obj,), daemon=True).start()

    def _play_worker(self, channel_obj):
        try:
            app = MDApp.get_running_app()
            stream_url = app.client.create_link(channel_obj['id'], mode=self.current_tab)
            if not stream_url:
                raise RuntimeError("Empty stream path resolved.")
            Clock.schedule_once(lambda dt: self._launch_player(stream_url, channel_obj['name']))
        except Exception:
            pass

    def _launch_player(self, url, title):
        video_screen = self.manager.get_screen('video')
        video_screen.play_video(url, title)
        self.manager.current = 'video'

    def logout(self):
        self.manager.current = 'login'


class VideoScreen(Screen):
    video_title = StringProperty("Streaming Network Link")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.video_widget = None

    def play_video(self, url, title):
        self.video_title = title
        self.ids.player_box.clear_widgets()
        
        # Local imports ensure cross-platform compatibility without crashing early
        from kivy.uix.videoplayer import VideoPlayer
        
        # Native Video player construction config
        self.video_widget = VideoPlayer(
            source=url,
            state='play',
            options={'allow_stretch': True, 'eos': 'stop'}
        )
        self.ids.player_box.add_widget(self.video_widget)

    def back_to_main(self):
        if self.video_widget:
            self.video_widget.state = 'stop'
            self.ids.player_box.clear_widgets()
            self.video_widget = None
        self.manager.current = 'main'


class StalkerPlayerApp(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Green"
        self.client = None
        return Builder.load_string(KV)


if __name__ == '__main__':
    StalkerPlayerApp().run()
