# WiseBasket Iteration 2

This document describes the current repository implementation. It does not certify that every change is deployed or verified on a real device.

## Implemented scope

Iteration 2 retains authentication, profile synchronisation, deterministic weekly planning, hard dietary exclusions, location selection and store price comparison. It adds pantry and recipe workflows, receipt OCR and optional LLM interpretation. The mobile client is under `apps/mobile`; the API, worker and OCR service are under `services/api`, `services/worker` and `services/inference`. There is currently no `apps/admin` directory in this checkout.

Worth-considering recommendations use constrained LLM selection and curated wording, with a deterministic fallback. Budget, nutrition and store price calculations remain code-owned.

## Pantry and recipes

- Recipe “Have it” selections save canonical food IDs to the household pantry. Quantity is optional; no amount is invented.
- Basket “Have at home” choices also persist pantry presence. Receipt confirmation refreshes the pantry.
- Successful pantry state updates trigger a recipe suggestion fetch. Basket recipe cards open recipe details.
- Card badges count all listed recipe ingredients, including optional staples. Oil alone in Cauliflower Stir-Fry is `1/5`; eggs plus oil in Soy Sauce Eggs with Rice is `2/7`.
- The API supplies `ingredient_count`; the numerator is `available_ingredients.length`. Older responses without a valid total show the available count without a denominator.
- The badge turns green only when all listed ingredients are available. Availability does not prove enough quantity for household servings.

Recipe ranking currently prioritises the fraction and count of main ingredient matches, followed by required ingredient match percentage/count, quantity status, optional semantic score and stable tie-breakers. Main ingredients are inferred from required portions at least 25% of the largest required portion; missing recipe amounts use a conservative inclusion rule. This is a heuristic, not an explicit ingredient-role field.

Signed-in shopping-list purchased ticks save canonical ingredient presence to pantry and refresh recipe suggestions. Rapid changes are serialised. Unticking removes only pantry records created by this shopping session, preserving pre-existing pantry records. Planned purchase quantities are not treated as measured pantry amounts. Guest ticks remain local.

**Pending:** making the displayed all-ingredient percentage the primary ranking rule. The badge update alone did not change ranking. The basket's consumed/removed/quantity overrides still have local state paths that are not all synchronised to backend pantry records.

Source: `services/api/app/services/recipe_matching.py`, `services/api/app/main.py`, `apps/mobile/App.tsx`, `apps/mobile/src/services/recipePantry.ts`, `apps/mobile/src/services/recipeIngredientBadge.ts` and `apps/mobile/src/screens/MyBasketMainScreen.tsx`.

## Receipt OCR and LLM extraction

1. PaddleOCR recognises text boxes. Code groups them into visual rows and produces deterministic purchase drafts.
2. Duplicate suppression uses identical normalised text and overlapping geometry; genuine repeated purchases remain separate.
3. Inference returns parsed `lines` and full `raw_text`.
4. When enabled and configured, the existing text LLM receives the full numbered transcript and extracts purchase rows and supported abbreviation expansions. It does not see the receipt image.
5. Validation checks source row ownership, printed names and numeric evidence. Invalid output, timeout or absent text uses the parser drafts. Input limits remain 24,000 characters and 200 nonblank rows.
6. Valid LLM item drafts feed the existing receipt-label cleanup, abbreviation expansion and RapidFuzz catalogue matcher. There is no independent reader-comparison or conflict override step.
7. Non-food classification and the existing unresolved-label LLM fallback remain in both processing paths. User confirmation controls pantry writes.
8. The review page shows a catalogue food name or `Cannot be matched`. Food replacement updates the existing row while retaining its identity, amount fields and order.

Validation also rejects LLM output that excludes a product recovered by the deterministic parser. Both worker and inline extraction use the shared full-text extractor. LLM source row IDs ground extraction; they are not persisted receipt UUID IDs.

Source: `packages/receipt_full_text_llm.py`, `packages/receipt_matching/__init__.py`, `services/inference/app/paddle_receipt_parser.py`, `services/api/app/services/receipt_extraction.py`, `scripts/receipt_tasks.py` and `apps/mobile/src/services/receiptReviewRows.ts`.

## Runtime and deployment

The API dispatches queued receipt extraction when a Redis broker is configured; otherwise it has an inline fallback. The inference service provides `/receipt/extract`. Deploy API and worker with matching extraction packages and ensure inference returns the full transcript. Deploy API and mobile together for the new recipe total field; the mobile fallback supports older responses.

Server-side configuration includes `INFERENCE_URL`, `REDIS_URL` for queued execution, and the existing `LLM_ENABLED`, `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL` and `LLM_TIMEOUT_S`. Full-transcript extraction requests temperature zero, at most 4,096 output tokens and a timeout capped at 30 seconds or the configured lower limit. Classification and label normalisation have their own smaller budgets.

Mobile public variables include `EXPO_PUBLIC_API_BASE_URL` and the optional `EXPO_PUBLIC_ASSET_BASE_URL`. Provider credentials and database connection strings remain server-side.

## Validation and limitations

The latest targeted OCR regression run passed 27 tests: seven full-text extraction/integration tests and 20 inference tests. These used mocked LLM responses and did not make live provider calls or use application database fixtures. They verify behaviour, not real receipt accuracy. Real-receipt benchmarking remains required.

Run from the repository root in a Python environment with project dependencies:

```bash
python -m unittest tests.test_receipt_full_text_llm
python -m pytest services/inference/tests --confcutdir=services/inference -q -p no:cacheprovider
python -m unittest tests.epic5.test_recipe_pantry_ranking
```

Run from `apps/mobile`:

```bash
node src/services/recipeIngredientBadge.test.mjs
node src/services/recipePantry.test.mjs
node src/services/receiptReviewRows.test.mjs
npm run typecheck
```

The full backend suite uses destructive fixtures: run it only against a dedicated local or CI database with migrations applied. Never target Railway or another shared deployment database.

For receipt acceptance evidence, use labelled real receipts and record missing/extra purchase rows, correct food links, price and quantity accuracy, false matches, latency and provider cost. Text LLM interpretation cannot recover text that OCR never recognised. A number appearing in source text does not alone prove that it was assigned to the correct field. LLM interpretation and non-food classification can also retain or remove incorrect interpretations; these require real examples to evaluate.
