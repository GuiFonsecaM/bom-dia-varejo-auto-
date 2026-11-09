#!/usr/bin/env python3
"""
Bom dia varejo — gerador de posts do feed (carrossel) + story por notícia.

Uso:
    python gera_post_feed.py rodada.json                 # só gera as imagens e a legenda
    python gera_post_feed.py rodada.json --publicar      # gera e publica (carrossel + story)

O JSON pode ser um post único, uma lista de posts ou {"posts": [...]}.
Campos de cada post:
    tipo        "noticia" | "curiosidade" | "mundo"          (vai no nome dos arquivos)
    manchete    texto da capa; trechos entre **asteriscos** saem em laranja
    subtitulo   linha menor abaixo da manchete (capa)
    imagem      URL ou caminho da foto puxada na rodada
    fonte       nome do veículo (ex.: "Giro News")
    data        data da matéria (ex.: "07/10/2026 (atualizada em 08/10/2026)")
    link        URL original da notícia
    materia     texto corrido da matéria para a legenda (parágrafos separados por linha em branco)
    slides      [{"titulo": "...", "topicos": ["...", "..."]}]  — até 4 (carrossel máx. 5 imagens);
                trechos entre **asteriscos** saem em negrito
    hashtags    lista opcional; se vazia usa as padrão

Saída: saida/<data>_<tipo>_<nn>_<slug>/  com  feed_01_capa.jpg … feed_0N.jpg, story.jpg (JPEG: único formato aceito pela API), legenda.txt, post.json
"""
import argparse, io, json, os, re, sys, unicodedata, datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

BASE = os.path.dirname(os.path.abspath(__file__))
ASSETS = next((p for p in (os.path.join(BASE, "assets"), os.path.join(BASE, "..", "assets")) if os.path.isdir(p)), os.path.join(BASE, "assets"))

# ---------------------------------------------------------------- cores
LARANJA = (247, 118, 0)
FUNDO_CLARO = (237, 237, 237)
TEXTO_ESCURO = (26, 26, 26)
CINZA_FONTE = (138, 138, 138)
BRANCO = (255, 255, 255)
PRETO = (0, 0, 0)

FEED_W, FEED_H = 1080, 1350
STORY_W, STORY_H = 1080, 1920
HASHTAGS_PADRAO = ["#BomDiaVarejo", "#varejo", "#supermercado", "#atacarejo", "#noticias", "#economia"]

# ---------------------------------------------------------------- fontes
# Usa Segoe UI se os .ttf estiverem em assets/ (ou no Windows); senão Open Sans (variável).
_SEGOE = {400: "segoeui.ttf", 600: "seguisb.ttf", 700: "segoeuib.ttf", 800: "segoeuib.ttf", 900: "seguibl.ttf"}
_cache = {}


def fonte(peso, tam):
    chave = (peso, tam)
    if chave in _cache:
        return _cache[chave]
    for pasta in (ASSETS, r"C:\Windows\Fonts"):
        p = os.path.join(pasta, _SEGOE.get(peso, "segoeui.ttf"))
        if os.path.exists(p):
            f = ImageFont.truetype(p, tam)
            _cache[chave] = f
            return f
    f = ImageFont.truetype(os.path.join(ASSETS, "OpenSans.ttf"), tam)
    try:
        f.set_variation_by_axes([min(max(peso, 300), 800), 100])
    except Exception:
        pass
    _cache[chave] = f
    return f


def larg(f, t):
    return f.getlength(t)


# ---------------------------------------------------------------- texto rico (**destaque**)
# caracteres que a fonte pode não ter (hífen inseparável etc.) → equivalentes comuns
_TROCAS = {0x2011: "-", 0x2010: "-", 0x2012: "–", 0x00AD: "", 0x2009: " ", 0x202F: " ", 0x00A0: " ", 0x2060: ""}


def tokens(texto):
    """Quebra '... **x y** ...' em [(palavra, destaque, colada)]; colada = sem espaço antes (ex.: '2,5%' + '.')."""
    out, fim_com_espaco = [], True
    texto = (texto or "").translate(_TROCAS)
    for i, parte in enumerate(re.split(r"\*\*", texto)):
        if not parte:
            continue
        for j, w in enumerate(parte.split()):
            cola = j == 0 and bool(out) and not fim_com_espaco and not parte[0].isspace()
            out.append((w, i % 2 == 1, cola))
        fim_com_espaco = parte[-1].isspace()
    return out


