#!/usr/bin/env python3
"""Собирает видео-гайд из guides/<slug>/guide.json.

  python3 tools/build.py mortis            # полный цикл -> out/mortis/<slug>.mp4
  python3 tools/build.py mortis --stills   # только контрольные кадры (быстро)

Шаги: иконки с вики -> озвучка RHVoice -> тайминги по длине фраз ->
HTML-шаблон -> покадровый рендер (Playwright) -> музыка + эффекты + голос -> MP4.
"""
import json, os, re, shutil, subprocess, sys, urllib.parse, urllib.request, wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "brawl-guides-builder/1.0"}
WIKI_API = "https://brawlstars.fandom.com/api.php"
VOICE = os.environ.get("GUIDE_VOICE", "aleksandr-hq")
RATE = os.environ.get("GUIDE_RATE", "135")  # скорость речи, %


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


def vo_lines(g):
    return [("hook", g["hook"]["vo"]), ("g1", g["gadgets"][0]["vo"]), ("g2", g["gadgets"][1]["vo"]),
            ("s1", g["starpowers"][0]["vo"]), ("s2", g["starpowers"][1]["vo"]),
            ("gear", g["gears"]["vo"]), ("modes", g["modes"]["vo"]), ("final", g["final"]["vo"])]


def tts(g, vdir, rate):
    os.makedirs(vdir, exist_ok=True)
    dur = {}
    for key, text in vo_lines(g):
        txt, wav = os.path.join(vdir, key + ".txt"), os.path.join(vdir, key + ".wav")
        open(txt, "w").write(text)
        subprocess.run(["RHVoice-test", "-p", VOICE, "-r", str(rate), "-i", txt, "-o", wav], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with wave.open(wav) as w:
            dur[key] = w.getnframes() / w.getframerate()
    return dur


def timeline(g, d):
    """Длительность сцен подстраивается под озвучку. Возвращает тайминги и точки старта фраз."""
    sc, vo, t = [], {}, 0.0
    def card_stamp(c):  # когда падает штамп вердикта относительно старта карточки
        return 1.0 + c["rating"] * .13 + .25
    # hook
    dur = max(2.6, d["hook"] + .7)
    sc.append({"k": "hook", "start": 0, "end": dur, "cues": {"rib": min(1.35, dur - 1.0)}}); vo["hook"] = .25; t = dur
    for k, items, a, b in (("gad", g["gadgets"], "g1", "g2"), ("sp", g["starpowers"], "s1", "s2")):
        c1 = .35
        c2 = c1 + max(card_stamp(items[0]) + .55, d[a] + .25)
        end = c2 + max(card_stamp(items[1]) + 1.1, d[b] + .6)
        r0, r1 = items[0]["rating"], items[1]["rating"]
        cues = {"c1": c1, "c2": c2,
                "dim1": (c2 + card_stamp(items[1]) + .35) if r0 < r1 else None,
                "dim2": (c2 + card_stamp(items[1]) + .35) if r1 < r0 else None}
        sc.append({"k": k, "start": t, "end": t + end, "cues": cues})
        vo[a], vo[b] = t + c1 + .05, t + c2 + .05
        t += end
    dur = max(3.0, d["gear"] + 1.0)
    sc.append({"k": "gear", "start": t, "end": t + dur, "cues": {"stamp": min(1.5, dur - 1.0)}}); vo["gear"] = t + .3; t += dur
    n = len(g["modes"]["rows"])
    step = max(.95, (d["modes"] - .3) / n)
    rows = [.35 + i * step for i in range(n)]
    dur = max(rows[-1] + 2.0, d["modes"] + .75)
    sc.append({"k": "maps", "start": t, "end": t + dur, "cues": {"rows": rows}}); vo["modes"] = t + .3; t += dur
    dur = max(3.4, d["final"] + 1.1)
    act = [1.2, 1.38]
    sc.append({"k": "fin", "start": t, "end": t + dur, "cues": {"act": act}}); vo["final"] = t + .3; t += dur
    return {"scenes": sc, "duration": round(t, 3), "vo": vo}


def main():
    slug = sys.argv[1]
    stills = "--stills" in sys.argv
    gdir, out = os.path.join(ROOT, "guides", slug), os.path.join(ROOT, "out", slug)
    g = json.load(open(os.path.join(gdir, "guide.json")))
    os.makedirs(out, exist_ok=True)
    print("1/5 иконки")
    fetch_assets(g, os.path.join(out, "assets"))
    print("2/5 озвучка (" + VOICE + ")")
    rate = int(RATE)
    while True:
        d = tts(g, os.path.join(out, "vo"), rate)
        tl = timeline(g, d)
        if tl["duration"] <= 31 or rate >= 165:
            break
        rate += 8
        print("   длинновато (%.1f с), ускоряю голос до %d%%" % (tl["duration"], rate))
    print("   длительность ролика: %.1f с" % tl["duration"])
    print("3/5 шаблон")
    shutil.copytree(os.path.join(ROOT, "template", "fonts"), os.path.join(out, "fonts"), dirs_exist_ok=True)
    html = open(os.path.join(ROOT, "template", "video.html")).read()
    data = "window.G=%s;window.TL=%s;" % (json.dumps(g, ensure_ascii=False), json.dumps(tl))
    open(os.path.join(out, "index.html"), "w").write(html.replace("/*DATA*/", data.replace("</", "<\\/")))
    json.dump(tl, open(os.path.join(out, "timeline.json"), "w"), indent=1)
    render = ["node", os.path.join(ROOT, "tools", "render.js"), os.path.join(out, "index.html")]
    if stills:
        ts = [s["start"] + (s["end"] - s["start"]) * .85 for s in tl["scenes"]]
        subprocess.run(render + ["stills"] + ["%.2f" % x for x in ts], check=True)
        print("кадры:", os.path.join(out, "stills"))
        return
    print("4/5 рендер кадров")
    subprocess.run(render + ["sfx"], check=True)
    subprocess.run(render + ["video"], check=True)
    print("5/5 звук")
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "audio.py"), out], check=True)
    final = os.path.join(out, slug + ".mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(out, "video_noaudio.mp4"),
                    "-i", os.path.join(out, "audio.wav"), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", "-movflags", "+faststart", final], check=True)
    print("ГОТОВО:", final)


if __name__ == "__main__":
    main()
