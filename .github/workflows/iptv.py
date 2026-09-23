#!/usr/bin/env python3
"""
Professional Stalker Portal IPTV Player (console, Termux/Pydroid-safe) — v4.3
Fix: http:// URLs were opening in BROWSER instead of VLC/mpv.
  - Explicit player activity (VideoPlayerActivity / MPVActivity) = direct playback
  - MIME type video/* forces Android to route to a video player, never the browser
Endpoints: handshake, get_profile, get_main_info, get_genres, get_all_channels,
get_ordered_list (paginated fallback), create_link. Auto MAC generator included.
"""

import os
import sys
import json
import time
import random
import shutil
import subprocess
from datetime import datetime

import requests

# ---------------------------------------------------------------- colours
class C:
    R = "\033[91m"; G = "\033[92m"; Y = "\033[93m"; B = "\033[94m"
    M = "\033[95m"; CY = "\033[96m"; W = "\033[97m"; BOLD = "\033[1m"
    DIM = "\033[2m"; END = "\033[0m"

def cprint(color, text): print(f"{color}{text}{C.END}")

def banner():
    os.system("cls" if os.name == "nt" else "clear")
    print(f"""{C.CY}{C.BOLD}{'='*58}
      STALKER PORTAL IPTV PLAYER  v4.3
{'='*58}{C.END}""")

def one_line(color, msg):
    sys.stdout.write(f"\r{color}{str(msg)[:110]}{C.END}")
    sys.stdout.flush()

def normalize_mac(raw):
    digits = "".join(ch for ch in raw.strip().upper() if ch in "0123456789ABCDEF")
    if len(digits) != 12:
        return None
    return ":".join(digits[i:i+2] for i in range(0, 12, 2))

def generate_mac():
    return f"00:1A:79:{random.randint(0,255):02X}:{random.randint(0,255):02X}:{random.randint(0,255):02X}"

ZERO_DATES = {"", "0000-00-00", "0000-00-00 00:00:00", "1970-01-01 00:00:00"}

def expiry_ok(exp):
    exp = str(exp or "").strip()
    if exp in ZERO_DATES: return False
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(exp[:19], fmt) > datetime.now()
        except ValueError:
            continue
    return False

def is_android():
    return sys.platform == "android" or os.path.exists("/system/bin/am")

