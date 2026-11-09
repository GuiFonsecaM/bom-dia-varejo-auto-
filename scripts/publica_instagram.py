#!/usr/bin/env python3
"""
Publica no Instagram (API oficial de publicação de conteúdo) o que o gera_post_feed.py gerou:
  1) carrossel do feed com a legenda (manchete + matéria + tópicos + link da fonte)
  2) logo em seguida, o story da mesma notícia

Variáveis de ambiente (GitHub Secrets):
  IG_USER_ID        id da conta profissional do Instagram
  IG_TOKEN          token de longa duração (o mesmo que o token.yml renova a cada 15 dias)
  IG_GRAPH_HOST     graph.instagram.com (login via Instagram, padrão) ou graph.facebook.com
  IG_API_VERSION    padrão v24.0

Hospedagem das imagens (a API só aceita URL pública):
  PUBLIC_BASE_URL   se você já hospeda mídia (ex.: a mesma usada para os Reels), as imagens devem estar em
                    PUBLIC_BASE_URL/<pasta>/<arquivo>
  — ou —
  GITHUB_TOKEN + GITHUB_REPOSITORY (já existem no Actions): sobe as imagens para o branch "midia" do
                    próprio repositório e usa o link raw (o repositório precisa ser público).

Uso avulso:  python publica_instagram.py saida/<pasta_do_post>
"""
import base64, json, os, sys, time, urllib.parse, urllib.request

GRAPH = f"https://{os.getenv('IG_GRAPH_HOST', 'graph.instagram.com')}/{os.getenv('IG_API_VERSION', 'v24.0')}"
TOKEN_ENV = "IG_TOKEN" if os.getenv("IG_TOKEN") else "IG_ACCESS_TOKEN"


def _req(metodo, url, dados=None, headers=None):
    corpo = None
    if dados is not None:
        if isinstance(dados, (bytes, str)):
            corpo = dados.encode() if isinstance(dados, str) else dados
        else:
            corpo = urllib.parse.urlencode(dados).encode()
    req = urllib.request.Request(url, data=corpo, method=metodo, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{metodo} {url.split('?')[0]} → {e.code}: {e.read().decode(errors='ignore')}") from None


# ------------------------------------------------------------ hospedagem
def _gh(metodo, caminho, dados=None):
    h = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json",
         "Content-Type": "application/json"}
    return _req(metodo, f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}{caminho}",
                json.dumps(dados) if dados is not None else None, h)


def _garante_branch(nome="midia"):
    try:
        _gh("GET", f"/git/ref/heads/{nome}")
    except RuntimeError:
        padrao = _gh("GET", "")["default_branch"]
        sha = _gh("GET", f"/git/ref/heads/{padrao}")["object"]["sha"]
        _gh("POST", "/git/refs", {"ref": f"refs/heads/{nome}", "sha": sha})


def url_publica(caminho_local):
    pasta = os.path.basename(os.path.dirname(caminho_local))
    arq = os.path.basename(caminho_local)
    if os.getenv("PUBLIC_BASE_URL"):
        return f"{os.environ['PUBLIC_BASE_URL'].rstrip('/')}/{pasta}/{arq}"
    if os.getenv("GITHUB_TOKEN") and os.getenv("GITHUB_REPOSITORY"):
        _garante_branch()
        destino = f"posts/{pasta}/{arq}"
        with open(caminho_local, "rb") as fh:
            conteudo = base64.b64encode(fh.read()).decode()
        dados = {"message": f"mídia {pasta}/{arq}", "content": conteudo, "branch": "midia"}
        try:
            dados["sha"] = _gh("GET", f"/contents/{urllib.parse.quote(destino)}?ref=midia")["sha"]
        except RuntimeError:
            pass
        _gh("PUT", f"/contents/{urllib.parse.quote(destino)}", dados)
        return f"https://raw.githubusercontent.com/{os.environ['GITHUB_REPOSITORY']}/midia/{urllib.parse.quote(destino)}"
    raise RuntimeError("Defina PUBLIC_BASE_URL ou rode no GitHub Actions (GITHUB_TOKEN + GITHUB_REPOSITORY).")


# ------------------------------------------------------------ Instagram
def _ig(caminho, dados):
    dados = dict(dados, access_token=os.environ[TOKEN_ENV])
    return _req("POST", f"{GRAPH}/{caminho}", dados)


def _espera(container_id, limite=180):
    t0 = time.time()
    while time.time() - t0 < limite:
        q = urllib.parse.urlencode({"fields": "status_code", "access_token": os.environ[TOKEN_ENV]})
        st = _req("GET", f"{GRAPH}/{container_id}?{q}").get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"container {container_id} com status {st}")
        time.sleep(4)
    raise RuntimeError(f"container {container_id} não ficou pronto a tempo")


def _publica(container_id):
    _espera(container_id)
    return _ig(f"{os.environ['IG_USER_ID']}/media_publish", {"creation_id": container_id})["id"]


def publica_carrossel(urls, legenda):
    uid = os.environ["IG_USER_ID"]
    if len(urls) == 1:
        c = _ig(f"{uid}/media", {"image_url": urls[0], "caption": legenda})["id"]
        return _publica(c)
    filhos = []
    for u in urls[:10]:
        fid = _ig(f"{uid}/media", {"image_url": u, "is_carousel_item": "true"})["id"]
        _espera(fid)
        filhos.append(fid)
    c = _ig(f"{uid}/media", {"media_type": "CAROUSEL", "children": ",".join(filhos), "caption": legenda})["id"]
    return _publica(c)


def publica_story(url):
    c = _ig(f"{os.environ['IG_USER_ID']}/media", {"image_url": url, "media_type": "STORIES"})["id"]
    return _publica(c)


def publica_pasta(pasta):
    with open(os.path.join(pasta, "post.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    pid = None
    if meta.get("feed"):  # só a notícia principal da rodada vai para o feed
        urls = [url_publica(os.path.join(pasta, a)) for a in meta["feed"]]
        pid = publica_carrossel(urls, meta["legenda"])
        print(f"  ✓ carrossel publicado (id {pid})")
    sid = publica_story(url_publica(os.path.join(pasta, meta["story"])))
    print(f"  ✓ story publicado (id {sid})")
    meta["publicado"] = {"feed_id": pid, "story_id": sid, "em": time.strftime("%Y-%m-%d %H:%M:%S")}
    with open(os.path.join(pasta, "post.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        publica_pasta(p)
