"""
buscar_notion.py — pega no Notion o roteiro do dia (JSON) gerado pela tarefa agendada.

Procura a página "DD/MM/AAAA — 🎬 Notícias" | "— 💡 Curiosidade" | "— 🌎 Mundo",
lê o bloco de código JSON com "cenas" e salva em roteiro.json.

Variáveis: NOTION_TOKEN, MODO (noticias|curiosidade|mundo), DATA (DD/MM/AAAA, opcional = hoje em Brasília)
Saída (GITHUB_OUTPUT): page_id, titulo
Códigos de saída: 0 ok · 3 página ainda não existe · 4 já publicada
"""
import json
import os
import sys
import unicodedata
from datetime import datetime, timedelta, timezone

import requests

API = "https://api.notion.com/v1"
H = {"Authorization": f"Bearer {os.environ['NOTION_TOKEN']}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
MODO = os.environ.get("MODO", "noticias").strip().lower()
DATA = os.environ.get("DATA") or datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y")
CHAVE = {"noticias": "noticias", "curiosidade": "curiosidade", "mundo": "mundo"}[MODO]


def norm(s):
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()


def titulo(p):
    for v in p.get("properties", {}).values():
        if v.get("type") == "title":
            return "".join(t.get("plain_text", "") for t in v["title"])
    return ""


def buscar_paginas():
    achadas, cursor = [], None
    for _ in range(5):
        body = {"query": DATA, "filter": {"property": "object", "value": "page"}, "page_size": 100,
                "sort": {"direction": "descending", "timestamp": "last_edited_time"}}
        if cursor:
            body["start_cursor"] = cursor
        r = requests.post(f"{API}/search", headers=H, json=body, timeout=30)
        r.raise_for_status()
        j = r.json()
        for p in j["results"]:
            t = titulo(p)
            if t.startswith(DATA) and CHAVE in norm(t):
                achadas.append((p["created_time"], p["id"], t))
        if not j.get("has_more"):
            break
        cursor = j["next_cursor"]
    return sorted(achadas, reverse=True)


def blocos(bid, nivel=0):
    cursor = None
    while True:
        url = f"{API}/blocks/{bid}/children?page_size=100" + (f"&start_cursor={cursor}" if cursor else "")
        r = requests.get(url, headers=H, timeout=30)
        r.raise_for_status()
        j = r.json()
        for b in j["results"]:
            yield b
            if b.get("has_children") and nivel < 2 and b["type"] != "child_page":
                yield from blocos(b["id"], nivel + 1)
        if not j.get("has_more"):
            break
        cursor = j["next_cursor"]


def main():
    publicados = set(json.load(open("publicados.json"))) if os.path.exists("publicados.json") else set()
    paginas = buscar_paginas()
    if not paginas:
        print(f"Nenhuma página de {MODO} com data {DATA} ainda.")
        sys.exit(3)
    novas = [p for p in paginas if p[1] not in publicados]
    if not novas:
        print("A página do dia já foi publicada.")
        sys.exit(4)
    _, pid, t = novas[0]
    for b in blocos(pid):
        if b["type"] != "code":
            continue
        texto = "".join(x.get("plain_text", "") for x in b["code"]["rich_text"])
        try:
            rot = json.loads(texto)
        except json.JSONDecodeError:
            continue
        if isinstance(rot, dict) and rot.get("cenas"):
            json.dump(rot, open("roteiro.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            print(f"Roteiro encontrado: {t} ({len(rot['cenas'])} cenas)")
            with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as o:
                o.write(f"page_id={pid}\n")
                o.write(f"titulo={t}\n")
            return
    print(f"A página '{t}' não tem bloco JSON com 'cenas'.")
    sys.exit(1)


if __name__ == "__main__":
    main()
