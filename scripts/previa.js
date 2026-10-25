// previa.js — folha de contato do roteiro para conferir as cenas antes de publicar.
// Uso: node scripts/previa.js roteiro.json [saida.jpg] [--cenas 3,4,7]
// Gera: previa.jpg (2 quadros por cena: 35% e 85% do tempo) e previa.json (erros e avisos de física por cena).
// Avisos de física: objeto flutuando, pessoa atravessando objeto, pessoas se encostando. Corrija todos antes de salvar.
// Precisa de: npm i three@0.128.0 (o Playwright/Chromium já vem no ambiente)
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const args = process.argv.slice(2);
  const rotPath = args[0] || 'roteiro.json';
  const out = (args[1] && !args[1].startsWith('--')) ? args[1] : 'previa.jpg';
  const iC = args.indexOf('--cenas');
  const so = iC > -1 ? args[iC + 1].split(',').map(n => +n - 1) : null;
  const raiz = path.resolve(__dirname, '..');
  const motor = fs.readFileSync(path.join(raiz, 'render', 'motor.html'), 'utf8');
  const pag = path.join(raiz, 'render', '_previa.html');
  fs.writeFileSync(pag, '<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0">' + motor + '</body></html>');
  const rot = JSON.parse(fs.readFileSync(rotPath, 'utf8'));

  const three = (() => { try { return require.resolve('three/build/three.min.js', { paths: [process.cwd(), raiz] }); } catch (e) { return null; } })();
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: 360, height: 640 } });
  const erros = [];
  p.on('pageerror', e => erros.push(e.message));
  p.on('console', m => { if (m.type() === 'error' && !/net::|Failed to load/.test(m.text())) erros.push(m.text()); });
  if (three) await p.route('**/three.min.js', r => r.fulfill({ body: fs.readFileSync(three), contentType: 'application/javascript' }));
  await p.goto('file://' + pag + '?render');
  await p.waitForFunction(() => window.loadRoteiro, null, { timeout: 60000 });
  await p.evaluate(r => window.loadRoteiro(r, null, { render: true }), rot);
  const info = await p.evaluate(() => ({ cenas: (window.__CENAS || []), erros: window.__ERROS || [] }));

  const imgs = [];
  const fis = {};
  for (let i = 0; i < info.cenas.length; i++) {
    if (so && !so.includes(i)) continue;
    const c = info.cenas[i];
    const av = await p.evaluate(k => (window.checarCena ? window.checarCena(k) : []), i);
    if (av.length) fis[i] = new Set(av);
    for (const f of [0.35, 0.85]) {
      const url = await p.evaluate(t => window.frameJPEG(t, 0.82), c.inicio + (c.fim - c.inicio) * f);
      imgs.push({ i, f, url });
    }
  }
  const erros2 = await p.evaluate(() => window.__ERROS || []);
  // monta a folha com rótulos
  const cols = 6, w = 180, h = 320;
  const html = `<html><body style="margin:0;background:#111;font:600 13px sans-serif;color:#fff">
    <div style="display:grid;grid-template-columns:repeat(${cols},${w}px);gap:6px;padding:6px">
    ${imgs.map(o => `<div style="position:relative"><img src="${o.url}" width="${w}" height="${h}" style="display:block">
      <div style="position:absolute;left:4px;top:4px;background:#ff7a00;color:#000;padding:2px 6px;border-radius:4px">Cena ${o.i + 1} · ${Math.round(o.f * 100)}%</div>
      ${erros2.some(e => e.cena === o.i) ? '<div style="position:absolute;right:4px;top:4px;background:#e5534b;padding:2px 6px;border-radius:4px">ERRO → reserva</div>' : ''}
      ${fis[o.i] ? '<div style="position:absolute;right:4px;top:30px;background:#f2c84b;color:#000;padding:2px 6px;border-radius:4px">⚠ física</div>' : ''}</div>`).join('')}
    </div></body></html>`;
  const q = await b.newPage({ viewport: { width: cols * (w + 6) + 6, height: 400 } });
  await q.setContent(html);
  await q.waitForTimeout(300);
  await q.screenshot({ path: out, fullPage: true, type: 'jpeg', quality: 80 });
  await b.close();
  fs.unlinkSync(pag);
  const avisos = Object.keys(fis).map(k => ({ cena: +k + 1, avisos: [...fis[k]] }));
  const rel = { imagem: out, cenas: info.cenas.length, erros_por_cena: erros2, avisos_fisica: avisos, outros_erros: erros.filter(e => !/cena \d+/.test(e)) };
  fs.writeFileSync(out.replace(/\.\w+$/, '.json'), JSON.stringify(rel, null, 2));
  console.log(JSON.stringify(rel, null, 2));
  process.exit(erros2.length ? 2 : (avisos.length ? 3 : 0));
})().catch(e => { console.error(e); process.exit(1); });
