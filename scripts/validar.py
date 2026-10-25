"""
validar.py — confere o roteiro.json antes de salvar no Notion.
Uso: python3 scripts/validar.py roteiro.json noticias|curiosidade|mundo
Sai com código 0 se estiver tudo certo; senão lista os problemas e sai com 1.
"""
import json
import re
import sys

ABERTURA = {
    "noticias": "Bom dia varejo! Isso é o que você precisa saber antes da loja abrir.",
    "curiosidade": "Bom dia varejo! Hoje é dia de curiosidade sobre o mundo das lojas.",
}
FECHAMENTO = {
    "noticias": "Isso foi o Bom dia varejo. Segue o perfil pra saber antes da loja abrir.",
    "curiosidade": "Isso foi o Bom dia varejo. Segue o perfil pra saber antes da loja abrir.",
    "mundo": "Isso foi o Bom dia varejo, edição da noite. Segue o perfil pra não perder nada.",
}
CATALOGO = set("""fachada_atacarejo corredor_porta_paletes gondola_mercearia hortifruti acougue_frios checkout_caixas centro_distribuicao estrada_caminhao porto_conteineres lavoura posto_combustivel rua_comercial casa_familia fabrica escritorio_reuniao predio_governo bolsa_mercado cidade_mundo grafico_barras grafico_linha contador_gigante vitrine_produto mapa_brasil mapa_minas globo_mundo linha_do_tempo urna_votacao protesto comicio bombardeio ataque_drones interceptacao_misseis navios_guerra rede_eletrica parlamento tribunal policia familias_deslocadas tempestade incendio cupula_diplomatica""".split())
CAMERAS = set("aproximacao afastamento sobrevoo mergulho_drone orbita travelling_lateral segue_personagem vista_de_cima close_produto camera_na_mao".split())
LUZES = {"dia", "tarde", "noite", "interno", "estudio"}
PROIBIDAS = ["hoje", "ontem", "amanhã", "nesta semana", "semana passada", "leitura editorial", "shopping cart"]


def main():
    rot = json.load(open(sys.argv[1], encoding="utf-8"))
    modo = sys.argv[2] if len(sys.argv) > 2 else rot.get("modo", "noticias")
    P = []
    cenas = rot.get("cenas", [])
    if not 16 <= len(cenas) <= 26:
        P.append(f"{len(cenas)} cenas (esperado 16 a 26)")
    palavras = sum(len(str(c.get("fala", "")).split()) for c in cenas)
    if not 300 <= palavras <= 420:
        P.append(f"{palavras} palavras na fala (esperado 300 a 420)")
    if cenas:
        ab = cenas[1] if len(cenas) > 1 else cenas[0]
        if modo in ABERTURA and ab.get("fala", "").strip() != ABERTURA[modo] and not (modo == "noticias" and ab.get("fala", "").startswith("Bom dia varejo!")):
            P.append("abertura diferente da fala exata do modo")
        if modo == "mundo" and not ab.get("fala", "").startswith("Bom dia varejo, edição da noite."):
            P.append("abertura do Mundo deve começar com 'Bom dia varejo, edição da noite.'")
        if cenas[-1].get("fala", "").strip() != FECHAMENTO.get(modo, ""):
            P.append("fechamento diferente da fala exata do modo")
    texto_total = json.dumps(rot, ensure_ascii=False).lower()
    for fixa in list(ABERTURA.values()) + list(FECHAMENTO.values()):
        texto_total = texto_total.replace(fixa.lower(), "")
    for w in PROIBIDAS:
        if re.search(r"\b" + re.escape(w) + r"\b", texto_total):
            P.append(f"palavra proibida no roteiro: '{w}'")
    for i, c in enumerate(cenas, 1):
        fala, narr = str(c.get("fala", "")), str(c.get("narracao", ""))
        if re.search(r"[0-9*%€$/+]", fala):
            P.append(f"cena {i}: a fala tem algarismo ou símbolo: {re.findall(r'[0-9*%€$/+]+', fala)[:3]}")
        if narr.count("**") > 4 or narr.count("**") % 2:
            P.append(f"cena {i}: destaques ** demais ou sem fechar")
        h = c.get("hud")
        if h:
            if len(h.get("chapeu", "")) > 26: P.append(f"cena {i}: chapeu com mais de 26 caracteres")
            if len(h.get("destaque", "")) > 9: P.append(f"cena {i}: destaque com mais de 9 caracteres")
            if len(h.get("apoio", "")) > 34: P.append(f"cena {i}: apoio com mais de 34 caracteres")
        c3 = c.get("cena3d") or {}
        if c3.get("luz") not in LUZES:
            P.append(f"cena {i}: luz inválida ({c3.get('luz')})")
        if c3.get("codigo"):
            cod = str(c3["codigo"])
            if "return" not in cod:
                P.append(f"cena {i}: o código não tem 'return {{...}}'")
            if "Math.random" in cod:
                P.append(f"cena {i}: não use Math.random (use K.aleatorio na montagem)")
            if "K.numero(" in cod or "K.contador(" in cod:
                P.append(f"cena {i}: não use número solto em 3D (K.numero/K.contador): o número fica só no hud")
            dest = re.sub(r"[^0-9]", "", (c.get("hud") or {}).get("destaque", ""))
            if dest and len(dest) >= 2 and re.search(r"['\"`][^'\"`]*" + dest + r"[^'\"`]*['\"`]", cod) and "etiquetaPreco" not in cod:
                P.append(f"cena {i}: o número do hud ({dest}) aparece escrito na cena 3D; tire (o hud já mostra)")
            if c3.get("reserva") not in CATALOGO:
                P.append(f"cena {i}: 'reserva' precisa ser um cenário do catálogo")
        else:
            if c3.get("cenario") not in CATALOGO:
                P.append(f"cena {i}: sem código e com cenário inválido ({c3.get('cenario')})")
        if c3.get("camera") and c3["camera"] not in CAMERAS:
            P.append(f"cena {i}: câmera inválida ({c3['camera']})")
    if not rot.get("legenda_post"):
        P.append("falta legenda_post")
    if P:
        print("PROBLEMAS:\n- " + "\n- ".join(P))
        sys.exit(1)
    print(f"OK: {len(cenas)} cenas, {palavras} palavras.")


if __name__ == "__main__":
    main()
