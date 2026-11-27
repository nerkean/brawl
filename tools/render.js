// Покадровый рендер HTML-шаблона.
//   node render.js <index.html> stills <t1> <t2> ...   -> stills/t*.png
//   node render.js <index.html> sfx                    -> sfx.json (моменты звуковых эффектов)
//   node render.js <index.html> video                  -> video_noaudio.mp4
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const { spawn } = require('child_process');
(async () => {
  const [file, mode, ...rest] = process.argv.slice(2);
  const dir = path.dirname(path.resolve(file));
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  await p.goto('file://' + path.resolve(file));
  await p.evaluate(() => document.fonts.ready);
  await p.evaluate(async () => { await Promise.all([...document.images].map(i => i.decode().catch(() => {}))); window.fitAll && fitAll(); });
  await p.waitForTimeout(400);
  if (mode === 'stills') {
    fs.mkdirSync(path.join(dir, 'stills'), { recursive: true });
    for (const t of rest.map(Number)) { await p.evaluate(t => seek(t), t); await p.screenshot({ path: path.join(dir, 'stills', `t${t}.png`) }); }
  } else if (mode === 'sfx') {
    fs.writeFileSync(path.join(dir, 'sfx.json'), JSON.stringify(await p.evaluate(() => getSFX())));
  } else {
    const fps = 30, dur = await p.evaluate(() => TL.duration), N = Math.ceil(dur * fps);
    const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', '' + fps, '-c:v', 'mjpeg', '-i', '-',
      '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', path.join(dir, 'video_noaudio.mp4')], { stdio: ['pipe', 'inherit', 'inherit'] });
    for (let i = 0; i < N; i++) {
      await p.evaluate(t => seek(t), i / fps);
      const buf = await p.screenshot({ type: 'jpeg', quality: 94 });
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if (i % 150 === 0) console.log(`   кадр ${i}/${N}`);
    }
    ff.stdin.end(); await new Promise(r => ff.on('close', r));
  }
  await b.close();
})();
