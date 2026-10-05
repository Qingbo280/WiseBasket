import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const source = fs.readFileSync(
  path.resolve(process.cwd(), 'src/data/recipeAssetManifest.ts'),
  'utf8',
);

test('builds public R2 recipe image URLs from recipe catalogue slugs', () => {
  assert.match(source, /recipes\/\$\{normalizedId\}\.webp/);
  assert.match(source, /recipeImageUriForId/);
  assert.match(source, /cache: 'force-cache'/);
});

test('only allows safe slug-form recipe IDs in R2 paths', () => {
  assert.match(source, /\^\[a-z0-9\]\+\(\?:-\[a-z0-9\]\+\)\*\$/);
});