def corta_txt(t, n):
    t = (t or "").strip()
    if len(limpa(t)) <= n:
        return t
    pedaco = t[:n]
    for sep in (". ", "; ", " — ", ", "):
        i = pedaco.rfind(sep)
        if i > n * 0.5:
            out = pedaco[:i]
            break
    else:
        out = pedaco.rsplit(" ", 1)[0]
    if out.count("**") % 2:
        out += "**"
    return out.rstrip(" ,;—") + "…"


def limpa(texto):
    return re.sub(r"\*\*", "", texto or "").strip()


def quebra(toks, f_norm, f_dest, largura):
    """Agrupa tokens colados (ex.: '2,5%' + '.') para não quebrarem separados, depois quebra em linhas."""
    grupos = []
    for t in toks:
        if t[2] and grupos:
            grupos[-1].append(t)
        else:
            grupos.append([t])
    esp = larg(f_norm, " ")
    linhas, atual, w_atual = [], [], 0
    for g in grupos:
        lw = sum(larg(f_dest if d else f_norm, w) for w, d, _ in g)
        extra = lw if not atual else esp + lw
        if atual and w_atual + extra > largura:
            linhas.append(atual)
            atual, w_atual = list(g), lw
        else:
            atual += g
            w_atual += extra
    if atual:
        linhas.append(atual)
    return linhas


def larg_linha(linha, f_norm, f_dest):
    esp = larg(f_norm, " ")
    return sum(larg(f_dest if d else f_norm, w) + (0 if (c or i == 0) else esp) for i, (w, d, c) in enumerate(linha))


def desenha_linha(draw, linha, x, y, f_norm, f_dest, cor, cor_dest):
    esp = larg(f_norm, " ")
    for i, (w, d, c) in enumerate(linha):
        if i and not c:
            x += esp
        f = f_dest if d else f_norm
        draw.text((x, y), w, font=f, fill=cor_dest if d else cor)
        x += larg(f, w)


# ---------------------------------------------------------------- logo
def logo(diam):
    for nome in ("logo.png", "logo_bom_dia_varejo.png"):
        p = os.path.join(ASSETS, nome)
        if os.path.exists(p):
            im = Image.open(p).convert("RGBA").resize((diam, diam), Image.LANCZOS)
            m = Image.new("L", (diam, diam), 0)
            ImageDraw.Draw(m).ellipse((0, 0, diam - 1, diam - 1), fill=255)
            im.putalpha(Image.composite(im.getchannel("A"), m, m))
            return im
    # desenho vetorial: círculo preto, carrinho branco, meio sol laranja dentro
    s = 8
    D = diam * s
    im = Image.new("RGBA", (D, D), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((0, 0, D - 1, D - 1), fill=(0, 0, 0, 255))
    u = D / 100.0
    lw = max(1, int(5.2 * u))
    # meio sol
    cx, cy, r = 52 * u, 58 * u, 12 * u
    d.pieslice((cx - r, cy - r, cx + r, cy + r), 180, 360, fill=LARANJA + (255,))
    # alça + cesto
    d.line([(20 * u, 33 * u), (29 * u, 33 * u), (35 * u, 60 * u)], fill=BRANCO, width=lw, joint="curve")
    d.line([(31 * u, 42 * u), (75 * u, 42 * u), (70 * u, 60 * u), (35 * u, 60 * u)], fill=BRANCO, width=lw, joint="curve")
    d.line([(35 * u, 60 * u), (37 * u, 67 * u), (71 * u, 67 * u)], fill=BRANCO, width=lw, joint="curve")
    for rx in (41, 66):
        rr = 4.6 * u
        d.ellipse((rx * u - rr, 75 * u - rr, rx * u + rr, 75 * u + rr), fill=BRANCO)
    return im.resize((diam, diam), Image.LANCZOS)


# ---------------------------------------------------------------- imagem da rodada
def carrega_imagem(ref):
    if not ref:
        return None
    try:
        if re.match(r"^https?://", ref):
            import urllib.request
            req = urllib.request.Request(ref, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36", "Accept": "image/avif,image/webp,image/*,*/*;q=0.8"})
            with urllib.request.urlopen(req, timeout=40) as r:
                img = Image.open(io.BytesIO(r.read()))
                img = ImageOps.exif_transpose(img)
                return img.convert("RGB")
        p = ref if os.path.isabs(ref) else os.path.join(os.getcwd(), ref)
        return Image.open(p).convert("RGB")
    except Exception as e:
        print(f"  ! não consegui abrir a imagem {ref!r}: {e}", file=sys.stderr)
        return None


def cobre(img, w, h, foco_y=0.45):
    """Recorta/escala para preencher w×h (object-fit: cover)."""
    iw, ih = img.size
    esc = max(w / iw, h / ih)
    nw, nh = int(iw * esc + 0.5), int(ih * esc + 0.5)
    img = img.resize((nw, nh), Image.LANCZOS)
    x = (nw - w) // 2
    y = int(max(0, min(nh - h, (nh - h) * foco_y)))
    return img.crop((x, y, x + w, y + h))


def fundo_sem_foto(w, h):
    im = Image.new("RGB", (w, h), (18, 18, 18))
    d = ImageDraw.Draw(im)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)], fill=(int(40 - 30 * t), int(30 - 22 * t), int(20 - 16 * t)))
    return im


