# KIT de peças 3D — referência para escrever `cena3d.codigo`

Cada cena do roteiro traz um **corpo de função JavaScript** em `cena3d.codigo`. O motor executa:

```js
new Function('K', 'THREE', 'cena', codigo)(K, THREE, cena)
```

- `K` é o kit (abaixo). Tudo o que você cria com `K.` já entra na cena.
- `cena` = `{ narracao, hud, dados, placa, duracao, indice }` (a duração é em segundos).
- O código **precisa terminar com `return { ... }`**:

```js
return {
  foco: [x, y, z],        // ponto principal da cena (a câmera mira aqui)
  raio: 6,                // meia-largura do que precisa caber na tela (o vídeo é vertical 9:16)
  az: 0,                  // de onde a câmera olha: 0 = de +z (frente), 1.57 = da direita, -1.57 = da esquerda
  atualizar(t) { ... },   // chamado a cada quadro; t = segundos desde o início da cena
  camera(t, dur) { ... }  // opcional: câmera própria (K.camera / K.cameraDe); sem isso, usa cena3d.camera
};
```

**Regras de ouro**
- **Toda cena começa num ambiente completo** (`K.ambiente(...)`, abaixo) ou num cenário pronto (`K.cenario(...)`). Nada de cena com chão vazio e meia dúzia de peças: o lugar precisa parecer real e vivo.
- **Movimento desde o primeiro quadro.** Em t = 0 algo já está se mexendo (pessoas andando, máquinas, trânsito, a câmera). O acontecimento principal da frase começa até 1 s; nada de esperar 2 s para "começar".
- **Nenhum número solto em 3D.** O número da cena aparece só no hud. Não escreva valores, anos, contagens ou percentuais em placas, rótulos ou contadores. Exceções: a etiqueta de preço quando a frase é sobre o preço mudando, e telas/placas do próprio mundo (CAIXA 3).
- Tudo deve ser **determinístico em função de `t`**: nada de `Math.random()` dentro de `atualizar`, nada de `setTimeout`. Use `K.aleatorio()` só na montagem (fora de `atualizar`).
- Chão em y = 0, unidades em metros. Uma pessoa tem ~1,9 m, um carro 4 m, uma gôndola 2,3 m.
- Pessoas e veículos olham para **+z**. Use `rotY` para virar (Math.PI = de costas para a câmera padrão).
- A faixa da tela entre 35% e 65% da altura é a área livre. O destaque (hud) fica em cima e a legenda embaixo. Mire o `foco` no assunto e use um `raio` que o enquadre bem.
- Texto 3D só quando faz parte do mundo (placa de loja, telão, etiqueta de preço, faixa de protesto), nunca para repetir o hud.
- Prédios e lojas que ficarem entre a câmera e o foco somem sozinhos naquele quadro; paredes e teto dos ambientes internos são "em corte" (somem vistos de fora), então a câmera pode olhar o interior de qualquer ângulo.
- Nada de marcas ou logos reais, nada de pessoas reais reconhecíveis, nada de sangue, feridos ou mortos. Conflitos podem ter aviões, mísseis, drones, navios e explosões genéricas.
- Seja econômico: até ~150 pessoas e ~600 peças por cena.
- **Física coerente, sempre** (vale para qualquer coisa, não só para os exemplos): nada flutua, nada atravessa nada, quem segura algo segura com a mão. Veja a seção *Física* abaixo; a prévia acusa as falhas e a cena só está pronta com zero avisos.

---

