import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import { introPosterLayout } from './introPosterLayout.ts';

const posters = ['06_intro_01.png', '06_intro_02.png'].map((name) => {
  const png = fs.readFileSync(new URL(`../../assets/images/intro/${name}`, import.meta.url));
  return { width: png.readUInt32BE(16), height: png.readUInt32BE(20) };
});

for (const viewport of [
  { width: 320, height: 493 },
  { width: 393, height: 777 },
  { width: 430, height: 857 },
  { width: 390, height: 704 },
  { width: 852, height: 318 },
]) {
  test(`poster and controls fit ${viewport.width} × ${viewport.height}`, () => {
    for (const poster of posters) {
      const layout = introPosterLayout(viewport, poster);
      assert.ok(layout.width <= viewport.width + 0.001);
      assert.ok(layout.height <= viewport.height + 0.001);
      assert.ok(Math.abs(layout.width / layout.height - poster.width / poster.height) < 0.001);
      // Inspect the actual art: Skip is centred around (770, 160), arrow (750, 1725).
      for (const [control, point] of [[layout.skip, [770, 160]], [layout.next, [750, 1725]]]) {
        const x = point[0] / poster.width * layout.width;
        const y = point[1] / poster.height * layout.height;
        assert.ok(x >= control.left && x <= control.left + control.width);
        assert.ok(y >= control.top && y <= control.top + control.height);
        assert.ok(control.left >= 0 && control.top >= 0);
        assert.ok(control.left + control.width <= layout.width + 0.001);
        assert.ok(control.top + control.height <= layout.height + 0.001);
        assert.ok(control.width >= 44 && control.height >= 44);
      }
      const logo = layout.logo;
      const skip = layout.skip;
      assert.ok(logo.left + logo.width < skip.left);
      assert.ok(Math.abs(logo.top + logo.height / 2 - 160 / poster.height * layout.height) < 2);
    }
  });
}
