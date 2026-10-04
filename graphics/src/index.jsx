import React, {useEffect, useRef, useState} from 'react';
import {AbsoluteFill, Composition, cancelRender, continueRender, delayRender, registerRoot} from 'remotion';
import '@fontsource/noto-sans/latin-400.css';
import '@fontsource/noto-sans/latin-700.css';
import './overlay.css';

function Overlay({kind, text}) {
  const panel = useRef(null);
  const content = useRef(null);
  const [handle] = useState(() => delayRender('Lokale Schrift und sichere Textgrenzen'));
  useEffect(() => {
    let active = true;
    (async () => {
      await document.fonts.load('400 32px "Noto Sans"');
      await document.fonts.load('700 32px "Noto Sans"');
      await document.fonts.ready;
      if (!active) return;
      const node = content.current;
      const maxHeight = kind === 'title' ? 180 : 520;
      let fit = false;
      for (let size = kind === 'title' ? 42 : 36; size >= 22; size -= 2) {
        node.style.fontSize = `${size}px`;
        if (node.scrollHeight <= maxHeight && node.scrollWidth <= node.clientWidth) {fit = true; break;}
      }
      if (!fit) throw new Error('GRAPHICS_TEXT_OVERFLOW: Text passt nicht in die sicheren Ränder.');
      const box = panel.current.getBoundingClientRect();
      if (box.left < 64 || box.right > 608 || box.top < 96 || box.bottom > 1040) {
        throw new Error('GRAPHICS_TEXT_OVERFLOW: Grafik überschreitet den sicheren Bereich.');
      }
      console.log('GRAPHICS_LAYOUT:' + JSON.stringify({kind, fontSize: Number.parseInt(node.style.fontSize),
        left: box.left, right: box.right, top: box.top, bottom: box.bottom, text}));
      continueRender(handle);
    })().catch(cancelRender);
    return () => {active = false;};
  }, [handle, kind, text]);
  return <AbsoluteFill style={{backgroundColor: 'transparent', fontFamily: 'Noto Sans'}}>
    <div ref={panel} className={`overlay-panel ${kind}`}>
      <div ref={content} className="overlay-text">{text}</div>
    </div>
  </AbsoluteFill>;
}

function Root() {
  return <Composition id="Overlay" component={Overlay} width={720} height={1280} fps={24} durationInFrames={1}
    defaultProps={{kind: 'title', text: 'Bienen, Blüten & Grüße', position: 1, total: 6}} />;
}
registerRoot(Root);