## Física — o que o motor faz sozinho e o que é com você
**Apoio automático.** Produtos, caixas, sacolas, cestas, paletes, celulares, notebooks, maquininhas, monitores, mesas, cadeiras e carrinhos (`K.produto`, `K.caixaPapelao`, `K.sacola`, `K.cesta`, `K.palete`, `K.celular`, `K.notebook`, `K.maquininha`, `K.monitor`, `K.mesa`, `K.cadeira`, `K.carrinho`) **descem ou sobem a cada quadro até encostar no que estiver embaixo**: chão, esteira, prateleira, bancada, mesa ou outro objeto apoiado (empilham). Se o objeto ficar "dentro" de algo sólido (ex.: cartão em y = 0 sob a esteira), ele sobe para o topo dele. Então basta dar `x` e `z` (e a altura aproximada da prateleira, se houver mais de uma) que ele pousa certo. Para outra peça também pousar sozinha, passe `{apoiar:true}` (ex.: `K.caixa(.9,.12,.7,'#333',{x,z,apoiar:true})`).
**O que pode voar** (avião, drone, balão, míssil, objeto caindo de propósito, algo pendurado em fio): passe `{voa:true}` ou chame `K.soltar(obj)`; sem isso a prévia acusa "objeto flutuando".
**Segurar de verdade.** `pessoa.segurar(obj, mao)` põe o objeto na palma e ele acompanha o braço; `pessoa.carregar(obj)` põe o objeto entre as duas mãos (ajusta o tamanho para caber); `robo.segurar(obj)` (robô de `K.produto('robo')`) faz o mesmo com os braços do robô. Nunca use `obj.position.set(...)`/`add` para fingir que alguém segura algo.
**Pessoas não se atravessam.** Os figurantes dos ambientes já andam em faixas próprias (≥ 1 m) e desviam sozinhos de móveis, gôndolas, carros, árvores e de quem está parado. As suas pessoas também precisam disso:
- quem anda segue uma faixa reta própria, a ≥ 1 m de qualquer outra; trajetórias nunca se cruzam;
- deixe espaço para o protagonista: `K.ambiente(nome, {livre:{x, z, raio}})` tira figurantes dessa área, e `K.cenario(nome, {figurantes:false})` desliga os figurantes do cenário;
- grupos e filas: `K.multidao` (só usa pontos livres) ou posições a ≥ 1 m (2,4 m na frente de quem empurra carrinho);
- se mesmo assim duas pessoas se encostarem, o motor afasta as duas no quadro (proteção final), mas a prévia avisa e você deve corrigir a trajetória.
**A prévia confere tudo isso.** `node scripts/previa.js roteiro.json` percorre cada cena inteira (a cada 0,25 s) e lista em `previa.json → avisos_fisica` coisas como "objeto flutuando no ar em x…", "pessoa atravessando objeto em x…", "2 pares de pessoas se encostando em x…" com o segundo exato. O quadro ganha o selo **⚠ física**. Corrija até não sobrar nenhum aviso.

---

## Ambientes completos — comece por aqui
`const a = K.ambiente(nome, op)` monta um lugar inteiro, cheio de gente e movimento, e devolve:
`a.palco` = `{x, z}` (área livre onde você coloca a ação da frase), `a.foco`, `a.raio` (enquadramento sugerido) e `a.atualizar(t)` (chame sempre no seu `atualizar`).

| nome | o que tem | palco |
|---|---|---|
| `supermercado` | 6 corredores de gôndolas com placas, açougue, padaria, frios, hortifrúti, 7 caixas com operadoras e fila, clientes com carrinho andando | corredor central na frente (0, 4); caixas em z = 14 (x = −15 a 15, a cada 5) |
| `atacarejo_interior` | porta-paletes altos, placas, empilhadeiras circulando, repositor, clientes, 6 caixas | corredor central (0, 8); caixas em z = 18 |
| `galpao` | centro de distribuição: porta-paletes, docas com caminhões, 3 empilhadeiras, operadores com paleteira, esteira com caixas, paletes | piso central (0, 6) |
| `fabrica` | duas linhas de produção com produtos andando, braços robóticos, máquinas, operários, empilhadeira | frente (0, 12) |
| `cidade` | cruzamento com avenida, prédios, faixas, semáforos, ônibus e carros andando, pedestres | calçada da esquina (9, 10) |
| `rua_comercial` | rua com 12 lojas com placas (padaria, farmácia, mercado...), árvores, carros, moto, pedestres com sacolas | calçada (6.5, 6); `op.lojas` = nomes das lojas |
| `bairro` | casas com cerca, rua, árvores, crianças jogando bola, pedestres | rua (0, 6) |
| `escritorio` | open space com 12 mesas, monitores com gráficos, pessoas digitando, sala de reunião de vidro | frente (0, 6) |
| `shopping` | átrio com lojas em dois andares, escada rolante, fonte, gente com sacolas | átrio (0, 8) |
| `porto` | mar com ondas, cais, guindastes trabalhando, navio de contêineres, pilhas de contêineres, caminhões | cais (0, 4) |
| `fazenda` | lavoura, colheitadeira e trator andando, celeiro, silos, cerca, vacas | (4, 10); `op.cultura` = cor da plantação |
| `aeroporto` | pista, terminal, aviões parados e um decolando, vans de serviço | (0, 0) |
| `estudio_tv` | bancada de telejornal com apresentador falando, telão com a logo, câmeras e holofotes | bancada (0, −1) |

