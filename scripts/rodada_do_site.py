#!/usr/bin/env python3
"""
Monta a rodada do Instagram a partir do site bomdiavarejo.com.br (repo bom-dia-varejo-site):
1 notícia principal por categoria (Varejo, Economia, Política, Mundo), só entre as notícias
que entraram no site desde a rodada anterior.

Lê data/dias/AAAA-MM-DD.json do site: {"data": ..., "noticias": [{titulo, topicos, fonte, link,
categoria, imagem, ...}]}. O site grava as notícias de cada coleta em ordem de relevância
(varejo alimentar pesa mais), então a "principal" de cada categoria é a primeira notícia nova
dela — preferindo a que tem foto.

Uso:
    python rodada_do_site.py                       # lê o JSON de hoje direto do repositório do site
    python rodada_do_site.py --dia data/dias/2026-11-09.json   # arquivo local (teste)
Saída: rodadas/ultima.json (entrada do gera_post_feed.py) e estado_instagram.json (o que já foi visto/postado).
"""
import argparse, datetime, io, json, os, re, unicodedata, urllib.request
from urllib.parse import urljoin

SITE_RAW = os.getenv("SITE_RAW", "https://raw.githubusercontent.com/GuiFonsecaM/bom-dia-varejo-site/main/")
CATEGORIAS = ["Varejo", "Economia", "Política", "Mundo"]
TIPO = {"Varejo": "noticia", "Economia": "noticia", "Política": "noticia", "Mundo": "mundo"}
HASHTAGS = {
    "Varejo": ["#BomDiaVarejo", "#varejo", "#supermercado", "#atacarejo", "#varejoalimentar"],
    "Economia": ["#BomDiaVarejo", "#economia", "#varejo", "#mercado", "#negocios"],
    "Política": ["#BomDiaVarejo", "#politica", "#economia", "#brasil", "#noticias"],
    "Mundo": ["#BomDiaVarejo", "#mundo", "#economiaglobal", "#noticias", "#internacional"],
}
ESTADO = "estado_instagram.json"


def baixa_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (BomDiaVarejo bot)", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def norm(t):
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def chave(n):
    """Mesma ideia do site: domínio + caminho do link original."""
    u = re.sub(r"^https?://(www\.)?", "", str(n.get("link") or "")).split("?")[0].split("#")[0].rstrip("/").lower()
    return u or norm(n.get("titulo"))


def categoria(c):
    c = norm(c)
    if c.startswith(("varejo", "atacarejo")):
        return "Varejo"
    for cat in CATEGORIAS:
        if c.startswith(norm(cat)[:5]):
            return cat
    return None  # Indicadores e outras ficam de fora


# ------------------------------------------------------------ texto
_ESC = r"(?:milhões|milhão|mil|bilhões|bilhão|trilhões|trilhão)"
RE_NUM = re.compile(
    rf"(R\$\s?[\d.,]+(?:\s?{_ESC})?|US\$\s?[\d.,]+(?:\s?{_ESC})?|€\s?[\d.,]+(?:\s?{_ESC})?"
    r"|[\d.,]+\s?%|[\d.,]+\s?(?:p\.p\.|pontos? percentua(?:l|is))"
    rf"|\d[\d.,]*\s(?:{_ESC}|lojas|unidades|anos|meses|empregos|toneladas))", re.I)


def negrita_numeros(t):
    return RE_NUM.sub(lambda m: f"**{m.group(0).strip()}**", t)


def destaque_manchete(t):
    """Trecho laranja da capa: do 1º valor até o fim (se curto); senão depois da última vírgula; senão as 3 últimas palavras."""
    m = RE_NUM.search(t)
    if m:
        if len(t[m.start():].split()) <= 6:
            return t[:m.start()] + "**" + t[m.start():].strip() + "**"
        return t.replace(m.group(0).strip(), f"**{m.group(0).strip()}**", 1)
    if ":" in t:
        a, b = t.split(":", 1)
        if 2 <= len(b.split()) <= 6:
            return f"{a}: **{b.strip()}**"
    if "," in t:
        a, b = t.rsplit(",", 1)
        if 1 <= len(b.split()) <= 7:
            return f"{a}, **{b.strip()}**"
    w = t.split()
    return " ".join(w[:-3]) + " **" + " ".join(w[-3:]) + "**" if len(w) > 4 else t


