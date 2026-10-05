import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from packages.receipt_full_text_llm import refine_ocr_output


class FullTextReceiptTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_llm_items_feed_matcher_without_reader_comparison(self):
        from packages.receipt_matching import match_text_candidates
        data = {'raw_text': 'AYAM 8.90', 'lines': [{'name': 'AYAM', 'source_row_ids': [1]}]}
        async def complete(*args):
            return json.dumps({'items': [{'source_row_ids': [1], 'printed_name': 'AYAM',
                'normalised_name': 'chicken', 'qty': None, 'unit': None, 'price_rm': 8.9}],
                'excluded_row_ids': []})
        with patch('packages.receipt_full_text_llm.log.warning') as warning:
            result = await refine_ocr_output(data, complete)
        self.assertEqual(len(result), 1)
        self.assertIn('expanded_name', result[0],
                      f'Valid extraction fell back: {warning.call_args_list}')
        self.assertEqual(result[0]['expanded_name'], 'chicken')
        self.assertNotIn('_parser_line', result[0])
        self.assertNotIn('_llm_line', result[0])
        food_id, _, _ = match_text_candidates([result[0]['name'], result[0]['expanded_name']], [('chicken', 'chicken')])
        self.assertEqual(food_id, 'chicken')

    async def test_full_text_recovers_split_item_before_matching(self):
        data = {'raw_text': 'SHOP\nAYAM B/LESS\n0.500 kg 8.90\nTOTAL 8.90', 'lines': []}
        async def complete(system, user):
            self.assertIn('AYAM B/LESS', user)
            self.assertIn('TOTAL 8.90', user)
            return json.dumps({'items': [{'source_row_ids': [2, 3], 'printed_name': 'AYAM B/LESS',
                'normalised_name': 'boneless chicken', 'qty': 0.5, 'unit': 'kg', 'price_rm': 8.9}],
                'excluded_row_ids': [1, 4]})
        result = await refine_ocr_output(data, complete)
        self.assertEqual(result[0]['name'], 'AYAM B/LESS')
        self.assertEqual(result[0]['expanded_name'], 'boneless chicken')
        self.assertEqual(result[0]['qty'], 0.5)

    async def test_repeated_purchases_remain_separate_and_in_receipt_order(self):
        data = {'raw_text': 'CHICKEN 8.90\nCHICKEN 8.90', 'lines': []}
        async def complete(*args):
            return json.dumps({'items': [{'source_row_ids': [row], 'printed_name': 'CHICKEN',
                'normalised_name': 'chicken', 'qty': None, 'unit': None, 'price_rm': 8.9}
                for row in [2, 1]], 'excluded_row_ids': []})
        result = await refine_ocr_output(data, complete)
        self.assertEqual([item['source_row_ids'] for item in result], [[1], [2]])

    async def test_bad_outputs_and_timeouts_fall_back(self):
        data = {'raw_text': 'CHICKEN 8.90', 'lines': [{'name': 'CHICKEN', 'price_rm': 8.9}]}
        for response in [None, 'not json', json.dumps({'items': [], 'excluded_row_ids': [1]}),
                         json.dumps({'items': [{'source_row_ids': [99]}], 'excluded_row_ids': []})]:
            async def complete(*args):
                return response
            self.assertEqual(await refine_ocr_output(data, complete), data['lines'])
        async def timeout(*args):
            raise TimeoutError()
        self.assertEqual(await refine_ocr_output(data, timeout), data['lines'])

    async def test_invented_price_and_duplicate_source_rows_are_rejected(self):
        data = {'raw_text': 'CHICKEN 8.90', 'lines': [{'name': 'CHICKEN'}]}
        for price, ids in [(99, [1]), (8.9, [1, 1])]:
            async def complete(*args):
                return json.dumps({'items': [{'source_row_ids': ids, 'printed_name': 'CHICKEN',
                    'normalised_name': 'chicken', 'qty': None, 'unit': None, 'price_rm': price}], 'excluded_row_ids': []})
            self.assertEqual(await refine_ocr_output(data, complete), data['lines'])

    async def test_missing_raw_text_uses_existing_parser_without_llm_call(self):
        async def complete(*args):
            self.fail('LLM should not be called')
        self.assertEqual(await refine_ocr_output({'lines': [{'name': 'egg'}]}, complete), [{'name': 'egg'}])

    async def test_rejection_reports_guard_without_receipt_contents(self):
        data = {'raw_text': 'CHICKEN 8.90', 'lines': [{'name': 'CHICKEN'}]}
        async def complete(*args):
            return json.dumps({'items': [{'source_row_ids': [1], 'printed_name': 'CHICKEN',
                'normalised_name': 'chicken', 'qty': None, 'unit': None, 'price_rm': 99}],
                'excluded_row_ids': []})
        with patch('packages.receipt_full_text_llm.log.warning') as warning:
            self.assertEqual(await refine_ocr_output(data, complete), data['lines'])
        warning.assert_called_once_with(
            'Full receipt LLM extraction rejected (%s); using OCR parser fallback',
            'amount absent from source')

    async def test_shared_pipeline_uses_local_parser_until_paid_adapter_is_budgeted(self):
        from services.api.app.services import receipt_extraction as inline
        from scripts import receipt_tasks as worker
        data = {'raw_text': 'CHICKEN 8.90', 'lines': [{'name': 'CHICKEN', 'source_row_ids': [1]}]}
        response = Mock()
        response.json.return_value = data
        settings = SimpleNamespace(inference_url='http://unused', llm_timeout_s=30)
        with patch.object(inline, 'get_settings', return_value=settings), \
             patch.object(inline, '_post_with_busy_retry', AsyncMock(return_value=response)):
            result = await inline._extract_lines(Mock(), 'image')
            self.assertEqual(result, data['lines'])

        with patch.object(worker, 'run_extraction', AsyncMock()) as shared:
            await worker.process_receipt('00000000-0000-0000-0000-000000000001')
            shared.assert_awaited_once_with('00000000-0000-0000-0000-000000000001')