Para lojas e supermercados com gôndola específica (vazia, pela metade, de um produto), use `K.gondolaRapida({x,z,comprimento,produtos})`, que é leve mesmo com muitas.

## Utilidades
| Função | O que faz |
|---|---|
| `K.aleatorio(a,b)`, `K.escolher(lista)` | aleatório determinístico (use só na montagem) |
| `K.entre(t,t0,t1)` | 0→1 entre t0 e t1 (limitado) |
| `K.ease(p)`, `K.saltar(p)`, `K.quicar(p)` | curvas de animação (suave, com overshoot, quicando) |
| `K.repetir(t,periodo)` | 0→1 em loop |
| `K.cor(hex, ajuste)` | clareia (+) ou escurece (−) uma cor, ex.: `K.cor('#c0392b',-.1)` |
| `K.LARANJA`, `K.VERMELHO`, `K.VERDE` | cores da marca |
| `K.noite` | true se `luz` = "noite" (janelas acesas, faróis) |
| `K.grupo({x,y,z,rotY})` + `K.dentro(grupo, () => {...})` | cria um grupo e monta peças dentro dele (posições relativas) |
| `K.ceu('#hex')` | troca a cor do céu desta cena |

Todas as peças aceitam um objeto de opções com `x, y, z, rotY, rot:[x,y,z], escala, pai`.

## Primitivas
`K.caixa(w,h,d,cor,op)`, `K.cilindro(rTopo,rBase,h,cor,op)`, `K.esfera(r,cor,op)`, `K.cone(r,h,cor,op)`, `K.anel(r,espessura,cor,op)`,
`K.plano(w,h,cor,{deitado})`, `K.chao(cor)`, `K.parede(w,h,cor,op)`, `K.janela(op)`, `K.porta(op)`,
`K.extrudar([[x,z],...], altura, cor, op)` (forma qualquer vista de cima), `K.linha3D([[x,y,z],...], cor)`,
`K.tubo([[x,y,z],...], raio, cor)` → `.desenhar(p)` desenha o tubo de 0 a p (linhas, trajetos, rotas).
Opções de material: `{brilho:true, metal:true, emissivo:true, opacidade:.5}`.

## Texto, placas e telas
- `K.placa(texto,{largura,altura,fundo,cor})` placa retangular (fundo `null` = só o texto)
- `K.faixa(texto,{largura})` faixa de protesto com dois paus
- `K.placaOferta(texto)`, `K.placaAluga({texto})`, `K.etiquetaPreco(texto,{eletronica})` → `.trocar(novoTexto)`
- `K.tela((ctx,W,H,...args)=>{desenho 2D}, {largura,altura})` tela qualquer → `.redesenhar(...args)` (app, painel, placar, gráfico 2D)
- `K.telao(desenho,{largura,altura,y})`, `K.monitor({tela})`, `K.notebook({tela})`, `K.celular({tela})` (as três têm `.tela.redesenhar()`)
- `K.qrcodePix({largura})`, `K.rotulo(texto,{cor,largura,altura,x,y,z})` → `.mudar(texto)` (texto flutuante: use pouco)
- (números soltos em 3D foram desativados: `K.numero` e `K.contador` não desenham nada)

## Pessoas
`K.pessoa({uniforme, camisa, calca, pele, cabelo, x, z, rotY, escala})`
Uniformes: `policial, medico, enfermeiro, chef, operario, juiz, terno, soldado, atleta, astronauta, entregador, repositor, caixa, agricultor, bombeiro, cientista, estudante, idoso, crianca`.
Ações (chame dentro de `atualizar`): `.andar(t,vel)`, `.correr(t)`, `.parado(t)`, `.acenar(t)`, `.bracosParaCima(t)`, `.apontar()`, `.falar(t)`, `.digitar(t)`, `.comemorar(t)`, `.empurrar(t)` (carrinho);
uma vez: `.sentar()`, `.carregar(obj)` (com as duas mãos; o braço fica travado enquanto carrega), `.segurar(obj, mao=1)` (na palma; o objeto acompanha o braço).
Partes: `p.userData.arms[0|1].rotation.x`, `p.userData.legs[0|1].rotation.x` para poses próprias.

