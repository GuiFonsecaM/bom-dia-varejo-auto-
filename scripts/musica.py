"""
musica.py — trilha de telejornal gerada por código (sem direitos autorais).

Gera trilha.wav (48 kHz, estéreo) do tamanho da narração, com:
  - vinheta de abertura (subida + impacto de tímpano)
  - "relógio" de redação em semicolcheias, baixo pulsante, pad e sino em Ré menor (i–VI–III–VII)
  - bateria leve; troca de clima por modo (noticias, curiosidade, mundo)
  - "whoosh" curto em cada troca de cena (lido de tempos.json)
  - impacto final
Uso: python musica.py --tempos tempos.json --modo noticias --saida trilha.wav
"""
import argparse
import json

import numpy as np
import soundfile as sf

SR = 48000
rng = np.random.default_rng(7)


def t_(d):
    return np.arange(int(d * SR)) / SR


def env(n, a=0.005, r=0.2, dur=None):
    """envelope ataque-decaimento exponencial"""
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / max(r, 1e-4))
    return e


def lowpass(x, fc):
    a = np.exp(-2 * np.pi * fc / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):  # um polo; só usado em trechos curtos
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def lp_fast(x, fc):
    # passa-baixa por média móvel em cascata (rápido, suficiente para pad/ruído)
    w = max(1, int(SR / fc / 2))
    k = np.ones(w) / w
    return np.convolve(np.convolve(x, k, mode="same"), k, mode="same")


def nota(f, d, kind="sine", a=0.005, r=0.3, det=0.0):
    t = t_(d)
    if kind == "sine":
        s = np.sin(2 * np.pi * f * t)
    elif kind == "saw":
        s = sum(np.sin(2 * np.pi * f * (1 + det * k) * t * h) / h for k in (-1, 0, 1) for h in range(1, 9)) / 3
    elif kind == "bell":  # FM
        s = np.sin(2 * np.pi * f * t + 2.2 * np.exp(-t * 6) * np.sin(2 * np.pi * f * 3.5 * t))
    elif kind == "pluck":
        s = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2 * f * t) + 0.12 * np.sin(2 * np.pi * 3 * f * t)
    return s * env(len(t), a, r)


def add(buf, x, at, gain=1.0, pan=0.0):
    i = int(at * SR)
    if i >= buf.shape[0]:
        return
    x = x[: buf.shape[0] - i]
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    buf[i:i + len(x), 0] += x * gain * l
    buf[i:i + len(x), 1] += x * gain * r


def hz(m):
    return 440 * 2 ** ((m - 69) / 12)


def kick():
    t = t_(0.45)
    f = 50 + 90 * np.exp(-t * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7)


def snare():
    t = t_(0.25)
    n = rng.standard_normal(len(t))
    n = n - lp_fast(n, 900)
    return (0.7 * n + 0.4 * np.sin(2 * np.pi * 190 * t)) * np.exp(-t * 18)


def hat(open_=False):
    t = t_(0.12 if not open_ else 0.3)
    n = rng.standard_normal(len(t))
    n = n - lp_fast(n, 6000)
    return n * np.exp(-t * (45 if not open_ else 12))


def tick():
    t = t_(0.03)
    return np.sin(2 * np.pi * 2600 * t) * np.exp(-t * 180)


def whoosh(d=0.7, up=True):
    t = t_(d)
    n = rng.standard_normal(len(t))
    # varredura: mistura de passa-baixas com corte crescente
    lo, hi = lp_fast(n, 400), lp_fast(n, 3500)
    k = (t / d) if up else (1 - t / d)
    s = lo * (1 - k) + hi * k
    e = np.sin(np.pi * np.clip(t / d, 0, 1)) ** 2
    return s * e


def impacto():
    t = t_(2.2)
    f = 46 + 60 * np.exp(-t * 9)
    tim = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.2)
    n = rng.standard_normal(len(t))
    n = lp_fast(n, 1800) * np.exp(-t * 6)
    bell = nota(hz(74), 2.2, "bell", 0.002, 0.9) + 0.6 * nota(hz(81), 2.2, "bell", 0.002, 0.8)
    return tim * 1.0 + n * 0.5 + bell * 0.25


