"""
narrar.py — Bom dia, Varejo
Gera a narração do vídeo com a SUA voz, a partir do roteiro.json (prompt v4).

Usa o Chatterbox Multilingual (Resemble AI, licença MIT, roda grátis em CPU ou GPU).
Saídas:
  narracao.wav  -> áudio final, normalizado para Instagram (-14 LUFS)
  tempos.json   -> início e fim de cada cena e de cada frase (o renderizador 3D sincroniza a legenda com isso)

Uso:
  pip install chatterbox-tts soundfile numpy
  python narrar.py roteiro.json --voz minha_voz.wav
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

# tom de cada cena -> parâmetros do Chatterbox
#  exaggeration: expressividade (0.25 calmo … 1.0 muito expressivo)
#  cfg_weight:   aderência ao ritmo da voz de referência; mais baixo = fala mais pausada
TONS = {
    "neutro":  {"exaggeration": 0.45, "cfg_weight": 0.40, "temperature": 0.75},
    "animado": {"exaggeration": 0.65, "cfg_weight": 0.35, "temperature": 0.80},
    "serio":   {"exaggeration": 0.35, "cfg_weight": 0.45, "temperature": 0.70},
}
PAUSA_ENTRE_FRASES_MS = 140   # respiro natural entre frases da mesma cena
FADE_MS = 12                  # evita estalos nas emendas


def frases(texto: str) -> list[str]:
    """Quebra a fala em frases curtas: o modelo soa mais natural e erra menos em trechos curtos."""
    partes = re.split(r"(?<=[.!?…])\s+", texto.strip())
    saida = []
    for p in partes:
        p = p.strip()
        if not p:
            continue
        # frase longa demais: divide na vírgula mais próxima do meio
        if len(p.split()) > 22 and "," in p:
            meio = len(p) // 2
            corte = min((i for i, c in enumerate(p) if c == ","), key=lambda i: abs(i - meio))
            saida += [p[: corte + 1].strip(), p[corte + 1 :].strip()]
        else:
            saida.append(p)
    return saida


def apara_silencio(wav: np.ndarray, sr: int, limiar_db: float = -42) -> np.ndarray:
    """Corta o silêncio do começo e do fim que o modelo às vezes deixa."""
    if wav.size == 0:
        return wav
    janela = int(sr * 0.01)
    energia = np.array([np.sqrt(np.mean(wav[i : i + janela] ** 2) + 1e-12) for i in range(0, len(wav), janela)])
    db = 20 * np.log10(energia + 1e-12)
    voz = np.where(db > limiar_db)[0]
    if voz.size == 0:
        return wav
    ini = max(0, voz[0] * janela - int(sr * 0.03))
    fim = min(len(wav), (voz[-1] + 1) * janela + int(sr * 0.08))
    return wav[ini:fim]


def fade(wav: np.ndarray, sr: int) -> np.ndarray:
    n = min(len(wav) // 2, int(sr * FADE_MS / 1000))
    if n > 0:
        rampa = np.linspace(0, 1, n)
        wav[:n] *= rampa
        wav[-n:] *= rampa[::-1]
    return wav


def silencio(ms: int, sr: int) -> np.ndarray:
    return np.zeros(int(sr * ms / 1000), dtype=np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("roteiro")
    ap.add_argument("--voz", default="minha_voz.wav", help="gravação de referência da sua voz (10 a 20 s)")
    ap.add_argument("--saida", default="narracao.wav")
    ap.add_argument("--tempos", default="tempos.json")
    ap.add_argument("--seed", type=int, default=42, help="mesma seed = mesma 'interpretação' em todo vídeo")
    args = ap.parse_args()

    roteiro = json.loads(Path(args.roteiro).read_text(encoding="utf-8"))
    if not Path(args.voz).exists():
        sys.exit(f"Arquivo de voz não encontrado: {args.voz}")

    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
    print(f"Carregando Chatterbox Multilingual em {device}…")
    modelo = ChatterboxMultilingualTTS.from_pretrained(device=device)
    sr = modelo.sr
    idioma = roteiro.get("voz", {}).get("idioma", "pt")

    pedacos, tempos, t = [], [], 0.0
    pedacos.append(silencio(250, sr)); t += 0.25

    for i, cena in enumerate(roteiro["cenas"]):
        fala = cena.get("fala") or re.sub(r"\*\*", "", cena["narracao"])
        params = TONS.get(cena.get("tom", "neutro"), TONS["neutro"])
        ini_cena, frases_info = t, []
        for j, frase in enumerate(frases(fala)):
            torch.manual_seed(args.seed + i * 100 + j)
            wav = modelo.generate(frase, language_id=idioma, audio_prompt_path=args.voz, **params)
            wav = wav.squeeze().detach().cpu().numpy().astype(np.float32)
            wav = fade(apara_silencio(wav, sr), sr)
            dur = len(wav) / sr
            frases_info.append({"texto": frase, "inicio": round(t, 3), "fim": round(t + dur, 3)})
            pedacos.append(wav); t += dur
            pedacos.append(silencio(PAUSA_ENTRE_FRASES_MS, sr)); t += PAUSA_ENTRE_FRASES_MS / 1000
            print(f"  cena {i + 1:02d} · frase {j + 1}: {dur:4.1f}s  {frase[:60]}")
        pausa = int(cena.get("pausa_depois_ms", 300))
        pedacos.append(silencio(pausa, sr)); t += pausa / 1000
        tempos.append({"cena": i, "tipo": cena["tipo"], "inicio": round(ini_cena, 3), "fim": round(t, 3), "frases": frases_info})

    pedacos.append(silencio(600, sr)); t += 0.6
    bruto = Path(args.saida).with_suffix(".bruto.wav")
    sf.write(bruto, np.concatenate(pedacos), sr)

    # acabamento de estúdio: tira ronco grave, suaviza sibilância, comprime leve e normaliza para -14 LUFS
    filtros = ("highpass=f=70,"
               "deesser=i=0.35,"
               "acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120:makeup=2,"
               "loudnorm=I=-14:TP=-1.5:LRA=9")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(bruto), "-af", filtros,
                    "-ar", "48000", "-ac", "1", args.saida], check=True)
    bruto.unlink(missing_ok=True)

    Path(args.tempos).write_text(json.dumps({"duracao": round(t, 3), "cenas": tempos}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nPronto: {args.saida} ({t:.1f}s) e {args.tempos}")


if __name__ == "__main__":
    main()