`K.multidao(n,{x,z,largura,profundidade,olhando,cartazes:0.4,uniformes:[...],camisas:[...]})` → `.atualizar(t, modo, vel)` com modo `'parado' | 'andar' | 'pular' | 'acenar' | 'aplaudir'`.
`K.caminhar(obj, [[x,z],[x,z],...], t, vel, loop)` move e anima pelo trajeto.

## Veículos (frente para +z)
`K.carro({cor})`, `K.viatura()`, `K.ambulancia()` (as duas têm `.atualizar(t)` para o giroflex), `K.caminhao({cor})`, `K.onibus({cor})`, `K.van({cor})`, `K.moto({piloto,uniforme})`, `K.bicicleta()`,
`K.empilhadeira()` (`.atualizar(t)` sobe o garfo), `K.paleteira()`, `K.carrinho()`, `K.trator()`, `K.colheitadeira()`,
`K.aviao({tipo:'comercial'|'caca', cor, corCauda})`, `K.helicoptero()` (`.atualizar(t)` gira o rotor), `K.navio({tipo:'carga'|'guerra'|'cruzeiro'|'pesqueiro'})`, `K.barco()`,
`K.trem({vagoes})` + `K.trilhos(comprimento)`, `K.drone()`, `K.missil()`, `K.foguete()` (`.chama.visible`, `.atualizar(t)`), `K.satelite()`.

## Construções e lugares
`K.predio({largura,altura,profundidade,cor})`, `K.casa({cor,telhado})`, `K.loja({placa,largura,cor,corFaixa})`, `K.atacarejo({placa})`, `K.galpao({placa})`, `K.fabrica({placa})` (`.atualizar` = fumaça),
`K.escola({placa})`, `K.hospital({placa})`, `K.igreja()`, `K.estadio({cores})` (`.atualizar(t, festa)` = torcida), `K.posto()`, `K.palco({texto})`, `K.doca()`,
`K.torreEnergia()`, `K.paineisSolares({fileiras,colunas})`, `K.eolica()` (`.atualizar`), `K.plataformaPetroleo()` (`.atualizar`), `K.guindastePorto()` (`.atualizar`), `K.pista()`, `K.ponte({comprimento})`,
`K.rua({comprimento,largura})`, `K.cidade({largura,profundidade,min,max,cores})`, `K.arvore({tamanho,cor})`, `K.floresta(n,{largura,profundidade})`, `K.montanha({raio,altura,neve})`,
`K.mar({cor})` (`.atualizar(t)` = ondas), `K.agua({nivel})`, `K.campo({cor,largura,fileiras})`, `K.cerca(comp)`, `K.poste()`, `K.semaforo()` (`.estado(0|1|2)`), `K.bancoPraca()`, `K.mesa({largura,profundidade})`, `K.cadeira()`.

## Varejo
`K.gondola({comprimento,niveis,produtos:'mercearia'|'bebidas'|'limpeza'|'higiene'|'laticinios'|'meia'|'vazia',placa})`, `K.portaPalete({comprimento,vazio})`,
`K.checkout({numero,operador})` (`.atualizar(t)` = esteira e operador), `K.selfCheckout()`, `K.balcaoRefrigerado({itens:'carne'|'frios'})`, `K.camaraFria()`, `K.padariaVitrine()`,
`K.bancaHortifruti({cores,preco})`, `K.palete({carga,altura,cor})`, `K.caixaPapelao()`, `K.sacola()`, `K.cesta()`, `K.maquininha()`, `K.qrcodePix()`, `K.etiquetaPreco()`,
`K.fitaInauguracao({largura})` (`.cortar(p)`), `K.baloes(n,{largura})` (`.atualizar`), `K.headset()`.