def gradiente_vertical(w, h, paradas):
    """paradas: [(y_rel, alpha 0-255), ...] → máscara L."""
    m = Image.new("L", (1, h))
    for y in range(h):
        t = y / (h - 1)
        for (t0, a0), (t1, a1) in zip(paradas, paradas[1:]):
            if t0 <= t <= t1:
                k = 0 if t1 == t0 else (t - t0) / (t1 - t0)
                k = k * k * (3 - 2 * k)
                m.putpixel((0, y), int(a0 + (a1 - a0) * k))
                break
    return m.resize((w, h))


# ---------------------------------------------------------------- FEED: capa
def feed_capa(post):
    W, H = FEED_W, FEED_H
    foto = carrega_imagem(post.get("imagem"))
    base = cobre(foto, W, H) if foto else fundo_sem_foto(W, H)
    preto = Image.new("RGB", (W, H), PRETO)
    base = Image.composite(preto, base, gradiente_vertical(W, H, [(0, 120), (0.16, 0), (0.38, 0), (0.62, 225), (0.78, 245), (1, 250)]))
    d = ImageDraw.Draw(base)

    # marca no topo, centralizada
    lg = 62
    f_marca = fonte(700, 37)
    txt = "Bom dia varejo"
    tw = larg(f_marca, txt)
    x0 = int((W - (lg + 18 + tw)) / 2)
    lg_img = logo(lg)
    base.paste(lg_img, (x0, 63), lg_img)
    d.text((x0 + lg + 18, 63 + lg / 2), txt, font=f_marca, fill=BRANCO, anchor="lm")

    # rodapé: linha com seta + ARRASTE PARA O LADO
    mx = 74
    y_seta = 1253
    d.line([(mx, y_seta), (W - mx, y_seta)], fill=BRANCO, width=3)
    d.line([(W - mx - 22, y_seta - 13), (W - mx, y_seta), (W - mx - 22, y_seta + 13)], fill=BRANCO, width=3, joint="curve")
    f_cta = fonte(700, 21)
    d.text((mx, y_seta + 22), "ARRASTE PARA O LADO", font=f_cta, fill=BRANCO)

    # subtítulo (de baixo para cima)
    largura = W - 2 * mx
    y_base = y_seta - 52
    sub = limpa(post.get("subtitulo", ""))
    if sub:
        f_sub = fonte(400, 31)
        l_sub = quebra(tokens(sub), f_sub, f_sub, largura)[:2]
        lh = 42
        y_base -= lh * len(l_sub)
        for i, ln in enumerate(l_sub):
            wl = larg_linha(ln, f_sub, f_sub)
            desenha_linha(d, ln, (W - wl) / 2, y_base + i * lh, f_sub, f_sub, BRANCO, BRANCO)
        y_base -= 26

    # manchete com destaque laranja, auto-ajuste
    tam = 70
    while True:
        f_m = fonte(700, tam)
        linhas = quebra(tokens(post["manchete"]), f_m, f_m, largura)
        if len(linhas) <= 4 or tam <= 48:
            break
        tam -= 3
    lh = int(tam * 1.2)
    y_top = y_base - lh * len(linhas)
    for i, ln in enumerate(linhas):
        wl = larg_linha(ln, f_m, f_m)
        desenha_linha(d, ln, (W - wl) / 2, y_top + i * lh, f_m, f_m, BRANCO, LARANJA)
    return base


