import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';

const source = fs.readFileSync(new URL('./FloatingUnitMenu.tsx', import.meta.url), 'utf8');
const positionSource = source.match(/export function floatingMenuPosition[\s\S]*?\n\}/)[0];
const compiled = ts.transpileModule(positionSource, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { floatingMenuPosition } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);

test('floating units fit mobile viewport edges and flip above a low trigger', () => {
  for (const width of [320, 390, 480]) {
    for (const y of [8, 400, 850]) {
      const anchor = { x: width - 56, y, width: 48, height: 44 };
      const menu = floatingMenuPosition(anchor, width, 900, 266);
      assert.ok(menu.left >= 8 && menu.left + menu.width <= width - 8);
      assert.ok(menu.top >= 8 && menu.top + menu.maxHeight <= 892);
      if (y === 850) assert.ok(menu.top + menu.maxHeight < anchor.y, 'Low trigger opens upward');
      else assert.ok(menu.top >= anchor.y + anchor.height, 'Menu opens under trigger where room permits');
    }
  }
});

test('short viewports constrain the scrollable menu instead of overflowing', () => {
  const menu = floatingMenuPosition({ x: 120, y: 150, width: 56, height: 44 }, 320, 300, 266);
  assert.ok(menu.maxHeight < 266);
  assert.ok(menu.top + menu.maxHeight <= 292);
});

test('receipt and pantry unit menus float outside scroll layout and dismiss on outside or system back', () => {
  assert.match(source, /<Modal transparent visible animationType="none" onRequestClose=\{onClose\}/);
  assert.match(source, /accessibilityLabel="Close unit menu"[\s\S]*?onPress=\{onClose\}/);
  assert.match(source, /position: 'absolute'/);
  assert.match(source, /keyboardShouldPersistTaps="handled"/);
  for (const name of ['ReceiptReviewScreen', 'MyBasketMainScreen']) {
    const screen = fs.readFileSync(new URL(`../screens/${name}.tsx`, import.meta.url), 'utf8');
    assert.match(screen, /measureInWindow/);
    assert.match(screen, /<FloatingUnitMenu[\s\S]*?onClose=/);
    assert.doesNotMatch(screen, /style=\{styles\.(unitOptionsMenu|remainingUnitMenu)\}/);
  }
});
