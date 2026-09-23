#!/usr/bin/env python3
"""Stalker Portal IPTV Player — Kivy APK edition. Engine: iptv.py"""
import functools
import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

from iptv import StalkerClient, generate_mac, expiry_ok


def play_url(url, package="org.videolan.vlc"):
    """Open stream in VLC/mpv app — video/* MIME excludes the browser."""
    from kivy.utils import platform
    if platform == "android":
        from jnius import autoclass
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        Activity = autoclass("org.kivy.android.PythonActivity")
        intent = Intent("android.intent.action.VIEW")
        intent.setDataAndType(Uri.parse(url), "video/*")
        intent.addFlags(0x10000000)      # FLAG_ACTIVITY_NEW_TASK
        intent.setPackage(package)       # VLC (org.videolan.vlc) or mpv (is.xyz.mpv)
        Activity.mActivity.startActivity(intent)
    else:
        import webbrowser
        webbrowser.open(url)


class IPTVRoot(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", padding=dp(8), spacing=dp(6), **kw)
        self.client, self.channels, self.genres = None, [], {}

        # ---- connect screen ----
        self.connect_panel = BoxLayout(orientation="vertical", spacing=dp(6))
        self.portal_in = TextInput(hint_text="Portal URL e.g. http://host:8080/c",
                                   multiline=False, size_hint_y=None, height=dp(44))
        self.mac_in = TextInput(hint_text="MAC e.g. 00:1A:79:D1:FC:C2",
                                multiline=False, size_hint_y=None, height=dp(44))
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        btn_mac = Button(text="Random MAC")
        btn_mac.bind(on_press=lambda *_: setattr(self.mac_in, "text", generate_mac()))
        btn_go = Button(text="Connect")
        btn_go.bind(on_press=self.do_connect)
        row.add_widget(self.mac_in); row.add_widget(btn_mac)
        self.status = Label(text="Enter portal + MAC", halign="left", valign="middle",
                            size_hint_y=None, height=dp(70), color=(0.6, 0.9, 0.6, 1))
        self.status.bind(size=lambda s, *_: s.setter("text_size")(s, s.size))
        for w in (self.portal_in, row, btn_go, self.status):
            self.connect_panel.add_widget(w)
        self.add_widget(self.connect_panel)

        # ---- channel browser (added after connect) ----
        self.main_panel = BoxLayout(orientation="vertical", spacing=dp(6))
        self.info = Label(text="", halign="left", size_hint_y=None, height=dp(50),
                          color=(0.5, 0.8, 1, 1), font_size=dp(12))
        self.info.bind(size=lambda s, *_: s.setter("text_size")(s, s.size))
        self.genre_sp = Spinner(text="All genres", size_hint_y=None, height=dp(44))
        self.genre_sp.bind(text=self.refresh_list)
        self.search_in = TextInput(hint_text="Search…", multiline=False,
                                   size_hint_y=None, height=dp(44))
        self.search_in.bind(text=self.refresh_list)
        self.list_holder = GridLayout(cols=1, size_hint_y=None, spacing=dp(2))
        self.list_holder.bind(minimum_height=self.list_holder.setter("height"))
        sv = ScrollView(); sv.add_widget(self.list_holder)
        for w in (self.info, self.genre_sp, self.search_in, sv):
            self.main_panel.add_widget(w)

    # ---------- background / UI thread helpers ----------
    def run_bg(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    def ui(self, fn, *a):
        Clock.schedule_once(lambda *_: fn(*a), 0)

    def set_status(self, msg):
        self.status.text = str(msg)

    # ---------- connect ----------
    def do_connect(self, *_):
        portal = self.portal_in.text.strip()
        if not portal:
            return
        if not portal.startswith(("http://", "https://")):
            portal = "http://" + portal
        mac = self.mac_in.text.strip()
        self.set_status("Connecting…")

        def work():
            try:
                cli = StalkerClient(portal, mac)
                cli.handshake(); cli.get_profile()
                acc = cli.get_main_info()
                self.client = cli
                self.ui(self.on_connected, acc)
            except Exception as e:
                self.ui(self.set_status, f"Connect failed: {e}")
        self.run_bg(work)

    def on_connected(self, acc):
        exp = str(acc.get("phone", "") or "")
        mark = "VALID" if expiry_ok(exp) else "expired/none"
        self.info.text = f"{self.client.portal}\nMAC {self.client.mac} · expiry: {exp or 'n/a'} ({mark})"
        self.remove_widget(self.connect_panel)
        self.add_widget(self.main_panel)
        self.set_status("Loading channels…")
        self.run_bg(self.load_channels)

    def load_channels(self):
        self.genres = self.client.get_genres()
        self.channels = self.client.get_all_channels()
        self.ui(self.populate)

    def populate(self):
        opts = ["All genres"] + sorted({self.genres.get(c["tv_genre_id"], "Other")
                                        for c in self.channels})
        self.genre_sp.values = opts
        self.set_status(f"{len(self.channels)} channels loaded")
        self.refresh_list()

    def refresh_list(self, *_):
        q = self.search_in.text.strip().lower()
        g = self.genre_sp.text
        self.list_holder.clear_widgets()
        for ch in self.channels:
            if q and q not in ch["name"].lower():
                continue
            if g != "All genres" and self.genres.get(ch["tv_genre_id"], "Other") != g:
                continue
            num = str(ch.get("num") or "")
            b = Button(text=f"{num:>4}  {ch['name']}", size_hint_y=None, height=dp(42),
                       halign="left", font_size=dp(14))
            b.bind(on_press=functools.partial(self.play_channel, ch))
            self.list_holder.add_widget(b)

    def play_channel(self, ch, *_):
        self.set_status(f"Resolving stream: {ch['name']}…")

        def work():
            try:
                url = self.client.create_link(ch["id"])
                if url:
                    self.ui(self.set_status, f"▶ Playing: {ch['name']}")
                    play_url(url, "org.videolan.vlc")   # or "is.xyz.mpv"
                else:
                    self.ui(self.set_status, "No stream URL returned")
            except Exception as e:
                self.ui(self.set_status, f"create_link failed: {e}")
        self.run_bg(work)


class IPTVApp(App):
    title = "IPTV Player"

    def build(self):
        Window.softinput_mode = "below_target"
        return IPTVRoot()


if __name__ == "__main__":
    IPTVApp().run()