# ---------------------------------------------------------------- client
class StalkerClient:
    UA = ("Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 "
          "(KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3")
    XUA = "Model: MAG250; Link: WiFi"

    def __init__(self, portal, mac):
        self.mac = normalize_mac(mac)
        if not self.mac:
            raise ValueError("Invalid MAC address")
        self.raw_portal = portal.strip().rstrip("/")
        base = self.raw_portal.removesuffix("/portal.php")
        if base != self.raw_portal:
            candidates = [self.raw_portal]
        elif base.endswith("/c"):
            candidates = [base + "/portal.php",
                          base[:-2].rstrip("/") + "/portal.php"]
        else:
            candidates = [base + "/c/portal.php",
                          base + "/portal.php",
                          base + "/server/portal.php"]
        self.candidates, self.portal = candidates, candidates[0]
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": self.UA, "X-User-Agent": self.XUA,
                               "Accept": "*/*",
                               "Referer": "http://localhost/stalker_portal/c/"})
        # mac cookie MUST be present on handshake for many portals
        self.s.cookies.update({"mac": self.mac, "stb_lang": "en",
                               "timezone": "Europe/London"})
        self.token = None
        self.account = {}

    def _get(self, params):
        errors = []
        urls = [self.portal] if self.token else self.candidates
        for url in urls:
            try:
                r = self.s.get(url, params=params, timeout=12)
                if r.status_code != 200:
                    errors.append(f"{url} -> HTTP {r.status_code}")
                    continue
                if not r.text.strip():
                    errors.append(f"{url} -> empty body")
                    continue
                try:
                    data = r.json()
                except ValueError:
                    errors.append(f"{url} -> non-JSON: {r.text.strip()[:80]!r}")
                    continue
                self.portal = url
                return data
            except requests.RequestException as e:
                errors.append(f"{url} -> {type(e).__name__}: {e}")
        raise RuntimeError("Portal request failed:\n  " + "\n  ".join(errors))

    def handshake(self):
        js = self._get({"type": "stb", "action": "handshake",
                        "JsHttpRequest": "1-xml"}).get("js", {})
        self.token = (js.get("token") or "").split("~")[0]
        if not self.token:
            raise RuntimeError("handshake ok but no token in response")
        self.s.headers["Authorization"] = f"Bearer {self.token}"
        return self.token

    def get_profile(self):
        return self._get({"type": "stb", "action": "get_profile",
                          "JsHttpRequest": "1-xml"}).get("js", {})

    def get_main_info(self):
        js = self._get({"type": "account_info", "action": "get_main_info",
                        "JsHttpRequest": "1-xml"}).get("js", {})
        if isinstance(js, list) and js: js = js[0]
        self.account = js or {}
        return self.account

    def get_genres(self):
        try:
            js = self._get({"type": "itv", "action": "get_genres",
                            "JsHttpRequest": "1-xml"}).get("js", [])
            return {str(g["id"]): g["title"] for g in js if isinstance(g, dict)}
        except Exception:
            return {}

    def get_all_channels(self, progress=None):
        chans = []
        try:
            js = self._get({"type": "itv", "action": "get_all_channels",
                            "JsHttpRequest": "1-xml"}).get("js", {})
            chans = js.get("data", []) if isinstance(js, dict) else (js or [])
        except Exception:
            chans = []
        if not chans:
            page = 1
            while True:
                try:
                    js = self._get({"type": "itv", "action": "get_ordered_list",
                                    "JsHttpRequest": "1-xml",
                                    "type_itv": "1", "p": str(page)}).get("js", {})
                except Exception:
                    break
                data = js.get("data", []) if isinstance(js, dict) else (js or [])
                if not data: break
                chans.extend(data)
                if progress: progress(page, len(chans))
                if not isinstance(js, dict) or page >= int(js.get("max_page", 1) or 1):
                    break
                page += 1
        seen, out = set(), []
        for ch in chans:
            cid = str(ch.get("id", ""))
            if cid and cid not in seen:
                seen.add(cid)
                out.append({"id": cid, "name": ch.get("name", "?"),
                            "num": ch.get("number", ""),
                            "tv_genre_id": str(ch.get("tv_genre_id", ""))})
        return out

    def create_link(self, channel_id):
        js = self._get({"type": "itv", "action": "create_link",
                        "JsHttpRequest": "1-xml",
                        "cmd": f"ffmpeg http://localhost/ch/{channel_id}"}).get("js", {})
        url = js.get("cmd", "")
        for pref in ("ffmpeg ", "vlc ", "http "):
            if url.startswith(pref):
                url = url[len(pref):]
        return url

# ---------------------------------------------------------------- players
VLC_PATHS = [r"C:\Program Files\VideoLAN\VLC\vlc.exe",
             r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"]
MPV_PATHS = [r"C:\Program Files\mpv\mpv.exe",
             r"C:\Program Files (x86)\mpv\mpv.exe"]

# explicit playback activities — these exist in VLC / mpv Android builds
ANDROID_ACTIVITIES = {
    "org.videolan.vlc": "org.videolan.vlc/org.videolan.vlc.gui.video.VideoPlayerActivity",
    "is.xyz.mpv":       "is.xyz.mpv/.MPVActivity",
}

def android_play(url, package):
    """Route the stream URL to the player APP, never the browser.
    1) explicit player activity (-n)  2) -p package + video/* MIME  3) VIEW video/*
    The video/* MIME type excludes the browser (browsers only handle text/html)."""
    activity = ANDROID_ACTIVITIES.get(package)
    cmds = []
    if activity:                                        # 1) direct player activity
        cmds.append(["am", "start", "-a", "android.intent.action.VIEW",
                     "-d", url, "-n", activity])
    cmds.append(["am", "start", "-a", "android.intent.action.VIEW",
                 "-d", url, "-t", "video/*", "-p", package])   # 2) constrained by package
    cmds.append(["am", "start", "-a", "android.intent.action.VIEW",
                 "-d", url, "-t", "video/*"])                  # 3) any video player
    for cmd in cmds:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True)
            out = (r.stdout or "") + (r.stderr or "")
            if r.returncode == 0 and "Error" not in out and "does not exist" not in out:
                return True
        except Exception:
            continue
    return False

def play_vlc(url):
    if is_android():
        if android_play(url, "org.videolan.vlc"):
            return "VLC app (Android)"
        cprint(C.Y, f"  [!] VLC app launch failed — stream URL:\n  {url}")
        return "URL printed"
    v = shutil.which("vlc")
    if v:
        subprocess.Popen([v, "--play-and-exit", url]); return f"VLC ({v})"
    for p in VLC_PATHS:
        if os.path.exists(p):
            subprocess.Popen([p, "--play-and-exit", url]); return f"VLC ({p})"
    if sys.platform == "darwin" and os.path.exists("/Applications/VLC.app/Contents/MacOS/VLC"):
        subprocess.Popen(["/Applications/VLC.app/Contents/MacOS/VLC", url])
        return "VLC (macOS)"
    cprint(C.Y, f"  [!] VLC not found — stream URL:\n  {url}")
    return "URL printed"

