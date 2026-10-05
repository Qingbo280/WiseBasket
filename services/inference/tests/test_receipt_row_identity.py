import unittest

from services.inference.app.paddle_receipt_parser import order_ocr_tokens, parse_receipt_lines


class ReceiptRowIdentityTests(unittest.TestCase):
    def test_parser_tracks_single_and_split_source_rows(self):
        lines = parse_receipt_lines(['SHOP', 'CHICKEN 8.90', 'MILK', '123456789 UNIT 1 x 4.50 4.50'])
        self.assertEqual([line.source_row_ids for line in lines], [[2], [3, 4]])

    def test_duplicate_detection_of_same_printed_line_is_removed(self):
        tokens = [
            {"text": "CHICKEN 12.50", "box": [10, 100, 200, 130]},
            {"text": "CHICKEN 12.50", "box": [11, 101, 201, 131]},
        ]
        self.assertEqual(order_ocr_tokens(tokens), ["CHICKEN 12.50"])

    def test_identical_purchases_on_distinct_printed_rows_are_kept(self):
        tokens = [
            {"text": "CHICKEN 12.50", "box": [10, 100, 200, 120]},
            {"text": "CHICKEN 12.50", "box": [10, 140, 200, 160]},
        ]
        lines = parse_receipt_lines(order_ocr_tokens(tokens))
        self.assertEqual(len(lines), 2)
        self.assertEqual([line.name for line in lines], ["CHICKEN", "CHICKEN"])

    def test_missing_geometry_does_not_justify_deleting_a_detection(self):
        self.assertEqual(order_ocr_tokens([
            {"text": "CHICKEN", "box": [0, 0, 0, 0]},
            {"text": "CHICKEN", "box": [0, 0, 0, 0]},
        ]), ["CHICKEN CHICKEN"])

    def test_unmatched_product_labels_remain_receipt_items(self):
        lines = parse_receipt_lines(["UNKNOWN PRODUCT 4.50", "CHICKEN 12.50"])
        self.assertEqual([line.name for line in lines], ["UNKNOWN PRODUCT", "CHICKEN"])
