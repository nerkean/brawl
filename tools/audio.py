#!/usr/bin/env python3
"""Звук ролика: синтезированный бит-заглушка + звуковые эффекты (sfx.json).  Использование: audio.py <out_dir>"""
import json, os, sys
import numpy as np
from scipy.signal import butter, sosfilt
from scipy.io import wavfile

OUT = sys.argv[1]
TL = json.load(open(os.path.join(OUT, "timeline.json")))
SR = 44100; D = TL["duration"] + 0.4; N = int(SR * D); rng = np.random.default_rng(7)
music = np.zeros((N, 2)); fx = np.zeros((N, 2))


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
BPM = 120; beat = 60 / BPM

# ---------- music ----------
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
def pluck(m, dur=.4):
    n = int(dur * SR); t = np.arange(n) / SR; f = nf(m)
    x = np.sin(2 * np.pi * f * t) + .5 * np.sin(2 * np.pi * 2 * f * t) + .25 * np.sin(2 * np.pi * 3.01 * f * t)
    return x * env(n, .002, .12) * .12
def pad(ms, dur):
    n = int(dur * SR); t = np.arange(n) / SR; x = np.zeros(n)
    for m in ms:
        for dt in (-.08, .08): x += np.sin(2 * np.pi * nf(m) * (1 + dt / 100) * t) + .3 * np.sin(2 * np.pi * 2 * nf(m) * t)
    return lp(x, 1800) * np.minimum(1, t / .25) * np.minimum(1, (dur - t) / .3) * .035
prog = [(57, [57, 60, 64]), (53, [53, 57, 60]), (48, [55, 60, 64]), (55, [55, 59, 62])]
K = kick(); C = clap(); nb = int(D / beat)
for b in range(nb):
    t = b * beat; root, ch = prog[(b // 4) % 4]
    if t >= 1 or b == 0: add(music, t, K, g=.9)
    if b % 4 in (1, 3) and t >= 1: add(music, t, C)
    if t >= 1:
        add(music, t + beat / 2, hat(b % 8 == 7), pan=.3)
        add(music, t + beat / 4, hat(), pan=-.3, g=.6); add(music, t + 3 * beat / 4, hat(), pan=-.3, g=.6)
    for k in range(2): add(music, t + k * beat / 2, bass(root - 12 if k == 0 else root, beat / 2 * .95))
    if b % 4 == 0: add(music, t, pad(ch, 4 * beat))
    if t >= 3:
        arp = [ch[0] + 12, ch[1] + 12, ch[2] + 12, ch[1] + 24]
        for k in range(4): add(music, t + k * beat / 4, pluck(arp[(b * 4 + k) % 4]), pan=(-.4 if k % 2 else .4))
duck = np.ones(N)
for b in range(nb):
    i = int(b * beat * SR); n = int(.18 * SR); seg = duck[i:i + n]
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
