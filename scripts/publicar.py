"""
publicar.py — publica o Reel no Instagram (API do Instagram com login do Instagram).

Variáveis: IG_TOKEN, IG_USER_ID, VIDEO_URL (endereço público do .mp4), IG_API_VERSION (opcional)
Lê roteiro.json para montar a legenda (legenda_post + hashtags).
Saída (GITHUB_OUTPUT): media_id, permalink
"""
import json
import os
import re
import sys
import time

import requests

VER = os.environ.get("IG_API_VERSION", "v24.0")
G = f"https://graph.instagram.com/{VER}"
TOKEN = os.environ["IG_TOKEN"]
IG = os.environ["IG_USER_ID"]
VIDEO_URL = os.environ["VIDEO_URL"]


def legenda(rot):
    texto = (rot.get("legenda_post") or rot.get("titulo") or "").strip()
    texto = re.sub(r"(?i)leitura editorial:?\s*", "", texto)
    tags_texto = set(t.lower() for t in re.findall(r"#\w+", texto))
    extras = [h if h.startswith("#") else "#" + h for h in rot.get("hashtags", [])]
    extras = [h for h in extras if h.lower() not in tags_texto]
    if "#bomdiavarejo" not in tags_texto and "#BomDiaVarejo" not in extras:
        extras.insert(0, "#BomDiaVarejo")
    # Instagram: no máximo 30 hashtags e 2.200 caracteres
    vagas = max(0, 30 - len(tags_texto))
    extras = extras[:vagas]
    if extras:
        texto += "\n\n" + " ".join(extras)
    if len(texto) > 2200:
        corpo, _, tags = texto.rpartition("\n\n")
        texto = corpo[: 2200 - len(tags) - 3].rstrip() + "…\n\n" + tags
    return texto[:2200]


def checar(r):
    if r.status_code >= 400:
        print("Erro da API do Instagram:", r.status_code, r.text)
        sys.exit(1)
    return r.json()


def main():
    rot = json.load(open("roteiro.json", encoding="utf-8"))
    cap = legenda(rot)
    print("Legenda com", len(cap), "caracteres")

    c = checar(requests.post(f"{G}/{IG}/media", data={
        "media_type": "REELS", "video_url": VIDEO_URL, "caption": cap,
        "share_to_feed": "true", "access_token": TOKEN}, timeout=60))
    cid = c["id"]
    print("Contêiner criado:", cid)

    for i in range(60):  # até 15 min
        time.sleep(15)
        s = checar(requests.get(f"{G}/{cid}", params={"fields": "status_code,status", "access_token": TOKEN}, timeout=30))
        print("  status:", s.get("status_code"), s.get("status", ""))
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") in ("ERROR", "EXPIRED"):
            print("O Instagram recusou o vídeo:", s)
            sys.exit(1)
    else:
        print("O Instagram não terminou de processar o vídeo em 15 minutos.")
        sys.exit(1)

    p = checar(requests.post(f"{G}/{IG}/media_publish", data={"creation_id": cid, "access_token": TOKEN}, timeout=60))
    mid = p["id"]
    link = checar(requests.get(f"{G}/{mid}", params={"fields": "permalink", "access_token": TOKEN}, timeout=30)).get("permalink", "")
    print("Publicado:", link)
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as o:
        o.write(f"media_id={mid}\npermalink={link}\n")


if __name__ == "__main__":
    main()