def corta(t, n):
    t = t.strip()
    if len(t) <= n:
        return t
    pedaco = t[:n]
    for sep in (". ", "; ", " — ", ", "):
        i = pedaco.rfind(sep)
        if i > n * 0.55:
            return pedaco[:i].rstrip(" ,;—") + ("." if sep == ". " else "…")
    return pedaco.rsplit(" ", 1)[0].rstrip(",;:") + "…"


def subtitulo(topico):
    """Linha fina da capa: 1ª frase do 1º tópico, se couber; senão até a última vírgula/travessão antes de 120 caracteres."""
    if not topico:
        return ""
    frase = re.split(r"(?<=[.!?])\s", topico.strip())[0].rstrip(".")
    if len(frase) <= 120:
        return frase
    pedaco = frase[:120]
    for sep in (" — ", "; ", ", "):
        i = pedaco.rfind(sep)
        if i > 50:
            return pedaco[:i]
    return ""


def imagem_absoluta(img):
    if not img:
        return ""
    return img if re.match(r"^https?://", img) else SITE_RAW + img.lstrip("/")


UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Accept-Language": "pt-BR,pt;q=0.9", "Accept": "text/html,application/xhtml+xml,image/avif,image/webp,image/*,*/*;q=0.8"}


def _baixa(url, limite, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(limite), r.geturl()


def imagens_da_pagina(link):
    """(prévias, fotos do corpo) da matéria original: og:image/twitter:image e as <img> grandes do texto."""
    try:
        dados, final = _baixa(link, 2_500_000)
        html = dados.decode("utf-8", "ignore")
    except Exception as e:
        print(f"  ! não abri a matéria {link}: {e}")
        return [], []
    previas = []
    for tag in re.findall(r"<(?:meta|link)\b[^>]*>", html, re.I):
        chave = re.search(r'(?:property|name|itemprop|rel)\s*=\s*["\']([^"\']+)', tag, re.I)
        valor = re.search(r'(?:content|href)\s*=\s*["\']([^"\']+)', tag, re.I)
        if chave and valor and chave.group(1).lower() in (
                "og:image:secure_url", "og:image", "og:image:url", "twitter:image", "twitter:image:src", "image", "image_src"):
            url = urljoin(final, valor.group(1).replace("&amp;", "&").strip())
            if url.startswith("http") and url not in previas:
                previas.append(url)
    corpo = []
    for tag in re.findall(r"<(?:img|source)\b[^>]*>", html, re.I):
        for attr in ("data-src", "data-original", "data-lazy-src", "src", "srcset", "data-srcset"):
            m = re.search(attr + r'\s*=\s*["\']([^"\']+)', tag, re.I)
            if not m:
                continue
            # srcset: pega a última (maior) opção
            url = m.group(1).split(",")[-1].strip().split(" ")[0].replace("&amp;", "&")
            url = urljoin(final, url)
            if (url.startswith("http") and re.search(r"\.(?:jpe?g|png|webp)(?:$|[?/])", url, re.I)
                    and not re.search(r"logo|icon|avatar|sprite|placeholder|banner|selo|badge|emoji|1x1", url, re.I)
                    and url not in corpo and url not in previas):
                corpo.append(url)
            break
    return previas, corpo[:15]


def eh_frame_de_video(url):
    """Capa de vídeo (frame de telejornal, com tarja e logo de TV): fica fora do tema do post."""
    return bool(re.search(r"thumbor\.globoi\.com|video\.glbimg|/videos?/|ytimg\.com|img\.youtube|vimeocdn|jwplatform|brightcove", url, re.I))


def versoes_maiores(url):
    """Tenta chegar no arquivo original por trás de URLs redimensionadas por CDN."""
    out = []
    # Thumbor / Globo (g1, valor, ge): .../AbC=/1200x0/smart/filters:.../i.s3.glbimg.com/v1/.../foto.jpg
    m = re.search(r"/((?:i\.s3\.glbimg\.com|s\d?\.glbimg\.com)/v1/.+)$", url)
    if m:
        out.append("https://" + m.group(1))
    m = re.search(r"/filters:[^/]*/(.+\.(?:jpe?g|png|webp))", url, re.I)
    if m and "." in m.group(1).split("/")[0]:
        out.append("https://" + m.group(1))
    # WordPress: foto-1200x675.jpg → foto.jpg ; foto-scaled.jpg → foto.jpg
    sem_tam = re.sub(r"-(?:\d{2,4}x\d{2,4}|scaled)(?=\.(?:jpe?g|png|webp)(?:\?|$))", "", url, flags=re.I)
    if sem_tam != url:
        out.append(sem_tam)
    # parâmetros de redimensionamento (?w=600&h=..., ?resize=, ?width=)
    if re.search(r"[?&](?:w|h|width|height|resize|fit|quality|q|crop)=", url, re.I):
        out.append(url.split("?")[0])
    return out


def melhor_imagem(n):
    """Foto original da matéria (og:image), na maior resolução.
    Frames de vídeo (telejornal) são descartados; sem foto adequada, a capa sai com o fundo da marca."""
    from PIL import Image
    previas, corpo = imagens_da_pagina(n.get("link", ""))
    so_video = bool(previas) and all(eh_frame_de_video(u) for u in previas)

    def maior(urls, minimo):
        melhor, area = "", 0
        for u in dict.fromkeys(c for x in urls for c in versoes_maiores(x) + [x]):
            if eh_frame_de_video(u):
                continue
            try:
                dados, _ = _baixa(u, 25_000_000)
                w, h = Image.open(io.BytesIO(dados)).size
            except Exception:
                continue
            if w >= minimo and 0.45 <= w / h <= 2.6 and w * h > area:
                melhor, area = u, w * h
                print(f"    foto {w}x{h}: {u[:110]}")
        return melhor

    # fotos do corpo do texto ficam de fora: costumam ser foto de colunista ou miniatura de outra matéria
    escolhida = maior([u for u in previas if not eh_frame_de_video(u)], 400)
    if escolhida:
        return escolhida
    if so_video:
        print("    ! a matéria só tem capa de vídeo: capa sem foto (fundo da marca)")
        return ""
    reserva = imagem_absoluta(n.get("imagem"))
    if reserva:
        print("    ! usando a cópia reduzida do site (a matéria não deu acesso à foto original)")
    return reserva


def monta_post(n, cat, data_iso):
    titulo = re.sub(r"\s+", " ", n["titulo"]).strip()
    tops = [re.sub(r"\s+", " ", str(t)).strip(" •-") for t in (n.get("topicos") or []) if str(t).strip()]
    tops = [corta(t, 330) for t in tops]
    # até 3 tópicos por imagem e ~560 caracteres, no máx. 4 imagens internas (carrossel com até 5)
    grupos, atual = [], []
    for t in tops:
        if atual and (len(atual) == 3 or sum(map(len, atual)) + len(t) > 560):
            grupos.append(atual)
            atual = []
        atual.append(t)
    if atual:
        grupos.append(atual)
    nomes = ["O que aconteceu", "Mais detalhes", "Contexto", "O que vem agora"]
    slides = [{"titulo": nomes[i], "topicos": [negrita_numeros(t) for t in g]} for i, g in enumerate(grupos[:4])]
    img = melhor_imagem(n)
    d = datetime.date.fromisoformat(data_iso).strftime("%d/%m/%Y") if data_iso else ""
    return {
        "tipo": TIPO[cat],
        "categoria": cat,
        "manchete": destaque_manchete(titulo),
        "subtitulo": subtitulo(tops[0] if tops else ""),
        "imagem": img,
        "fonte": n.get("fonte") or re.sub(r"^https?://(www\.)?", "", n.get("link", "")).split("/")[0],
        "data": d,
        "link": n.get("link", ""),
        "materia": "",
        "slides": slides,
        "hashtags": HASHTAGS[cat],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dia", help="arquivo local do dia (padrão: baixa o de hoje do site)")
    ap.add_argument("--saida", default="rodadas/ultima.json")
    ap.add_argument("--estado", default=ESTADO)
    a = ap.parse_args()

    hoje = datetime.date.today().isoformat()  # o workflow roda com TZ=America/Sao_Paulo
    if a.dia:
        with open(a.dia, encoding="utf-8") as fh:
            dia = json.load(fh)
    else:
        try:
            dia = baixa_json(f"{SITE_RAW}data/dias/{hoje}.json")
        except Exception as e:
            print(f"Sem edição de hoje no site ({e}).")
            dia = {"data": hoje, "noticias": []}

    estado = {"vistos": [], "postados": []}
    if os.path.exists(a.estado):
        with open(a.estado, encoding="utf-8") as fh:
            estado.update(json.load(fh))
    vistos = set(estado["vistos"])
    ja_postados = {p["chave"] for p in estado["postados"]}

    novas = {c: [] for c in CATEGORIAS}
    for n in dia.get("noticias", []):
        cat = categoria(n.get("categoria"))
        k = chave(n)
        if cat and n.get("titulo") and k not in vistos and k not in ja_postados:
            novas[cat].append(n)

    posts = []
    agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    ordem = {chave(n): i for i, n in enumerate(dia.get("noticias", []))}
    escolhidas = []
    for cat in CATEGORIAS:
        if not novas[cat]:
            print(f"– {cat}: nenhuma notícia nova desde a última rodada")
            continue
        com_foto = [n for n in novas[cat] if n.get("imagem")]
        n = (com_foto or novas[cat])[0]  # ordem do site = relevância
        post = monta_post(n, cat, dia.get("data") or hoje)
        post["feed"] = False
        escolhidas.append((ordem.get(chave(n), 9999), post, n))
        print(f"✓ {cat}: {n['titulo']}")

    # 1 carrossel por rodada: Varejo, se houver notícia nova; senão a mais relevante segundo o site
    # (o site grava cada coleta em ordem de relevância), de preferência com foto. As 4 vão para os stories.
    if escolhidas:
        ordenadas = sorted(escolhidas, key=lambda x: (x[1]["categoria"] != "Varejo", x[0]))  # Varejo tem prioridade
        principal = next((x for x in ordenadas if x[1]["imagem"]), ordenadas[0])
        principal[1]["feed"] = True
        print(f"★ Feed: [{principal[1]['categoria']}] {principal[2]['titulo']}")
        # carrossel primeiro, depois os stories das outras
        for _, post, n in [principal] + [x for x in ordenadas if x is not principal]:
            posts.append(post)
            estado["postados"].append({"chave": chave(n), "categoria": post["categoria"], "titulo": n["titulo"],
                                       "em": agora, "feed": post["feed"]})

    # tudo o que já está no site conta como visto: a próxima rodada só olha o que entrar depois
    estado["vistos"] = (estado["vistos"] + [chave(n) for n in dia.get("noticias", []) if chave(n) not in vistos])[-3000:]
    estado["postados"] = estado["postados"][-1000:]

    os.makedirs(os.path.dirname(a.saida) or ".", exist_ok=True)
    with open(a.saida, "w", encoding="utf-8") as fh:
        json.dump({"posts": posts}, fh, ensure_ascii=False, indent=2)
    with open(a.estado, "w", encoding="utf-8") as fh:
        json.dump(estado, fh, ensure_ascii=False, indent=1)
    print(f"{sum(p['feed'] for p in posts)} carrossel + {len(posts)} stories nesta rodada.")


if __name__ == "__main__":
    main()
