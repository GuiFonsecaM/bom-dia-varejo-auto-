#!/usr/bin/env python3
"""
Refaz um post da última rodada (rodadas/ultima.json) buscando a foto de novo com as regras atuais.
Uso: python scripts/refaz_post.py Política [--saida rodadas/refazer.json]
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rodada_do_site import melhor_imagem, norm

ap = argparse.ArgumentParser()
ap.add_argument("categoria")
ap.add_argument("--rodada", default="rodadas/ultima.json")
ap.add_argument("--saida", default="rodadas/refazer.json")
a = ap.parse_args()

with open(a.rodada, encoding="utf-8") as fh:
    posts = json.load(fh)["posts"]
alvo = [p for p in posts if norm(p.get("categoria")) == norm(a.categoria)]
if not alvo:
    sys.exit(f"Categoria {a.categoria!r} não está na última rodada: {[p.get('categoria') for p in posts]}")
post = alvo[0]
print(f"Refazendo: {post['manchete']}")
post["imagem"] = melhor_imagem({"link": post["link"]})
with open(a.saida, "w", encoding="utf-8") as fh:
    json.dump({"posts": [post]}, fh, ensure_ascii=False, indent=2)