def reverb(x, wet=0.22):
    out = x.copy()
    for d, g in [(0.029, 0.5), (0.037, 0.45), (0.051, 0.4), (0.071, 0.35), (0.113, 0.28), (0.173, 0.2)]:
        k = int(d * SR)
        y = np.zeros_like(x)
        y[k:] = x[:-k] * g
        out += y * wet
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tempos", default="tempos.json")
    ap.add_argument("--modo", default="noticias")
    ap.add_argument("--saida", default="trilha.wav")
    ap.add_argument("--duracao", type=float, default=None)
    a = ap.parse_args()
    try:
        tempos = json.load(open(a.tempos, encoding="utf-8"))
    except Exception:
        tempos = {"duracao": a.duracao or 30, "cenas": []}
    dur = (a.duracao or tempos.get("duracao", 30)) + 1.5
    modo = a.modo

    bpm = {"noticias": 112, "curiosidade": 100, "mundo": 96}.get(modo, 108)
    beat = 60 / bpm
    bar = beat * 4
    # Ré menor: Dm Bb F C  (curiosidade: F C Dm Bb, mais leve; mundo: Dm Bb Gm A, mais grave)
    prog = {
        "noticias": [(62, [62, 65, 69]), (58, [58, 62, 65]), (65, [65, 69, 72]), (60, [60, 64, 67])],
        "curiosidade": [(65, [65, 69, 72]), (60, [60, 64, 67]), (62, [62, 65, 69]), (58, [58, 62, 65])],
        "mundo": [(62, [62, 65, 69]), (58, [58, 62, 65]), (55, [55, 58, 62]), (57, [57, 61, 64])],
    }.get(modo)

    buf = np.zeros((int(dur * SR) + SR, 2))
    intro = 2.0  # a música entra depois da vinheta
    # vinheta
    add(buf, whoosh(1.6, True), 0.0, 0.5)
    add(buf, impacto(), 1.5, 0.9)

    nbars = int((dur - intro) / bar) + 1
    for b in range(nbars):
        t0 = intro + b * bar
        root, chord = prog[b % 4]
        # pad (acorde) com ataque lento
        for k, m in enumerate(chord):
            p = nota(hz(m - 12), bar + 0.3, "saw", 0.6, 2.5, det=0.004)
            add(buf, lp_fast(p, 1400), t0, 0.06, pan=(k - 1) * 0.5)
        # baixo pulsante em colcheias
        for e in range(8):
            add(buf, nota(hz(root - 24), beat / 2, "pluck", 0.004, 0.12), t0 + e * beat / 2, 0.38)
        # sino/arpejo
        seq = [chord[0], chord[1], chord[2], chord[1] + 12 if modo != "mundo" else chord[0] + 12]
        for e in range(8):
            if modo == "mundo" and e % 2:
                continue
            m = seq[e % 4] + 12
            add(buf, nota(hz(m), 0.6, "bell", 0.002, 0.25), t0 + e * beat / 2, 0.07, pan=0.35 if e % 2 else -0.35)
        # relógio de redação
        for e in range(16):
            add(buf, tick(), t0 + e * beat / 4, 0.09 if e % 4 == 0 else 0.045, pan=0.2)
        # bateria (entra no 2º compasso)
        if b >= 1:
            for e in range(4):
                if e in (0, 2) or (modo == "noticias" and e == 3 and b % 2):
                    add(buf, kick(), t0 + e * beat, 0.55)
                if e in (1, 3) and modo != "mundo":
                    add(buf, snare(), t0 + e * beat, 0.16)
            for e in range(8):
                add(buf, hat(e % 4 == 3), t0 + e * beat / 2, 0.05 if e % 2 else 0.07, pan=-0.3)

    # whoosh nas trocas de cena
    for c in tempos.get("cenas", [])[1:]:
        add(buf, whoosh(0.55, True), max(0, c["inicio"] - 0.35), 0.16)
    # impacto final + fade
    fim = dur - 1.5
    add(buf, impacto(), max(0, fim - 0.4), 0.7)
    buf = buf[: int(dur * SR)]
    fade = np.ones(len(buf))
    n = int(1.2 * SR)
    fade[-n:] = np.linspace(1, 0, n)
    buf *= fade[:, None]
    buf[:, 0] = reverb(buf[:, 0])
    buf[:, 1] = reverb(buf[:, 1])
    pico = np.max(np.abs(buf)) or 1
    buf = buf / pico * 0.89
    sf.write(a.saida, buf.astype(np.float32), SR)
    print(f"Trilha: {a.saida} ({dur:.1f}s, {bpm} bpm, modo {modo})")


if __name__ == "__main__":
    main()
