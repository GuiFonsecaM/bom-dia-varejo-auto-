// render.js — transforma roteiro.json (+ tempos.json da narração) em vídeo, quadro a quadro.
// Uso:
//   node scripts/render.js --roteiro roteiro.json --tempos tempos.json --parte 0 --partes 6 --out seg_0.mp4
//   node scripts/render.js --roteiro roteiro.json --tempos tempos.json --out video_sem_audio.mp4   (tudo de uma vez)
// Opções: --fps 30  --largura 720 (altura = 16:9 vertical)
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > -1 ? process.argv[i + 1] : d; };
const ROTEIRO = arg('roteiro', 'roteiro.json');
const TEMPOS = arg('tempos', null);
const PARTE = +arg('parte', 0), PARTES = +arg('partes', 1);
const FPS = +arg('fps', 30), W = +arg('largura', 720), H = Math.round(W * 16 / 9);
const OUT = arg('out', 'video_sem_audio.mp4');

(async () => {
  const raiz = path.resolve(__dirname, '..');
  const motor = fs.readFileSync(path.join(raiz, 'render', 'motor.html'), 'utf8');
  const pagina = path.join(raiz, 'render', '_pagina.html');
  fs.writeFileSync(pagina, '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0">' + motor + '</body></html>');

  const roteiro = JSON.parse(fs.readFileSync(ROTEIRO, 'utf8'));
  const tempos = TEMPOS && fs.existsSync(TEMPOS) ? JSON.parse(fs.readFileSync(TEMPOS, 'utf8')) : null;

  const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  const erros = [];
  page.on('pageerror', e => erros.push(e.message));
  await page.route('**/three.min.js', r => r.fulfill({ body: fs.readFileSync(require.resolve('three/build/three.min.js')), contentType: 'application/javascript' }));
  await page.goto('file://' + pagina + '?render');
  await page.waitForFunction(() => window.loadRoteiro && window.frameJPEG, null, { timeout: 60000 });
  const dur = await page.evaluate(([r, t]) => window.loadRoteiro(r, t, { render: true }), [roteiro, tempos]);
  if (erros.length) { console.error('Erro no motor:', erros); process.exit(1); }

  const total = Math.ceil(dur * FPS);
  const ini = Math.floor(total * PARTE / PARTES), fim = Math.floor(total * (PARTE + 1) / PARTES);
  console.log(`Duração ${dur.toFixed(2)} s · ${total} quadros · parte ${PARTE + 1}/${PARTES}: quadros ${ini}–${fim - 1}`);

  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p', '-r', String(FPS), OUT], { stdio: ['pipe', 'inherit', 'inherit'] });
  const t0 = Date.now();
  for (let f = ini; f < fim; f++) {
    const url = await page.evaluate(t => window.frameJPEG(t, 0.92), f / FPS);
    const buf = Buffer.from(url.slice(url.indexOf(',') + 1), 'base64');
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if ((f - ini) % 150 === 0) console.log(`  quadro ${f} (${((Date.now() - t0) / Math.max(1, f - ini + 1)).toFixed(0)} ms/quadro)`);
  }
  ff.stdin.end();
  await new Promise((res, rej) => ff.on('close', c => c === 0 ? res() : rej(new Error('ffmpeg saiu com ' + c))));
  await browser.close();
  fs.writeFileSync(OUT + '.json', JSON.stringify({ duracao: dur, quadros: total }));
  console.log('Pronto:', OUT);
})().catch(e => { console.error(e); process.exit(1); });