## Produtos e objetos — `K.produto(tipo, op)`
garrafa, lata, saco_grao, cafe, carne, frango, ovos, leite, fruta, verdura, pao, arroz, feijao, oleo, acucar, cerveja, refrigerante, sabao, papel_higienico, remedio,
caixa, palete, sacola, cesta, carrinho, cartao, celular, maquininha, moedas, notas, bolsa_dinheiro, cofre, caixa_registradora, documento, caneta, chave, cadeado, urna, calendario, relogio, livro,
termometro, seringa, vacina, trofeu, bola, medalha, microfone, bandeira, lupa, grafico, lampada, engrenagem, chip, robo, xicara, pizza, nuvem_chuva, sol, predio, globo, combustivel, conteiner, navio, aviao, trator, caminhao, empilhadeira, pessoas, carros.

## Natureza, clima e efeitos
`K.nuvem({tamanho,cor})`, `K.chuva()`, `K.neve()`, `K.raio({x,z,intervalo})`, `K.sol()`, `K.lua()`, `K.estrelas()`,
`K.fogo({tamanho,chamas})`, `K.fumaca({tamanho,qtd,cor})`, `K.explosoes()` → `.adicionar(x,y,z,t0,tamanho)` + `.atualizar(t)`,
`K.particulas({qtd,area,altura,cor,cores,subindo,vel})`, `K.confete()`, `K.moedasCaindo()`, `K.notasVoando()`, `K.pulso({x,z})`, `K.seta({descendo})`,
`K.luzPonto(cor,intensidade,distancia,{x,y,z})`, `K.holofote({x,y,z,alvoX,alvoY,alvoZ})`.
Os que têm movimento retornam um objeto com `.atualizar(t)`; chame dentro de `atualizar`.

## Dados
- `K.barras([{rotulo,valor,texto,cor}],{altura,espaco,unidade})` → `.atualizar(t)`
- `K.linhaGrafico([{rotulo,valor,texto}],{largura,altura})` → `.atualizar(t)`
- `K.pizza([{rotulo,valor,texto,cor}],{raio})` → `.atualizar(t)`
- `K.linhaDoTempo([{ano,texto}],{espaco})` → `.destacar(i)`, `.marcos[i].z`

## Mapas reais (fronteiras do Natural Earth e do IBGE)
- `K.globo({pinos:[{pais_en,lat,lon}], paises:['Saudi Arabia'], y, escala})` → `.atualizar(t)`; o globo gira até os pinos (a câmera deve olhar de frente, `az: 0`)
- `K.mapaBrasil({estados:['MG','SP'], pinos:[{lat,lon}]})` → `.atualizar(t)`
- `K.mapaMinas({pinos:[{lat,lon}]})` → `.atualizar(t)`
- `K.pino({cor})`
Sempre use lat/lon reais do local citado.

## Cenários prontos como fundo
`K.cenario(nome, {placa, dados})` monta um cenário inteiro do catálogo e devolve `{focus, r, update}`. Útil como base; acrescente o que a frase pede e chame `s.update(t)` no seu `atualizar`.
Nomes: fachada_atacarejo, corredor_porta_paletes, gondola_mercearia, hortifruti, acougue_frios, checkout_caixas, centro_distribuicao, estrada_caminhao, porto_conteineres, lavoura, posto_combustivel, rua_comercial, casa_familia, fabrica, escritorio_reuniao, predio_governo, bolsa_mercado, cidade_mundo, grafico_barras, grafico_linha, contador_gigante, vitrine_produto, mapa_brasil, mapa_minas, globo_mundo, linha_do_tempo, urna_votacao, protesto, comicio, bombardeio, ataque_drones, interceptacao_misseis, navios_guerra, rede_eletrica, parlamento, tribunal, policia, familias_deslocadas, tempestade, incendio, cupula_diplomatica.

## Animação
`K.aparecer(obj,t,t0,dur,escala)`, `K.sumir(obj,t,t0,dur)`, `K.mover(obj,[x,y,z],[x,y,z],t,t0,t1)`, `K.cair(obj,t,t0,altura,yFinal)`, `K.girar(obj,t,vel,eixo)`,
`K.balancar(obj,t,amp,vel)`, `K.flutuar(obj,t,amp,vel)`, `K.piscar(obj,t,freq)`, `K.seguirCurva(obj,[[x,y,z],...],t,t0,t1)` (vira na direção do movimento).