def play_mpv(url):
    if is_android():
        if android_play(url, "is.xyz.mpv"):
            return "mpv app (Android)"
        cprint(C.Y, f"  [!] mpv app launch failed — stream URL:\n  {url}")
        return "URL printed"
    m = shutil.which("mpv")
    if m:
        subprocess.Popen([m, "--really-quiet", url]); return f"mpv ({m})"
    for p in MPV_PATHS:
        if os.path.exists(p):
            subprocess.Popen([p, "--really-quiet", url]); return f"mpv ({p})"
    cprint(C.Y, f"  [!] mpv not found — stream URL:\n  {url}")
    return "URL printed"

def choose_and_play(url):
    cprint(C.CY, "\n  Play with:")
    print(f"    {C.W}1{C.END}. VLC app")
    print(f"    {C.W}2{C.END}. mpv app")
    p = input(f"  {C.Y}Player [1/2]: {C.END}").strip()
    if p == "2":
        return play_mpv(url)
    return play_vlc(url)

# ---------------------------------------------------------------- app
def connect_client(portal, mac):
    cli = StalkerClient(portal, mac)
    token = cli.handshake()
    cli.get_profile()
    acc = cli.get_main_info()
    exp = acc.get("phone", "")
    ok = expiry_ok(exp)
    cprint(C.B, f"\n  Portal : {cli.portal}")
    cprint(C.B, f"  MAC    : {cli.mac}")
    cprint(C.G, f"  Token  : {token}")
    cprint(C.G if ok else C.Y, f"  Expiry : {exp or 'n/a'}  {'(VALID)' if ok else '(expired/none)'}")
    return cli

def auto_gen_mac(portal):
    import concurrent.futures
    from threading import Lock

    cprint(C.M, "\n[*] Auto MAC generator running — Ctrl+C to abort")
    start = time.time()
    
    # Shared variables for cross-thread state tracking
    found_result = {}
    lock = Lock()
    tries = 0

    def worker_check(_):
        nonlocal tries
        if found_result:
            return None

        mac = generate_mac()
        
        with lock:
            tries += 1
            # Throttled status rendering reduces UI lagging across threads
            if tries % 5 == 0 or tries < 5:
                rate = tries / max(time.time() - start, 1)
                one_line(C.Y, f"  [{tries:>7}] {mac}  {rate:5.1f} mac/s")

        try:
            cli = StalkerClient(portal, mac)
            token = cli.handshake()
            acc = cli.get_main_info()
            exp = acc.get("phone", "")
            if expiry_ok(exp):
                with lock:
                    if not found_result:
                        found_result["mac"] = mac
                        found_result["expiry"] = exp
                        found_result["token"] = token
                return True
        except Exception:
            pass
        return None

    # max_workers=50 tests 50 MAC addresses concurrently instead of one by one
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            # Feeds an infinite index generator to keep working pipelines fueled
            for _ in executor.map(worker_check, range(2000000)):
                if found_result:
                    break

        if found_result:
            print()
            cprint(C.G + C.BOLD, "\n  ✅ VALID MAC FOUND!")
            cprint(C.G, f"     MAC    : {found_result['mac']}")
            cprint(C.G, f"     Expiry : {found_result['expiry']}")
            cprint(C.G, f"     Token  : {found_result['token']}")
            with open("found_mac.json", "w") as fh:
                json.dump({"mac": found_result['mac'], "expiry": found_result['expiry'], "token": found_result['token'],
                           "portal": portal,
                           "ts": datetime.now().isoformat()}, fh, indent=2)
            return found_result['mac']

    except KeyboardInterrupt:
        print()
        cprint(C.R, "[!] Generator stopped")
    return None