# ---------------------------------------------------------------- FEED: slides internos
def selo_marca(img, x_dir, y, escala=1.0):
    """Pílula com logo + 'Bom dia\\nvarejo' (canto superior direito)."""
    d = ImageDraw.Draw(img)
    f = fonte(700, int(27 * escala))
    lg = int(88 * escala)
    tw = max(larg(f, "Bom dia"), larg(f, "varejo"))
    h = lg + int(22 * escala)
    w = int(10 * escala + lg + 16 * escala + tw + 30 * escala)
    x0 = x_dir - w
    d.rounded_rectangle((x0, y, x_dir, y + h), radius=h // 2, fill=(242, 242, 242), outline=(212, 212, 212), width=3)
    ly = y + (h - lg) // 2
    li = logo(lg)
    img.paste(li, (x0 + int(11 * escala), ly), li)
    tx = x0 + int(11 * escala) + lg + int(16 * escala)
    d.text((tx, y + h / 2 - 2), "Bom dia", font=f, fill=(74, 74, 74), anchor="ld")
    d.text((tx, y + h / 2 + 2), "varejo", font=f, fill=(74, 74, 74), anchor="lt")


INT_MX, INT_XTXT, INT_Y0, INT_YLIM = 112, 151, 268, 1215


def layout_interno(slide, tam):
    W = FEED_W
    largura = W - INT_XTXT - 130
    f_t = fonte(700, int(tam * 1.22))
    f_n, f_b = fonte(400, tam), fonte(700, tam)
    lh, gap = int(tam * 1.36), int(tam * 0.8)
    titulo = limpa(slide.get("titulo", ""))
    l_tit = quebra(tokens(titulo), f_t, f_t, W - 2 * INT_MX) if titulo else []
    blocos = [quebra(tokens(t), f_n, f_b, largura) for t in slide.get("topicos", [])]
    h = len(l_tit) * int(f_t.size * 1.25) + (40 if l_tit else 0)
    h += sum(len(b) * lh for b in blocos) + gap * max(0, len(blocos) - 1)
    cabe = INT_Y0 + h + 70 <= INT_YLIM
    return cabe, f_t, f_n, f_b, lh, gap, l_tit, blocos


def tam_que_cabe(slide):
    for tam in range(46, 27, -2):
        if layout_interno(slide, tam)[0]:
            return tam
    return 28


def feed_interno(post, slide, tam=None):
    """tam: tamanho de fonte único para todos os slides do post (gera() passa o menor que serve em todos)."""
    W, H = FEED_W, FEED_H
    img = Image.new("RGB", (W, H), FUNDO_CLARO)
    d = ImageDraw.Draw(img)
    selo_marca(img, W - 72, 74)

    # barra laranja inferior esquerda com corte diagonal
    d.polygon([(0, 1253), (600, 1253), (692, H), (0, H)], fill=LARANJA)

    mx, x_txt = INT_MX, INT_XTXT
    fonte_txt = f"Fonte: {post.get('fonte', '')}" + (f", {post['data']}" if post.get("data") else "")
    tam = tam or tam_que_cabe(slide)
    _, f_t, f_n, f_b, lh, gap, l_tit, blocos = layout_interno(slide, tam)

    y = INT_Y0
    for ln in l_tit:
        desenha_linha(d, ln, mx, y, f_t, f_t, TEXTO_ESCURO, TEXTO_ESCURO)
        y += int(f_t.size * 1.25)
    if l_tit:
        y += 40
    r = max(5, int(tam * 0.15))
    for b in blocos:
        cy = y + lh * 0.52
        d.ellipse((mx + 4 - r, cy - r, mx + 4 + r, cy + r), fill=LARANJA)
        for ln in b:
            desenha_linha(d, ln, x_txt, y, f_n, f_b, TEXTO_ESCURO, TEXTO_ESCURO)
            y += lh
        y += gap
    y += 22
    if post.get("fonte"):
        d.text((mx, y), fonte_txt, font=fonte(400, 22), fill=CINZA_FONTE)
    return img


# ---------------------------------------------------------------- STORY
def story(post):
    W, H = STORY_W, STORY_H
    img = Image.new("RGB", (W, H), (10, 10, 10))
    d = ImageDraw.Draw(img)

    # barra branca abaixo dos indicadores do stories
    y_bar, h_bar = 128, 132
    d.rectangle((0, y_bar, W, y_bar + h_bar), fill=BRANCO)
    lg = 88
    li = logo(lg)
    img.paste(li, (64, y_bar + (h_bar - lg) // 2), li)
    d.text((64 + lg + 22, y_bar + h_bar / 2), "Bom dia varejo", font=fonte(700, 44), fill=(20, 20, 20), anchor="lm")

    mx = 72
    largura = W - 2 * mx
    y = y_bar + h_bar + 70
    rotulo = (post.get("categoria") or {"noticia": "NOTÍCIA", "curiosidade": "CURIOSIDADE", "mundo": "MUNDO"}.get(post.get("tipo", "noticia"), "NOTÍCIA")).upper()
    f_rot = fonte(700, 30)
    d.rounded_rectangle((mx, y, mx + larg(f_rot, rotulo) + 40, y + 52), radius=8, fill=LARANJA)
    d.text((mx + 20, y + 26), rotulo, font=f_rot, fill=BRANCO, anchor="lm")
    y += 52 + 40

    # manchete
    tam = 76
    while True:
        f_m = fonte(700, tam)
        linhas = quebra(tokens(post["manchete"]), f_m, f_m, largura)
        if len(linhas) <= 5 or tam <= 54:
            break
        tam -= 3
    lh = int(tam * 1.18)
    for ln in linhas:
        desenha_linha(d, ln, mx, y, f_m, f_m, BRANCO, LARANJA)
        y += lh
    y += 30

    # tópicos (texto pequeno) — até 3, do 1º slide
    f_n, f_b = fonte(400, 36), fonte(700, 36)
    lh_t = 50
    tops = [corta_txt(t, 150) for t in (post.get("slides") or [{}])[0].get("topicos", [])[:2]]
    if not tops and post.get("subtitulo"):
        tops = [post["subtitulo"]]
    y_cta = 1560  # área segura: nada abaixo de ~1670
    foto = carrega_imagem(post.get("imagem"))
    reserva = 470 if foto else 60  # espaço mínimo para a foto
    for t in tops:
        b = quebra(tokens(t), f_n, f_b, largura - 40)
        if y + len(b) * lh_t > y_cta - reserva:
            break
        cy = y + lh_t * 0.52
        d.ellipse((mx + 2, cy - 6, mx + 14, cy + 6), fill=LARANJA)
        for ln in b:
            desenha_linha(d, ln, mx + 40, y, f_n, f_b, (225, 225, 225), BRANCO)
            y += lh_t
        y += 18

    # foto da rodada no espaço que sobrar
    y += 20
    h_foto = min(620, y_cta - 50 - y)
    if foto and h_foto >= 300:
        f = cobre(foto, largura, h_foto, foco_y=0.4)
        m = Image.new("L", f.size, 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, f.size[0] - 1, f.size[1] - 1), radius=26, fill=255)
        img.paste(f, (mx, y), m)

    # chamada para o post + fonte
    f_cta = fonte(700, 38)
    cta = "Matéria completa no post do feed"
    wc = larg(f_cta, cta) + 160
    xc = (W - wc) / 2
    d.rounded_rectangle((xc, y_cta, xc + wc, y_cta + 92), radius=46, fill=LARANJA)
    d.text((xc + 50, y_cta + 46), cta, font=f_cta, fill=BRANCO, anchor="lm")
    xa = xc + wc - 48
    d.line([(xa - 16, y_cta + 30), (xa, y_cta + 46), (xa - 16, y_cta + 62)], fill=BRANCO, width=5, joint="curve")
    dominio = re.sub(r"^https?://(www\.)?", "", post.get("link", "")).split("/")[0]
    rod = "Fonte: " + post.get("fonte", "") + (f" · {dominio}" if dominio else "")
    d.text((W / 2, y_cta + 130), rod, font=fonte(400, 28), fill=(170, 170, 170), anchor="mm")
    return img


# ---------------------------------------------------------------- legenda
def legenda(post):
    emoji = {"noticia": "📰", "curiosidade": "💡", "mundo": "🌎"}.get(post.get("tipo", "noticia"), "📰")
    partes = [f"{emoji} {limpa(post['manchete'])}"]
    primeiro = limpa(((post.get("slides") or [{}])[0].get("topicos") or [""])[0])
    if post.get("subtitulo") and limpa(post["subtitulo"]).rstrip(".…") not in primeiro:
        partes.append(limpa(post["subtitulo"]))
    if post.get("materia"):
        partes.append("\n\n".join(p.strip() for p in limpa(post["materia"]).split("\n\n") if p.strip()))
    for s in post.get("slides", []):
        bloco = [f"📌 {limpa(s.get('titulo', ''))}"] if s.get("titulo") else []
        bloco += [f"• {limpa(t)}" for t in s.get("topicos", [])]
        if bloco:
            partes.append("\n".join(bloco))
    fonte_ln = f"🔗 Fonte: {post.get('fonte', '')}" + (f", {post['data']}" if post.get("data") else "")
    if post.get("link"):
        fonte_ln += f"\n{post['link']}"
    rodape = [fonte_ln, " ".join(post.get("hashtags") or HASHTAGS_PADRAO)]
    # limite do Instagram: 2.200 caracteres. Corta tópicos do fim, nunca a fonte, o link ou as hashtags.
    while len("\n\n".join(partes + rodape)) > 2200 and len(partes) > 1:
        linhas = partes[-1].split("\n")
        partes[-1] = "\n".join(linhas[:-1])
        if len(linhas) <= 2:
            partes.pop()
    return "\n\n".join(partes + rodape)[:2200]


# ---------------------------------------------------------------- orquestração
def slug(t, n=40):
    t = unicodedata.normalize("NFKD", limpa(t)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:n].strip("-")


def salva(img, caminho):
    img.convert("RGB").save(caminho, "JPEG", quality=94, optimize=True, progressive=True, subsampling=0)


def gera(post, pasta_saida, idx):
    data = datetime.date.today().strftime("%Y-%m-%d")
    tipo = post.get("tipo", "noticia")
    pasta = os.path.join(pasta_saida, f"{data}_{tipo}_{idx:02d}_{slug(post['manchete'])}")
    os.makedirs(pasta, exist_ok=True)
    arquivos = []
    p = os.path.join(pasta, f"feed_{tipo}_01_capa.jpg")
    salva(feed_capa(post), p)
    arquivos.append(p)
    slides = post.get("slides", [])[:4]
    tam = min((tam_que_cabe(s) for s in slides), default=None)
    for i, s in enumerate(slides, start=2):
        p = os.path.join(pasta, f"feed_{tipo}_{i:02d}.jpg")
        salva(feed_interno(post, s, tam), p)
        arquivos.append(p)
    p_story = os.path.join(pasta, f"story_{tipo}.jpg")
    salva(story(post), p_story)
    texto = legenda(post)
    with open(os.path.join(pasta, "legenda.txt"), "w", encoding="utf-8") as fh:
        fh.write(texto)
    meta = {"feed": [os.path.basename(a) for a in arquivos], "story": os.path.basename(p_story), "legenda": texto, "link": post.get("link")}
    with open(os.path.join(pasta, "post.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    print(f"✓ {pasta}  ({len(arquivos)} imagens no carrossel + story)")
    return pasta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json")
    ap.add_argument("--saida", default="saida")
    ap.add_argument("--publicar", action="store_true", help="publica carrossel + story no Instagram")
    a = ap.parse_args()
    with open(a.json, encoding="utf-8") as fh:
        dados = json.load(fh)
    posts = dados.get("posts", [dados]) if isinstance(dados, dict) else dados
    pastas = [gera(p, a.saida, i) for i, p in enumerate(posts, 1)]
    if a.publicar:
        from publica_instagram import publica_pasta
        falhas = 0
        for p in pastas:
            try:
                publica_pasta(p)
            except Exception as e:  # uma notícia com problema não derruba as outras
                falhas += 1
                print(f"  ✗ falhou ao publicar {os.path.basename(p)}: {e}", file=sys.stderr)
        if falhas:
            sys.exit(1)


if __name__ == "__main__":
    main()
