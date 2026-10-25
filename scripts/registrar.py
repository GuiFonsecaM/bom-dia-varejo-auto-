"""
registrar.py — marca a página como publicada: guarda o id em publicados.json e escreve o link no Notion.
Variáveis: NOTION_TOKEN, PAGE_ID, PERMALINK
"""
import json
import os
from datetime import datetime, timedelta, timezone

import requests

pid = os.environ["PAGE_ID"]
link = os.environ.get("PERMALINK", "")
agora = datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y %H:%M")

lista = json.load(open("publicados.json")) if os.path.exists("publicados.json") else []
if pid not in lista:
    lista.append(pid)
json.dump(lista[-300:], open("publicados.json", "w"), indent=2)

texto = [{"type": "text", "text": {"content": f"✅ Publicado no Instagram em {agora} (Brasília). "}}]
if link:
    texto.append({"type": "text", "text": {"content": "Ver o post", "link": {"url": link}}})
r = requests.patch(
    f"https://api.notion.com/v1/blocks/{pid}/children",
    headers={"Authorization": f"Bearer {os.environ['NOTION_TOKEN']}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"},
    json={"children": [{"object": "block", "type": "callout", "callout": {"rich_text": texto, "icon": {"type": "emoji", "emoji": "📲"}}}]},
    timeout=30,
)
print("Notion:", r.status_code)
