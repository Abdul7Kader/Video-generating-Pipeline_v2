import {ensureBrowser} from '@remotion/renderer';
import {fileURLToPath} from 'node:url';
process.chdir(fileURLToPath(new URL('.', import.meta.url)));
await ensureBrowser();
console.log('Lokaler Remotion-Browser bereit');