def main():
    banner()
    cprint(C.CY + C.BOLD, "  STALKER PORTAL PLAYER — handshake/profile/info/genres/channels")
    print()

    portal = input(f"  {C.Y}Portal URL {C.W}(e.g. http://domain.com:8080/c){C.END}: ").strip()
    if not portal: sys.exit("Portal URL required.")
    if not portal.startswith(("http://", "https://")): portal = "http://" + portal

    cprint(C.M, "\n  [1] Enter MAC manually")
    cprint(C.M, "  [2] Auto-generate MACs until valid one is found")
    opt = input(f"  {C.Y}Option {C.W}[1/2]{C.END}: ").strip()
    if opt == "2":
        mac = auto_gen_mac(portal)
        if not mac: return
    else:
        mac = input(f"  {C.Y}MAC address {C.W}(e.g. 00:1A:79:D1:FC:C2){C.END}: ").strip()

    try:
        cli = connect_client(portal, mac)
    except Exception as e:
        cprint(C.R, f"\n[!] Connect failed: {e}")
        return

    cprint(C.B, "\n[*] Loading genres + channels...")
    genres = cli.get_genres()
    def prog(p, n): one_line(C.DIM, f"  loading... page {p}  ({n} channels)")
    channels = cli.get_all_channels(prog)
    print()
    cprint(C.G, f"  Loaded {len(channels)} channels in {len(genres)} genres")

    by_genre = {}
    for ch in channels:
        by_genre.setdefault(ch["tv_genre_id"], []).append(ch)

    while True:
        print(f"\n{C.CY}{'-'*58}{C.END}")
        cprint(C.CY + C.BOLD, "  MENU")
        print(f"  {C.W}1{C.END}. List all channels")
        print(f"  {C.W}2{C.END}. Browse by genre")
        print(f"  {C.W}3{C.END}. Search channel by name")
        print(f"  {C.W}4{C.END}. Account info")
        print(f"  {C.W}5{C.END}. Play channel by number")
        print(f"  {C.W}0{C.END}. Exit")
        choice = input(f"  {C.Y}> {C.END}").strip()

        selected = None
        if choice == "1":
            for ch in channels:
                g = genres.get(ch["tv_genre_id"], "")
                print(f"  {C.DIM}{ch['num']:>4}{C.END}  {C.W}{ch['name']}{C.END}  {C.DIM}[{g}]{C.END}")
            sel = input(f"  {C.Y}Channel number to play (blank=menu): {C.END}").strip()
            if sel:
                selected = next((c for c in channels if str(c["num"]) == sel), None)
        elif choice == "2":
            gid = list(sorted(genres.keys(), key=lambda x: genres.get(x, "")))
            for i, g in enumerate(gid, 1):
                print(f"  {C.B}{i:>3}{C.END}. {genres[g]} {C.DIM}({len(by_genre.get(g, []))}){C.END}")
            gi = input(f"  {C.Y}Genre number: {C.END}").strip()
            if gi.isdigit() and 1 <= int(gi) <= len(gid):
                for ch in by_genre.get(gid[int(gi)-1], []):
                    print(f"  {C.DIM}{ch['num']:>4}{C.END}  {C.W}{ch['name']}{C.END}")
                sel = input(f"  {C.Y}Channel number to play (blank=menu): {C.END}").strip()
                if sel:
                    selected = next((c for c in by_genre[gid[int(gi)-1]] if str(c["num"]) == sel), None)
        elif choice == "3":
            q = input(f"  {C.Y}Search: {C.END}").strip().lower()
            for ch in channels:
                if q in ch["name"].lower():
                    print(f"  {C.DIM}{ch['num']:>4}{C.END}  {C.W}{ch['name']}{C.END}")
            sel = input(f"  {C.Y}Channel number to play (blank=menu): {C.END}").strip()
            if sel:
                selected = next((c for c in channels if str(c["num"]) == sel), None)
        elif choice == "4":
            acc = cli.get_main_info()
            for k, v in acc.items():
                cprint(C.B, f"  {k:<28}: {C.W}{v}{C.END}")
        elif choice == "5":
            sel = input(f"  {C.Y}Channel number: {C.END}").strip()
            selected = next((c for c in channels if str(c["num"]) == sel), None)
            if not selected: cprint(C.R, "  [!] Channel not found")
        elif choice == "0":
            cprint(C.CY, "\n  Goodbye 👋"); return

        if selected:
            cprint(C.B, f"\n[*] Resolving stream for {C.W}{selected['name']}{C.END}...")
            try:
                url = cli.create_link(selected["id"])
                if url:
                    cprint(C.G, f"  Stream: {url}")
                    player = choose_and_play(url)
                    cprint(C.G, f"  ▶ Playing in {player}")
                    cprint(C.Y, "  (link expires in minutes — resolve fresh each play)")
                else:
                    cprint(C.R, "  [!] No stream URL returned")
            except Exception as e:
                cprint(C.R, f"  [!] create_link failed: {e}")
            input(f"  {C.DIM}Press Enter for menu...{C.END}")

if __name__ == "__main__":
    main()

