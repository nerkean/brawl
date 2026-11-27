#!/usr/bin/env python3
"""Звук ролика: синтезированный бит-заглушка + звуковые эффекты (sfx.json).  Использование: audio.py <out_dir>"""
import hashlib, json, os, random, sys
import numpy as np
from scipy.signal import butter, sosfilt
from scipy.io import wavfile

OUT = sys.argv[1]
TL = json.load(open(os.path.join(OUT, "timeline.json")))
SR = 44100; D = TL["duration"] + 0.4; N = int(SR * D); rng = np.random.default_rng(7)
music = np.zeros((N, 2)); fx = np.zeros((N, 2))
# Музыка своя для каждого бравлера: параметры выбираются по имени папки (slug) — стабильно для одного
# и того же бравлера, разные для разных. GUIDE_MUSIC_SEED=<число> — принудительно другой вариант.
SEED = int(os.environ.get("GUIDE_MUSIC_SEED") or int(hashlib.md5(os.path.basename(os.path.normpath(OUT)).encode()).hexdigest(), 16) % 10**9)
mr = random.Random(SEED)


def add(buf, t, sig, pan=0.0, g=1.0):
    i = int(t * SR); j = min(N, i + len(sig))
    if i >= N or j <= 0: return
    s = sig[:j - i] * g
    buf[i:j, 0] += s * (1 - pan) ** .5; buf[i:j, 1] += s * (1 + pan) ** .5

def env(n, a=.002, d=.2):
    t = np.arange(n) / SR; return np.minimum(1, t / a) * np.exp(-t / d)
def bp(x, lo, hi): return sosfilt(butter(2, [lo, hi], 'band', fs=SR, output='sos'), x)
def hp(x, f): return sosfilt(butter(2, f, 'high', fs=SR, output='sos'), x)
def lp(x, f): return sosfilt(butter(2, f, 'low', fs=SR, output='sos'), x)
nf = lambda m: 440 * 2 ** ((m - 69) / 12)

# ---------- параметры трека ----------
BPM = mr.choice([108, 112, 116, 120, 124, 128]); beat = 60 / BPM
KEY = mr.choice([-5, -3, -2, 0, 2, 3])
PROGS = [
    [(57, [57, 60, 64]), (53, [53, 57, 60]), (48, [55, 60, 64]), (55, [55, 59, 62])],  # Am F C G
    [(57, [57, 60, 64]), (55, [55, 59, 62]), (53, [53, 57, 60]), (52, [52, 56, 59])],  # Am G F E
    [(57, [57, 60, 64]), (52, [55, 59, 64]), (53, [53, 57, 60]), (55, [55, 59, 62])],  # Am Em F G
    [(57, [57, 60, 64]), (50, [57, 62, 65]), (52, [55, 59, 64]), (57, [57, 60, 64])],  # Am Dm Em Am
    [(53, [53, 57, 60]), (55, [55, 59, 62]), (57, [57, 60, 64]), (57, [57, 60, 64])],  # F G Am Am
]
prog = [(r + KEY, [c + KEY for c in ch]) for r, ch in mr.choice(PROGS)]
KICKS = mr.choice([[0, 2, 4, 6], [0, 3, 4], [0, 3, 6], [0, 4, 5]])          # в восьмых долях такта
HATS = mr.choice(["8", "16", "off"])
BASS = mr.choice(["oct", "pulse", "sync"])
LEAD = mr.choice(["pluck", "chip", "bell", "saw"])
ARP = mr.choice([[0, 1, 2, 4], [4, 2, 1, 0], [0, 2, 1, 2], [0, 1, 2, 1, 4, 2, 1, 2]])
PAD = mr.random() < .7
print("   музыка: seed=%d, %d BPM, тональность %+d, бас %s, мелодия %s" % (SEED, BPM, KEY, BASS, LEAD))

def kick():
    n = int(.35 * SR); t = np.arange(n) / SR; f = 45 + 110 * np.exp(-t / .035)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / .16) + hp(rng.standard_normal(n), 3000) * env(n, .0005, .004) * .3
def clap():
    n = int(.25 * SR); x = bp(rng.standard_normal(n), 900, 4000)
    e = sum(np.roll(env(n, .0005, .012), int(k * SR)) for k in (0, .011, .022)) * .5 + env(n, .0005, .09) * .6
    return x * e * .55
def hat(o=False):
    n = int((.18 if o else .05) * SR); return hp(rng.standard_normal(n), 7000) * env(n, .0005, .06 if o else .012) * .28
def bass(m, dur):
    n = int(dur * SR); t = np.arange(n) / SR; f = nf(m)
    x = np.sign(np.sin(2 * np.pi * f * t)) * .5 + np.sin(2 * np.pi * f * t)
    return lp(x, 700) * np.minimum(1, t / .005) * np.exp(-t / .25) * .33
def lead(m, dur=.4):
    n = int(dur * SR); t = np.arange(n) / SR; f = nf(m); w = 2 * np.pi * f * t
    if LEAD == "pluck": x = np.sin(w) + .5 * np.sin(2 * w) + .25 * np.sin(3.01 * w); e = env(n, .002, .12)
    elif LEAD == "chip": x = lp(np.sign(np.sin(w)) * .6, 3500); e = env(n, .002, .09)
    elif LEAD == "bell": x = np.sin(w) + .4 * np.sin(2.76 * w) * np.exp(-t / .05); e = env(n, .001, .2)
    else: x = lp(2 * ((f * t) % 1) - 1, 2200) * .8; e = env(n, .003, .1)
    return x * e * .12