## Câmera própria (opcional)
Dentro de `camera(t,dur)`: `K.camera([x,y,z],[olharX,olharY,olharZ],fov)` ou `K.cameraDe(t,dur,[de],[para],[olharDe],[olharPara])` (movimento suave do início ao fim da cena).
Sem `camera`, o motor usa o preset de `cena3d.camera` em volta do `foco` e do `raio`.

---

## Exemplos

**Curiosidade — Tesco imprime 16 milhões de cartões (dentro de uma fábrica, sem número em 3D)**
```js
const a = K.ambiente('fabrica');
const maq = K.grupo({x: -2, z: 12});
K.dentro(maq, () => { K.caixa(3, 2.2, 2.4, '#5c6670'); K.caixa(3.2, .3, 2.6, K.LARANJA, {y: 2.2}); });
K.caixa(5, .9, 1, '#2b2f36', {x: 2, z: 12});
const op = K.pessoa({uniforme: 'operario', x: -2, z: 14.2, rotY: Math.PI});
const cartoes = []; for (let i = 0; i < 36; i++) cartoes.push(K.produto('cartao', {escala: .7}));
return {foco: [1, 1.4, 12], raio: 4.2, az: .35, atualizar(t) {
  a.atualizar(t); op.digitar(t);
  cartoes.forEach((c, i) => { const f = t * 1.4 + i / 36 * 2;            // já começa em movimento
    if (f < 2) c.position.set(-.6 + (f % 1) * 4.4, .95, 12);
    else c.position.set(4.6, .9 + (i % 18) * .05, i > 17 ? 12.5 : 11.6); });
}};
```

**Varejo — cliente paga com Pix (no caixa 4 do supermercado)**
```js
const a = K.ambiente('supermercado');
const cli = K.pessoa({x: -1.2, z: 15.2, rotY: Math.PI / 2, camisa: '#3f6fb5'});
cli.segurar(K.celular(), 1);
K.qrcodePix({largura: .5, altura: .5, x: -.3, y: 1.5, z: 15.6, rotY: -Math.PI / 2});
const tela = K.tela((x, W, H, ok) => { x.fillStyle = ok ? '#3fae6a' : '#14171c'; x.fillRect(0, 0, W, H);
  x.fillStyle = '#fff'; x.textAlign = 'center'; x.font = '800 ' + H * .32 + 'px Open Sans'; x.fillText(ok ? 'PAGO ✓' : 'PIX', W / 2, H * .64); },
  {largura: 1, altura: .5, y: 2.4, z: 15.3, rotY: -Math.PI / 2});
let pago = false;
return {foco: [-.6, 1.5, 14.6], raio: 2.8, az: -1.0, atualizar(t) {
  a.atualizar(t); cli.userData.arms[1].rotation.x = -1.2 - Math.min(.4, t * .4);
  const deve = t > 1.2; if (deve !== pago) { pago = deve; tela.redesenhar(pago); }
}};
```

**Mundo — manifestação em Paris com polícia**
```js
const s = K.cenario('protesto', {placa: 'CUSTO DE VIDA'});
const v = K.viatura({x: 9, z: 2, rotY: -.4});
return {foco: [0, 2.5, 4], raio: 12, az: 0, atualizar(t) { s.update(t); v.atualizar(t); }};
```

**Esporte — gol com câmera própria**
```js
K.chao('#2b2f36');
const est = K.estadio();
const bola = K.produto('bola');
const jog = []; for (let i = 0; i < 6; i++) jog.push(K.pessoa({uniforme: 'atleta', camisa: i < 3 ? '#e5534b' : '#f4f4f2', x: -6 + i * 2.4, z: -30 + i}));
return {foco: [0, 3, -40], raio: 10, atualizar(t) {
  est.atualizar(t, t > 3 ? 1.4 : .3);
  const q = K.entre(t, .5, 3); bola.position.set(Math.sin(q * 3) * 2, .1 + Math.sin(q * Math.PI) * 2.5, -30 - 22.5 * q);
  jog.forEach((p, i) => { p.position.z = -30 + i - q * 16; p.correr(t + i); if (t > 3.2 && i < 3) p.comemorar(t + i); });
}, camera(t, dur) { K.cameraDe(t, dur, [18, 10, -22], [10, 6, -36], [0, 1, -36], [0, 1, -48]); }};
```
