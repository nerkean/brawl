#!/usr/bin/env python3
"""Собирает видео-гайд из guides/<slug>/guide.json.

  python3 tools/build.py mortis            # полный цикл -> out/mortis/<slug>.mp4
  python3 tools/build.py mortis --stills   # только контрольные кадры (быстро)

Шаги: иконки с вики -> тайминги -> HTML-шаблон -> покадровый рендер (Playwright) ->
музыка + звуковые эффекты -> MP4. Озвучки нет: только музыка, эффекты и текст.
"""
import json, os, re, shutil, subprocess, sys, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "brawl-guides-builder/1.0"}
WIKI_API = "https://brawlstars.fandom.com/api.php"
# Сколько секунд держится каждый экран (время на чтение). Итог ~27 с.
HOLD = {"hook": 2.4, "card": 3.3, "gear": 3.2, "modes": 4.6, "fin": 3.6}


def safe(name):
    return re.sub(r"[^\w.-]+", "_", name)


def http_json(url, params):
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params), headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def all_icons(g):
    yield g["hook"]["icon"]
    for c in g["gadgets"] + g["starpowers"]:
        yield c["icon"]
    for x in g["gears"]["items"]:
        yield x["icon"]
    for row in g["modes"]["rows"]:
        yield from row["icons"]
    for n in g["final"]["next"]:
        yield n["icon"]


def fetch_assets(g, adir):
    """Скачивает файлы вики по их названиям (File:...), конвертирует в PNG и обрезает поля."""
    from PIL import Image
    os.makedirs(adir, exist_ok=True)
    need = [f for f in dict.fromkeys(all_icons(g)) if not os.path.exists(os.path.join(adir, safe(f)))]
    for i in range(0, len(need), 40):
        chunk = need[i:i + 40]
        d = http_json(WIKI_API, {"action": "query", "prop": "imageinfo", "iiprop": "url", "format": "json",
                                 "titles": "|".join("File:" + f for f in chunk)})
        norm = {n["to"]: n["from"] for n in d["query"].get("normalized", [])}
        missing = []
        for p in d["query"]["pages"].values():
            title = norm.get(p["title"], p["title"])[5:]
            if "imageinfo" not in p:
                missing.append(title)
                continue
            req = urllib.request.Request(p["imageinfo"][0]["url"], headers=UA)
            raw = urllib.request.urlopen(req, timeout=120).read()
            tmp = os.path.join(adir, ".dl")
            open(tmp, "wb").write(raw)
            im = Image.open(tmp).convert("RGBA")
            im.thumbnail((1200, 1200))
            bb = im.getbbox()
            if bb:
                im = im.crop(bb)
            im.save(os.path.join(adir, safe(title)))
            os.remove(tmp)
            print("  icon:", title)
        if missing:
            sys.exit("Нет таких файлов на вики: " + ", ".join(missing) +
                     "\nНайди правильные названия: api.php?action=query&list=allimages&aiprefix=...")


def timeline(g, d):
    """Экраны ролика по порядку: заставка, по экрану на каждый гаджет и пассивку, снаряжение, режимы, финал."""
    sc, t = [], 0.0
    def add(k, dur, **kw):
        nonlocal t
        sc.append({"k": k, "start": round(t, 3), "end": round(t + dur, 3), **kw}); t += dur
    add("hook", d["hook"])
    for src, sec, name in (("gadgets", "gad", "ГАДЖЕТ"), ("starpowers", "sp", "ПАССИВКА")):
        n = len(g[src])
        for i in range(n):
            add("card", d["card"], src=src, sec=sec, idx=i, label="%s %d ИЗ %d" % (name, i + 1, n))
    add("gear", d["gear"], label="СНАРЯЖЕНИЕ")
    rows = len(g["modes"]["rows"])
    add("modes", max(d["modes"], .35 + rows * 1.0 + 1.3), rows=[.35 + i * 1.0 for i in range(rows)], label="РЕЖИМЫ")
    add("fin", d["fin"], label="ДАЛЬШЕ")
    return {"screens": sc, "duration": round(t, 3)}


def main():
    slug = sys.argv[1]
    stills = "--stills" in sys.argv
    gdir, out = os.path.join(ROOT, "guides", slug), os.path.join(ROOT, "out", slug)
    g = json.load(open(os.path.join(gdir, "guide.json")))
    os.makedirs(out, exist_ok=True)
    print("1/4 иконки")
    fetch_assets(g, os.path.join(out, "assets"))
    tl = timeline(g, HOLD)
    print("   длительность ролика: %.1f с" % tl["duration"])
    print("2/4 шаблон")
    shutil.copytree(os.path.join(ROOT, "template", "fonts"), os.path.join(out, "fonts"), dirs_exist_ok=True)
    html = open(os.path.join(ROOT, "template", "video.html")).read()
    data = "window.G=%s;window.TL=%s;" % (json.dumps(g, ensure_ascii=False), json.dumps(tl))
    open(os.path.join(out, "index.html"), "w").write(html.replace("/*DATA*/", data.replace("</", "<\\/")))
    json.dump(tl, open(os.path.join(out, "timeline.json"), "w"), indent=1)
    render = ["node", os.path.join(ROOT, "tools", "render.js"), os.path.join(out, "index.html")]
    if stills:
        ts = [s["start"] + (s["end"] - s["start"]) * .85 for s in tl["screens"]]
        subprocess.run(render + ["stills"] + ["%.2f" % x for x in ts], check=True)
        print("кадры:", os.path.join(out, "stills"))
        return
    print("3/4 рендер кадров")
    subprocess.run(render + ["sfx"], check=True)
    subprocess.run(render + ["video"], check=True)
    print("4/4 звук")
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "audio.py"), out], check=True)
    final = os.path.join(out, slug + ".mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(out, "video_noaudio.mp4"),
                    "-i", os.path.join(out, "audio.wav"), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", "-movflags", "+faststart", final], check=True)
    print("ГОТОВО:", final)


if __name__ == "__main__":
    main()
