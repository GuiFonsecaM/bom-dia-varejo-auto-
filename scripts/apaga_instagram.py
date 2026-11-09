#!/usr/bin/env python3
"""
Apaga publicações do Instagram pelo id (post, carrossel ou story).
Uso: python scripts/apaga_instagram.py 1822102609036 1807919091872 ...
Variáveis: IG_TOKEN (ou IG_ACCESS_TOKEN), IG_GRAPH_HOST, IG_API_VERSION — as mesmas do publica_instagram.py.
"""
import os, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from publica_instagram import GRAPH, TOKEN_ENV, _req

falhas = 0
for mid in [x.strip() for a in sys.argv[1:] for x in a.split(",") if x.strip()]:
    q = urllib.parse.urlencode({"access_token": os.environ[TOKEN_ENV]})
    try:
        r = _req("DELETE", f"{GRAPH}/{mid}?{q}")
        print(f"✓ apagado {mid}: {r}")
    except Exception as e:
        falhas += 1
        print(f"✗ não apagou {mid}: {e}")
sys.exit(1 if falhas else 0)
