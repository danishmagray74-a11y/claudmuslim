"""
Claude Muslim - a free Windows app that changes your desktop wallpaper
automatically with Islamic architecture / pattern images and a quote from a
well-known Muslim personality.

* Images come from Wikimedia Commons (free licences only; credits are saved).
* Works in the background through Windows Task Scheduler: no running process,
  no tray icon, nothing to leave open.
* Free for everyone (MIT licence). No ads, no accounts, no tracking.

Usage:
    claude_muslim.py            open the settings window
    claude_muslim.py --apply    change the wallpaper once (used by the scheduler)
"""

import argparse
import ctypes
import hashlib
import html
import json
import os
import random
import re
import subprocess
import sys
import threading
import urllib.parse
import urllib.request

try:
    from PIL import Image, ImageDraw, ImageFont

    HAVE_PIL = True
except Exception:  # Pillow missing: wallpapers still work, just without quotes
    HAVE_PIL = False

APP_NAME = "Claude Muslim"
FOLDER = "ClaudeMuslim"
TASK_INTERVAL = "ClaudeMuslim-Interval"
TASK_LOGON = "ClaudeMuslim-Logon"
UA = "ClaudeMuslim/1.0 (free wallpaper app; MIT licence)"
API = "https://commons.wikimedia.org/w/api.php"

# ---------------------------------------------------------------------------
# Quotes. These are widely circulated; several are traditionally "attributed"
# rather than precisely sourced. Please verify before publishing them anywhere.
# Add your own in  %APPDATA%\ClaudeMuslim\my_quotes.json  as
# [{"text": "...", "by": "Name"}, ...]
# ---------------------------------------------------------------------------
QUOTES = [
    {"text": "Hold yourselves accountable before you are held accountable.",
     "by": "Umar ibn al-Khattab"},
    {"text": "Knowledge is better than wealth: you must guard wealth, "
             "but knowledge guards you.",
     "by": "Ali ibn Abi Talib (attributed)"},
    {"text": "People are enemies of what they do not know.",
     "by": "Ali ibn Abi Talib (attributed)"},
    {"text": "Knowledge without action is vanity, and action without "
             "knowledge is insanity.",
     "by": "Al-Ghazali (attributed)"},
    {"text": "Injustice brings about the ruin of civilization.",
     "by": "Ibn Khaldun (Muqaddimah, paraphrase)"},
    {"text": "The ultimate aim of the ego is not to see something, "
             "but to be something.",
     "by": "Muhammad Iqbal"},
    {"text": "Education is the passport to the future, for tomorrow belongs "
             "to those who prepare for it today.",
     "by": "Malcolm X"},
    {"text": "Service to others is the rent you pay for your room here on earth.",
     "by": "Muhammad Ali"},
    {"text": "We win or we die.",
     "by": "Omar Mukhtar"},
]

SEARCHES = [
    "mosque interior",
    "mosque dome",
    "Islamic geometric pattern",
    "Islamic calligraphy",
    "Alhambra",
    "Sheikh Zayed Grand Mosque",
    "Blue Mosque Istanbul",
    "Masjid minaret sunset",
    "Islamic architecture",
    "Mosque of Cordoba",
    "Sultan Ahmed Mosque",
    "Nasir al-Mulk Mosque",
]

DEFAULT_CONFIG = {"interval_min": 60, "overlay": True, "enabled": False}


# ---------------------------------------------------------------------------
# Paths, config, logging
# ---------------------------------------------------------------------------
def data_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    p = os.path.join(base, FOLDER)
    os.makedirs(os.path.join(p, "images"), exist_ok=True)
    os.makedirs(os.path.join(p, "wallpapers"), exist_ok=True)
    return p


def path(*parts):
    return os.path.join(data_dir(), *parts)