def pad(ms, dur):
    n = int(dur * SR); t = np.arange(n) / SR; x = np.zeros(n)
    for m in ms:
        for dt in (-.08, .08): x += np.sin(2 * np.pi * nf(m) * (1 + dt / 100) * t) + .3 * np.sin(2 * np.pi * 2 * nf(m) * t)
    return lp(x, 1800) * np.minimum(1, t / .25) * np.minimum(1, (dur - t) / .3) * .035

K = kick(); C = clap(); nbar = int(D / (4 * beat)) + 1; kick_times = []
for bar in range(nbar):
    t0 = bar * 4 * beat; root, ch = prog[bar % 4]; e8 = beat / 2
    for k in KICKS:
        t = t0 + k * e8
        if t >= 1 or t == 0: add(music, t, K, g=.9); kick_times.append(t)
    for b in range(4):
        t = t0 + b * beat
        if b in (1, 3) and t >= 1: add(music, t, C)
        if t >= 1:
            if HATS == "off": add(music, t + e8, hat(b == 3 and bar % 2), pan=.3)
            else:
                for q in range(2 if HATS == "8" else 4):
                    add(music, t + q * beat / (2 if HATS == "8" else 4), hat(), pan=(.3 if q % 2 else -.3), g=(.8 if q % 2 else .55))
        if BASS == "oct":
            for k in range(2): add(music, t + k * e8, bass(root - 12 if k == 0 else root, e8 * .95))
        elif BASS == "pulse":
            for k in range(2): add(music, t + k * e8, bass(root - 12, e8 * .9), g=(1 if k == 0 else .7))
        else:
            add(music, t, bass(root - 12, e8 * 1.4)); 
            if b % 2: add(music, t + e8 * 1.5, bass(root, e8 * .5))
        if t >= 2.5:
            notes = [ch[0] + 12, ch[1] + 12, ch[2] + 12, ch[0] + 24, ch[1] + 24]
            for q in range(4):
                add(music, t + q * beat / 4, lead(notes[ARP[(b * 4 + q) % len(ARP)]]), pan=(-.4 if q % 2 else .4))
    if PAD: add(music, t0, pad(ch, 4 * beat))
duck = np.ones(N)
for t in kick_times:
    i = int(t * SR); n = int(.18 * SR); seg = duck[i:i + n]
    duck[i:i + n] = np.minimum(seg, .55 + .45 * np.linspace(0, 1, n)[:len(seg)] ** 1.5)
music *= duck[:, None]

# ---------- sfx ----------
def whoosh(dur=.45):
    n = int(dur * SR); x = rng.standard_normal(n); out = np.zeros(n); seg = 512
    for s in range(0, n, seg):
        fc = 500 + 5000 * np.sin(np.pi * s / n) ** 2
        out[s:s + seg] = bp(x[max(0, s - 2048):s + seg], fc * .7, min(fc * 1.4, 20000))[-len(out[s:s + seg]):]
    return out * np.sin(np.pi * np.arange(n) / SR / dur) ** 2 * .32
def tick(f=2200): n = int(.04 * SR); t = np.arange(n) / SR; return np.sin(2 * np.pi * f * t) * env(n, .0005, .01) * .22
def pop(f0=500):
    n = int(.12 * SR); t = np.arange(n) / SR; f = f0 * (1 + 1.2 * np.minimum(1, t / .05))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, .001, .035) * .3
def stamp(notes, g):
    n = int(.4 * SR); t = np.arange(n) / SR; f = 60 + 180 * np.exp(-t / .03)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / .12) * .7
    click = bp(rng.standard_normal(n), 1500, 6000) * env(n, .0005, .015) * .4
    return body + click + sum(np.sin(2 * np.pi * nf(x) * t) * env(n, .002, .15) for x in notes) * g
def boing():
    n = int(.5 * SR); t = np.arange(n) / SR; f = 180 + 260 * np.exp(-t / .08) * np.abs(np.cos(t * 28))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, .002, .18) * .35
def slam():
    n = int(.3 * SR); t = np.arange(n) / SR; f = 55 + 140 * np.exp(-t / .025)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / .09) * .55 + hp(rng.standard_normal(n), 2500) * env(n, .0005, .02) * .35
S = {'slam': (slam(), .9), 'whoosh': (whoosh(), .9), 'swoosh': (whoosh(.3), .5), 'swoosh2': (whoosh(.3), .45), 'tick2': (tick(1600), 1.2),
     'pop': (pop(), 1), 'pop2': (pop(320), 1.3), 'boing': (boing(), 1),
     'stampG': (stamp([76, 79, 84], .07), 1), 'stampM': (stamp([72, 76], .08), .8), 'stampB': (stamp([64, 63], .09), 1),
     **{f'tick{i}': (tick(1500 * 2 ** (i * 2 / 12)), 1.1) for i in range(5)}}
for t, k in {tuple(x) for x in json.load(open(os.path.join(OUT, "sfx.json")))}:
    sig, g = S[k]; add(fx, t, sig, g=g)

mix = music * .8 + fx * .8
fo = int(1.2 * SR); mix[-fo:] *= np.linspace(1, 0, fo)[:, None]
mix = np.tanh(mix * 1.2) / np.tanh(1.2); mix /= np.abs(mix).max() / .89
wavfile.write(os.path.join(OUT, "audio.wav"), SR, (mix * 32767).astype(np.int16))
print("   audio.wav готов")
