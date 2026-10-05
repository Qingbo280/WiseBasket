import unittest

from packages.receipt_reader_comparison import compare_reader_rows, match_compared_row


class ReaderComparisonTests(unittest.TestCase):
    aliases = [('chicken', 'chicken'), ('beef', 'beef')]

    def row(self, ids, expanded=None):
        return {'name': 'ZZZ', 'source_row_ids': ids, 'expanded_name': expanded}

    def test_agreement_produces_one_food_row(self):
        rows = compare_reader_rows([self.row([1], 'chicken')], [self.row([1], 'chicken')])
        self.assertEqual(len(rows), 1)
        self.assertEqual(match_compared_row(rows[0], self.aliases)[0], 'chicken')

    def test_one_reader_recovers_unmatched_item(self):
        for parser_name, llm_name in [(None, 'chicken'), ('chicken', None)]:
            row = compare_reader_rows([self.row([1], parser_name)], [self.row([1], llm_name)])[0]
            self.assertEqual(match_compared_row(row, self.aliases)[0], 'chicken')

    def test_llm_disagreement_preserves_parser_food(self):
        row = compare_reader_rows([self.row([1], 'chicken')], [self.row([1], 'beef')])[0]
        food_id, _, candidates = match_compared_row(row, self.aliases)
        self.assertEqual(food_id, 'chicken')

    def test_repeats_and_llm_only_recovery_keep_receipt_order(self):
        rows = compare_reader_rows([self.row([1]), self.row([3])],
                                   [self.row([1]), self.row([2]), self.row([3])])
        self.assertEqual([row['source_row_ids'] for row in rows], [[1], [2], [3]])

    def test_llm_merging_two_purchases_cannot_collapse_rows(self):
        rows = compare_reader_rows([self.row([1], 'chicken'), self.row([2], 'chicken')],
                                   [self.row([1, 2], 'chicken')])
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(match_compared_row(row, self.aliases)[0] == 'chicken' for row in rows))

    def test_ambiguous_llm_merge_cannot_match_unresolved_parser_rows(self):
        rows = compare_reader_rows([self.row([1]), self.row([2])], [self.row([1, 2], 'chicken')])
        self.assertTrue(all(match_compared_row(row, self.aliases)[0] is None for row in rows))

    def test_ambiguous_llm_merge_cannot_fill_parser_quantities(self):
        rows = compare_reader_rows([self.row([1]), self.row([2])],
                                   [{**self.row([1, 2], 'chicken'), 'qty': 2, 'unit': 'kg'}])
        self.assertTrue(all(row.get('qty') is None for row in rows))

    def test_disagreement_is_logged_for_evaluation(self):
        row = compare_reader_rows([self.row([1], 'chicken')], [self.row([1], 'beef')])[0]
        with self.assertLogs('packages.receipt_reader_comparison', level='INFO') as logs:
            self.assertEqual(match_compared_row(row, self.aliases)[0], 'chicken')
        self.assertIn('disagreement', ' '.join(logs.output))

    def test_older_ocr_without_provenance_keeps_parser_fallback(self):
        parser = [{'name': 'chicken'}]
        self.assertEqual(compare_reader_rows(parser, [self.row([1])]), parser)

    def test_parser_amounts_are_preserved_and_missing_amounts_can_be_recovered(self):
        parser = {**self.row([1]), 'price_rm': 8.9, 'qty': None}
        llm = {**self.row([1]), 'price_rm': 9, 'qty': 0.5, 'unit': 'kg'}
        result = compare_reader_rows([parser], [llm])[0]
        self.assertEqual(result['price_rm'], 8.9)
        self.assertEqual(result['qty'], 0.5)
