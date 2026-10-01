import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {ensureBrowser, openBrowser, renderStill, selectComposition} from '@remotion/renderer';

const request = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
const output = path.resolve(process.argv[3]);
const base = path.dirname(fileURLToPath(import.meta.url));
process.chdir(base);
const installed = await ensureBrowser({browserExecutable: process.env.REMOTION_BROWSER_EXECUTABLE || undefined,
  onBrowserDownload: () => {throw new Error('Renderbrowser fehlt. npm run install-browser --prefix graphics ausführen.');}});
await fs.mkdir(output, {recursive: true});
const serveUrl = await bundle({entryPoint: path.join(base, 'src/index.jsx'), outDir: path.join(output, '.bundle')});
const browser = await openBrowser('chrome', {browserExecutable: installed.path});
const layouts = [];
try {
  for (const item of request.items) {
    if (!/^(graphics_title|caption_[0-9]+)$/.test(item.key) || !['title', 'caption'].includes(item.kind)
      || typeof item.text !== 'string' || !item.text.trim() || item.text.length > (item.kind === 'title' ? 120 : 400)
      || !Number.isInteger(request.total) || request.total < 6 || request.total > 10
      || (item.kind === 'caption' && (!Number.isInteger(item.position) || item.position < 1 || item.position > request.total))) {
      throw new Error('Ungültige Grafik-Eingabe');
    }
    const props = {kind: item.kind, text: item.text, position: item.position, total: request.total};
    const composition = await selectComposition({serveUrl, id: 'Overlay', inputProps: props, puppeteerInstance: browser});
    let measured = null;
    const target = path.join(output, item.key + '.png');
    const pending = target + '.part';
    try {
      await renderStill({serveUrl, composition, inputProps: props, puppeteerInstance: browser, output: pending,
        imageFormat: 'png', timeoutInMilliseconds: 30000,
        onBrowserLog: (log) => {if (log.text.startsWith('GRAPHICS_LAYOUT:')) measured = JSON.parse(log.text.slice(16));}});
      if (!measured) throw new Error('Layout-Prüfnachweis fehlt');
      await fs.rename(pending, target);
      layouts.push({key: item.key, ...measured});
    } finally {await fs.rm(pending, {force: true});}
  }
  await fs.writeFile(path.join(output, 'layout.json'), JSON.stringify(layouts));
} finally {await browser.close({silent: true});}