def log(msg):
    try:
        with open(path("log.txt"), "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except OSError:
        pass


def load_json(name, default):
    try:
        with open(path(name), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(name, obj):
    try:
        with open(path(name), "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
    except OSError as e:
        log(f"save {name} failed: {e}")


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(load_json("config.json", {}))
    return cfg


def all_quotes():
    extra = load_json("my_quotes.json", [])
    good = [q for q in extra if isinstance(q, dict) and q.get("text")]
    return QUOTES + [{"text": q["text"], "by": q.get("by", "")} for q in good]


# ---------------------------------------------------------------------------
# Getting images from Wikimedia Commons (free licences only)
# ---------------------------------------------------------------------------
ALLOWED_LICENSE = re.compile(
    r"^(CC0.*|Public domain.*|PD.*|CC[ -]BY([ -]SA)?[ -][0-9.]+.*)$", re.I
)
BLOCKED_LICENSE = re.compile(r"(NC|ND)", re.I)


def http_get(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def search_commons(query, offset):
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": "6",
        "gsrlimit": "40", "gsroffset": str(offset),
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": "2560",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    data = json.loads(http_get(url).decode("utf-8"))
    out = []
    for page in (data.get("query", {}).get("pages", {}) or {}).values():
        info = (page.get("imageinfo") or [None])[0]
        if not info or info.get("mime") != "image/jpeg":
            continue
        w, h = info.get("width", 0), info.get("height", 0)
        if w < 1920 or h == 0 or not (1.3 <= w / h <= 2.1):
            continue
        meta = info.get("extmetadata", {})
        lic = strip_tags(meta.get("LicenseShortName", {}).get("value", ""))
        if not lic or not ALLOWED_LICENSE.match(lic) or BLOCKED_LICENSE.search(lic):
            continue
        out.append({
            "url": info.get("thumburl") or info.get("url"),
            "title": page.get("title", "").replace("File:", ""),
            "artist": strip_tags(meta.get("Artist", {}).get("value", "")) or "Unknown",
            "license": lic,
            "page": info.get("descriptionurl", ""),
        })
    return out


def download_new_image():
    """Download one fresh free-licence image. Returns (file, credit) or None."""
    credits = load_json("credits.json", {})
    for _ in range(4):
        query = random.choice(SEARCHES)
        for offset in (random.randint(0, 80), 0):
            try:
                cands = search_commons(query, offset)
            except Exception as e:
                log(f"search failed: {e}")
                return None
            random.shuffle(cands)
            for c in cands:
                name = hashlib.sha1(c["url"].encode()).hexdigest()[:16] + ".jpg"
                if name in credits:
                    continue
                try:
                    blob = http_get(c["url"], timeout=90)
                except Exception as e:
                    log(f"download failed: {e}")
                    continue
                with open(path("images", name), "wb") as f:
                    f.write(blob)
                credits[name] = c
                save_json("credits.json", credits)
                prune_images(credits)
                return path("images", name), c
    return None


def prune_images(credits, keep=40):
    files = [os.path.join(path("images"), n) for n in os.listdir(path("images"))]
    files.sort(key=os.path.getmtime, reverse=True)
    for old in files[keep:]:
        try:
            os.remove(old)
            credits.pop(os.path.basename(old), None)
        except OSError:
            pass
    save_json("credits.json", credits)


def pick_cached_image():
    credits = load_json("credits.json", {})
    files = [n for n in os.listdir(path("images")) if n.lower().endswith(".jpg")]
    if not files:
        return None
    name = random.choice(files)
    return path("images", name), credits.get(name, {})


# ---------------------------------------------------------------------------
# Building and setting the wallpaper
# ---------------------------------------------------------------------------
def screen_size():
    try:
        u = ctypes.windll.user32
        return u.GetSystemMetrics(0), u.GetSystemMetrics(1)
    except Exception:
        return 1920, 1080


def find_font(size):
    for name in ("segoeuib.ttf", "segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def compose(image_file, quote, out_file):
    """Fill the screen with the image and draw the quote on it."""
    sw, sh = screen_size()
    img = Image.open(image_file).convert("RGB")
    scale = max(sw / img.width, sh / img.height)
    img = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1),
                     Image.LANCZOS)
    left, top = (img.width - sw) // 2, (img.height - sh) // 2
    img = img.crop((left, top, left + sw, top + sh)).convert("RGBA")

    if quote:
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        body_font = find_font(max(22, sh // 32))
        by_font = find_font(max(16, sh // 48))
        max_w = int(sw * 0.45)
        lines = wrap(d, "“" + quote["text"] + "”", body_font, max_w)
        by = "— " + quote["by"] if quote.get("by") else ""
        lh = body_font.size + 8
        box_h = lh * len(lines) + (by_font.size + 24 if by else 0) + 40
        box_w = max([d.textlength(l, font=body_font) for l in lines]
                    + [d.textlength(by, font=by_font)]) + 60
        x = int(sw * 0.06)
        y = int(sh * 0.60)
        d.rounded_rectangle((x, y, x + box_w, y + box_h), radius=18,
                            fill=(0, 0, 0, 140))
        ty = y + 22
        for line in lines:
            d.text((x + 30, ty), line, font=body_font, fill=(255, 255, 255, 255))
            ty += lh
        if by:
            d.text((x + 30, ty + 8), by, font=by_font, fill=(230, 210, 150, 255))
        img = Image.alpha_composite(img, overlay)

    img.convert("RGB").save(out_file, "JPEG", quality=92)


def set_wallpaper(file):
    # SPI_SETDESKWALLPAPER = 20, update ini + broadcast change = 3
    ok = ctypes.windll.user32.SystemParametersInfoW(20, 0, file, 3)
    if not ok:
        raise OSError("Windows refused to set the wallpaper")


def apply_once(overlay=True):
    """Change the wallpaper. Returns a short status message."""
    got = None
    try:
        got = download_new_image()
    except Exception as e:
        log(f"download error: {e}")
    if not got:
        got = pick_cached_image()
    if not got:
        return "No image yet. Check your internet connection and try again."

    image_file, credit = got
    quote = random.choice(all_quotes()) if overlay and HAVE_PIL else None
    out = path("wallpapers", f"wall_{random.randint(0, 10**9)}.jpg")
    try:
        if HAVE_PIL:
            compose(image_file, quote, out)
        else:
            out = image_file
        set_wallpaper(out)
    except Exception as e:
        log(f"apply failed: {e}")
        return f"Could not set wallpaper: {e}"

    # keep only the 3 newest composed wallpapers
    wall_dir = path("wallpapers")
    olds = sorted((os.path.join(wall_dir, n) for n in os.listdir(wall_dir)),
                  key=os.path.getmtime, reverse=True)[3:]
    for o in olds:
        try:
            os.remove(o)
        except OSError:
            pass

    who = credit.get("artist", "unknown")
    lic = credit.get("license", "")
    return f"Wallpaper changed. Photo: {credit.get('title', '')} by {who} ({lic})"


# ---------------------------------------------------------------------------
# Automatic changing through Windows Task Scheduler
# ---------------------------------------------------------------------------
def run_command():
    """The command Task Scheduler should run."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --apply'
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(pyw):
        exe = pyw
    return f'"{exe}" "{os.path.abspath(__file__)}" --apply'


def _schtasks(*args):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(["schtasks", *args], capture_output=True, text=True,
                          creationflags=flags)


def enable_auto(interval_min):
    cmd = run_command()
    _schtasks("/delete", "/tn", TASK_INTERVAL, "/f")
    _schtasks("/delete", "/tn", TASK_LOGON, "/f")
    if interval_min >= 1440:
        sched = ["/sc", "DAILY"]
    elif interval_min >= 60 and interval_min % 60 == 0:
        sched = ["/sc", "HOURLY", "/mo", str(interval_min // 60)]
    else:
        sched = ["/sc", "MINUTE", "/mo", str(interval_min)]
    r1 = _schtasks("/create", "/tn", TASK_INTERVAL, "/tr", cmd, "/f", *sched)
    r2 = _schtasks("/create", "/tn", TASK_LOGON, "/tr", cmd, "/f",
                   "/sc", "ONLOGON")
    if r1.returncode != 0:
        return False, (r1.stderr or r1.stdout or "schtasks failed").strip()
    return True, "Automatic wallpaper changing is ON."


def disable_auto():
    _schtasks("/delete", "/tn", TASK_INTERVAL, "/f")
    _schtasks("/delete", "/tn", TASK_LOGON, "/f")
    return "Automatic wallpaper changing is OFF."


# ---------------------------------------------------------------------------
# Settings window
# ---------------------------------------------------------------------------
INTERVALS = {"Every 30 minutes": 30, "Every hour": 60, "Every 3 hours": 180,
             "Every 6 hours": 360, "Once a day": 1440}


def gui():
    import tkinter as tk
    from tkinter import messagebox, ttk

    cfg = load_config()
    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry("460x430")
    root.resizable(False, False)
    try:
        ttk.Style(root).theme_use("vista")
    except tk.TclError:
        pass

    frm = ttk.Frame(root, padding=18)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=APP_NAME, font=("Segoe UI", 20, "bold")).pack(anchor="w")
    ttk.Label(frm, text="Islamic wallpapers and quotes, changed automatically.",
              foreground="#555").pack(anchor="w", pady=(0, 14))

    ttk.Label(frm, text="Change wallpaper").pack(anchor="w")
    label_for = {v: k for k, v in INTERVALS.items()}
    combo = ttk.Combobox(frm, state="readonly", values=list(INTERVALS),
                         width=26)
    combo.set(label_for.get(cfg["interval_min"], "Every hour"))
    combo.pack(anchor="w", pady=(2, 10))

    overlay = tk.BooleanVar(value=cfg["overlay"])
    cb = ttk.Checkbutton(frm, text="Show a quote on the wallpaper",
                         variable=overlay)
    cb.pack(anchor="w")
    if not HAVE_PIL:
        overlay.set(False)
        cb.state(["disabled"])
        ttk.Label(frm, text="(Quotes need Pillow: run  pip install pillow)",
                  foreground="#a00").pack(anchor="w")

    status = tk.StringVar(value="Automatic changing is "
                          + ("ON." if cfg["enabled"] else "OFF."))
    ttk.Label(frm, textvariable=status, wraplength=420,
              justify="left").pack(anchor="w", pady=14)

    def save_cfg(enabled=None):
        cfg["interval_min"] = INTERVALS[combo.get()]
        cfg["overlay"] = bool(overlay.get())
        if enabled is not None:
            cfg["enabled"] = enabled
        save_json("config.json", cfg)

    def change_now():
        save_cfg()
        status.set("Getting a new wallpaper...")
        btn_now.state(["disabled"])

        def work():
            msg = apply_once(cfg["overlay"])
            root.after(0, lambda: (status.set(msg), btn_now.state(["!disabled"])))

        threading.Thread(target=work, daemon=True).start()

    def turn_on():
        save_cfg(True)
        ok, msg = enable_auto(cfg["interval_min"])
        if not ok:
            cfg["enabled"] = False
            save_json("config.json", cfg)
        status.set(msg)

    def turn_off():
        save_cfg(False)
        status.set(disable_auto())

    def show_credits():
        credits = load_json("credits.json", {})
        if not credits:
            messagebox.showinfo(APP_NAME, "No photos downloaded yet.")
            return
        lines = [f"{c['title']}\n  {c['artist']} - {c['license']}\n  {c['page']}"
                 for c in credits.values()]
        win = tk.Toplevel(root)
        win.title("Photo credits")
        win.geometry("640x420")
        t = tk.Text(win, wrap="word")
        t.pack(fill="both", expand=True)
        t.insert("1.0", "Photos from Wikimedia Commons. Thank you to the "
                        "photographers.\n\n" + "\n\n".join(lines))
        t.config(state="disabled")

    btn_now = ttk.Button(frm, text="Change wallpaper now", command=change_now)
    btn_now.pack(fill="x", pady=2)
    row = ttk.Frame(frm)
    row.pack(fill="x", pady=2)
    ttk.Button(row, text="Turn ON automatic", command=turn_on).pack(
        side="left", expand=True, fill="x", padx=(0, 3))
    ttk.Button(row, text="Turn OFF", command=turn_off).pack(
        side="left", expand=True, fill="x", padx=(3, 0))
    row2 = ttk.Frame(frm)
    row2.pack(fill="x", pady=2)
    ttk.Button(row2, text="Photo credits", command=show_credits).pack(
        side="left", expand=True, fill="x", padx=(0, 3))
    ttk.Button(row2, text="Open data folder",
               command=lambda: os.startfile(data_dir())).pack(
        side="left", expand=True, fill="x", padx=(3, 0))

    root.mainloop()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="change the wallpaper once and exit")
    args = ap.parse_args()
    if args.apply:
        cfg = load_config()
        log(apply_once(cfg["overlay"]))
    else:
        gui()


if __name__ == "__main__":
    main()