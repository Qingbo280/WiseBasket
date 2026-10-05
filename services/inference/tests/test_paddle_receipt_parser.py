"""TDD contracts for deterministic parsing of PaddleOCR text boxes."""

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.paddle_receipt_parser import (  # noqa: E402
    extract_receipt_identity,
    order_ocr_tokens,
    parse_receipt_lines,
)


def test_order_ocr_tokens_reads_rows_top_to_bottom_then_left_to_right():
    tokens = [
        {"text": "1.38", "box": [180, 100, 220, 120]},
        {"text": "BAWANG MERAH", "box": [10, 100, 150, 120]},
        {"text": "PASAR RAYA", "box": [10, 20, 150, 40]},
    ]

    assert order_ocr_tokens(tokens) == ["PASAR RAYA", "BAWANG MERAH 1.38"]


def test_order_ocr_tokens_compensates_for_a_slanted_receipt_row():
    # Each detected word slopes 0.1 px down for every px to the right. Without
    # geometry compensation the price is 18 px below its description and is
    # incorrectly treated as the next OCR row.
    tokens = [
        {
            "text": "1.38",
            "box": [180, 118, 220, 138],
            "polygon": [[180, 118], [220, 122], [220, 142], [180, 138]],
        },
        {
            "text": "BAWANG MER",
            "box": [10, 101, 150, 121],
            "polygon": [[10, 101], [150, 115], [150, 135], [10, 121]],
        },
        {
            "text": "FARM FRESH",
            "box": [10, 141, 150, 161],
            "polygon": [[10, 141], [150, 155], [150, 175], [10, 161]],
        },
        {
            "text": "4.15",
            "box": [180, 158, 220, 178],
            "polygon": [[180, 158], [220, 162], [220, 182], [180, 178]],
        },
    ]

    assert order_ocr_tokens(tokens) == ["BAWANG MER 1.38", "FARM FRESH 4.15"]


def test_parse_receipt_lines_extracts_name_quantity_unit_and_price():
    ocr_rows = ["BAWANG MERAH 1.38", "BERAS 5 KG 15.50"]

    lines = parse_receipt_lines(ocr_rows)

    assert [(line.name, line.qty, line.unit, line.price_rm) for line in lines] == [
        ("BAWANG MERAH", None, None, 1.38),
        ("BERAS", 5.0, "kg", 15.5),
    ]


def test_printed_gm_unit_is_grams_and_ambiguous_compact_multipack_remains_in_label():
    lines = parse_receipt_lines(["HORLICKS 32GM 4.50", "OTHER NOODLES5PX425G 15.90"])
    assert (lines[0].name, lines[0].qty, lines[0].unit) == ("HORLICKS", 32.0, "g")
    assert (lines[1].name, lines[1].qty, lines[1].unit) == ("OTHER NOODLES5PX425G", None, None)


def test_parse_receipt_lines_excludes_totals_and_non_food_rows():
    ocr_rows = [
        "AYAM 12.50",
        "PLASTIC BAG 0.20",
        "TOTAL 12.70",
        "CASH 20.00",
        "MYDEBIT 12.70",
        "Rounding 0.02",
    ]

    lines = parse_receipt_lines(ocr_rows)

    assert [line.name for line in lines] == ["AYAM"]


def test_tax_and_membership_charges_are_not_groceries_but_similar_foods_survive():
    rows = [
        "GST 6% 1.50", "SST TAX 0.80", "GST 1.50", "SST 0.80",
        "MEMBERSHIP FEE 2.00", "EARTH AMBASSADOR PP HOVEN BAG 5.00",
        "SERVICE CHARGE 0.50", "FP Group app $ 25.05",
        "Paid by VISAxxxx 25.05", "Paid by CASH 25.05",
        "Paid by Mastercard 25.05", "Paid by QR 25.05",
        "Payment via TNG 25.05", "Eligible: Union/FP mbr benefit 0.00",
        "GST BRAND RICE 4.00", "SST CHILLI 1.20",
        "BEAN SPROUT CLEANED 0.77",
    ]
    assert [(line.name, line.price_rm) for line in parse_receipt_lines(rows)] == [
        ("GST BRAND RICE", 4.0), ("SST CHILLI", 1.2),
        ("BEAN SPROUT CLEANED", 0.77),
    ]


def test_real_receipt_tax_suffix_and_quantity_multiplier_keep_item_names():
    rows = [
        "2090104CHICKFILLET 6.34 2", "4145763 FARM TABLE EGG A30S 9.29 2",
        "DL KANGKUNG 3OUG", "2 pktx 4.50 9.00 Z",
        "Barcode: 9557337800106", "SUNGLO GREEK YOGURT unit 7.95 5Z",
        "ABF CHICKEN DRUMSTIC", "0.556 kg x 20.50 11.40Z",
        "WECHATCB - 77.10", "0 77.08 0.00 77.08",
    ]
    lines = parse_receipt_lines(rows)
    assert [(line.name, line.price_rm) for line in lines] == [
        ("CHICKFILLET", 6.34), ("FARM TABLE EGG A30S", 9.29),
        ("DL KANGKUNG 3OUG", 9.0), ("SUNGLO GREEK YOGURT unit", 7.95),
        ("ABF CHICKEN DRUMSTIC", 11.4),
    ]
    assert (lines[2].qty, lines[2].unit) == (2.0, "pkt")
    assert (lines[4].qty, lines[4].unit) == (0.556, "kg")


def test_private_receipt_identity_requires_unambiguous_header_and_total():
    rows = [
        "PASAR RAYA MAJU", "RECEIPT NO: R-2048", "DATE 23/09/2026 TIME 12:17",
        "AYAM 12.50", "BAWANG MERAH 1.38", "SUBTOTAL 13.88",
        "GST 6% 0.83", "GRAND TOTAL 14.71", "CASH 20.00",
    ]
    identity = extract_receipt_identity(rows)
    assert identity is not None
    assert identity.model_dump() == {
        "merchant": "PASAR RAYA MAJU", "date": "2026-09-23", "time": "12:17:00",
        "receipt_number": "R-2048", "total": "14.71",
    }
    assert extract_receipt_identity([row for row in rows if "RECEIPT NO" not in row]) is None
    assert extract_receipt_identity(rows + ["TOTAL 99.99"]) is None
    assert extract_receipt_identity(rows + ["TRANSACTION NO: Z-9999"]) is None


def test_private_receipt_identity_does_not_use_payment_card_as_receipt_number():
    rows = [
        "MYDIN", "DATE: 2026-09-23", "TIME: 08:01:02", "VISA CARD 4111111111111111",
        "CHICK FILLET 6.34", "TOTAL 6.34",
    ]
    assert extract_receipt_identity(rows) is None


def test_private_receipt_identity_does_not_use_invoice_date_as_number():
    rows = [
        "STORE NAME", "Invoice 25/09/2026", "Time 12:00", "RICE 2.00", "Total 2.00",
    ]
    assert extract_receipt_identity(rows) is None


def test_parse_receipt_lines_excludes_lotus_payment_and_loyalty_footer_rows():
    ocr_rows = [
        "02125600001382 BAWANG MER 1.38",
        "09555487800977 FARM FRESH 4.15",
        "TOTAL 17.92",
        "MYDEBIT 17.90",
        "Auth Code=442922 17.90",
        "MY LOTUS'S POINTS MISSED : 17",
        "SIGN UP NOW FOR SAVINGS",
        "THANK-YOU FOR SHOPPING AT LOTUS'S",
    ]

    lines = parse_receipt_lines(ocr_rows)

    assert [(line.name, line.price_rm) for line in lines] == [
        ("BAWANG MER", 1.38),
        ("FARM FRESH", 4.15),
    ]


def test_parse_receipt_lines_removes_leading_barcodes_from_product_names():
    ocr_rows = [
        "02125600001382 BAWANG MER 1.38",
        "09555487800977FARMFRESH 4.15",
    ]

    lines = parse_receipt_lines(ocr_rows)

    assert [(line.name, line.price_rm) for line in lines] == [
        ("BAWANG MER", 1.38),
        ("FARMFRESH", 4.15),
    ]


def test_parse_receipt_lines_removes_short_barcode_and_excludes_payment_and_tax_rows():
    ocr_rows = [
        "4051814 S0MMERSET C0TTAGE 4.45",
        "isa Card 25.05",
        "6% 4.20 0.25",
        "0% 20.59 0.00",
    ]

    lines = parse_receipt_lines(ocr_rows)

    assert [(line.name, line.price_rm) for line in lines] == [
        ("S0MMERSET C0TTAGE", 4.45),
    ]


def test_parse_receipt_lines_accepts_store_category_code_after_price():
    ocr_rows = [
        "2001794 MORIS PINEAPPLE PC 1.59 Z",
        "2001806 JOSAPINE PINEAPLE PC 1.59 Z",
        "2011583 BEAN SPROUT CLEANED 0.77 Z",
        "2021606 RED CHILLI KG 1.01 Z",
        "2090104 CHICK FILLET 6.34 Z",
        "4051814 SOMMERSET COTTAGE 4.45 S",
        "4145763 FARM TABLE EGG A30S 9.29 Z",
    ]

    lines = parse_receipt_lines(ocr_rows)

    assert [(line.name, line.price_rm) for line in lines] == [
        ("MORIS PINEAPPLE PC", 1.59),
        ("JOSAPINE PINEAPLE PC", 1.59),
        ("BEAN SPROUT CLEANED", 0.77),
        ("RED CHILLI KG", 1.01),
        ("CHICK FILLET", 6.34),
        ("SOMMERSET COTTAGE", 4.45),
        ("FARM TABLE EGG A30S", 9.29),
    ]
    assert lines[3].qty is None and lines[3].unit is None  # KG is a price basis, not 1kg


def test_product_names_containing_total_and_discount_remain_purchases():
    rows = ["TOTAL GRAIN CEREAL 500G 7.00", "MILK TOTAL NUTRITION 4.00",
            "DISCOUNT COOKIES 3.00", "TOTAL 14.00"]
    assert [line.name for line in parse_receipt_lines(rows)] == [
        "TOTAL GRAIN CEREAL", "MILK TOTAL NUTRITION", "DISCOUNT COOKIES",
    ]


def test_parse_receipt_lines_pairs_product_name_with_following_barcode_price_row():
    ocr_rows = [
        "JAYA GROCER",
        "NISSIN CHICKEN RAMEN 5PX425G*1",
        "4902105051108UNIT 1x28.21 28.21",
        "ARNOTTS ORANGE SLICE 250G *1",
        "9310072001708 UNI1 1Ã10.30 10.30",
        "Item 23 SubTotal 343.41",
        "Saving 0.00 Rounding -0.01",
        "Total 343.40",
        "Amex 343.40",
    ]

    lines = parse_receipt_lines(ocr_rows)

    assert [(line.name, line.qty, line.unit, line.price_rm) for line in lines] == [
        ("NISSIN CHICKEN RAMEN 5PX425G", 1.0, "pcs", 28.21),
        ("ARNOTTS ORANGE SLICE 250G", 1.0, "pcs", 10.3),
    ]


def test_same_row_package_size_and_outer_pack_count_are_private_total_mass():
    from decimal import Decimal
    from packages.receipt_purchase_rules import ground_purchase_quantity

    line = parse_receipt_lines(["DL KANGKUNG 300G 2 pkt 9.00"])[0]
    assert (line.name, line.qty, line.unit, line.price_rm) == ("DL KANGKUNG", 600, "g", 9)
    private = [{"name": line.name, "qty": line.qty, "unit": line.unit, "price_rm": line.price_rm}]
    assert ground_purchase_quantity("DL KANGKUNG 300G", 1, None, 9, private) == (Decimal("0.6"), "kg")
    assert ground_purchase_quantity("DL KANGKUNG 300G 2 pkt", 0.6, "kg", 9, private) == (Decimal("0.6"), "kg")


def test_parse_receipt_lines_pairs_barcode_price_with_following_name_and_discount():
    ocr_rows = [
        "1x9555897602702 EARTH AMBASSADOR PP HOVEN BAG 5.00",
        "1x2280409000902 0.90",
        "LEMON GRASS(E.T)",
        "1Ã2000043066658 3.90",
        "SM BAYAM RED/GREEN ORG",
        "1x2261710050077 50.07",
        "FRZ OX TAIL",
        "DISC 50%@25.04 -25.03",
        "1x2261710048371 48.37",
        "FRZ OX TAIL",
        "DISC 50%24.19 -24.18",
        "Sub-total 93.23",
        "Total Sales INCL SVC TAX 93.25",
        "MasterCard 93.25",
    ]

    lines = parse_receipt_lines(ocr_rows)

    assert [(line.name, line.qty, line.unit, line.price_rm) for line in lines] == [
        # The plastic bag is a non-food purchase, not pantry stock.
        ("LEMON GRASS(E.T)", 1.0, "pcs", 0.9),
        ("SM BAYAM RED/GREEN ORG", 1.0, "pcs", 3.9),
        ("FRZ OX TAIL", 1.0, "pcs", 25.04),
        ("FRZ OX TAIL", 1.0, "pcs", 24.19),
    ]


# --- 2026-10-02: Jaya Grocer weighed-item rows, noise rows, strict identity ---

JAYA_GROCER_ROWS = [
    "JAYA GROCER",
    "Trendcell Sdn Bhd (544047-T)",
    "D-01-01, BLOCK D, SUNWAY GEO AVENUE,",
    "TEL:03-56119735",
    "Invoice No : JGSG2626019002345",
    "113450(NORAINI) 345",
    "002 17/09/2026 19:11:31",
    "QL DELI FRESH EGGS 15'S *1",
    "9557240612681 UNIT 1x11.70 11.70",
    "PEAR-GOLDEN 2S (CHN)C10",
    "9551004480530 UNIT 1x8.90 8.90",
    "AQINA CHIKEN BONELESS THIGH ABF",
    "2107369001097 KG 0.444x24.70 10.97",
    "2107369001126KG 0.456x24.70 11.26",
    "G/GARDEN CHERRY TOMATO-HONEY 275G P15",
    "9555658700037 UNIT 1x7.00 7.00",
    "08 5.90 -1.10",
    "Item 4 SubTotal 48.73",
    "Qty 3.9 Spec.Disc 0.00",
    "Saving 1.10 Rounding 0.02",
    "Total 48.75",
    "(54567149****9108) MASTER 48.75",
    "ApproCode R37187",
    "Change 0.00",
    "Member No : 4c883b448933347d",
    "Grab Member Validated",
    "17/09/2026 19:11:31",
]


def test_weighed_item_barcode_is_product_code_never_quantity():
    lines = parse_receipt_lines(JAYA_GROCER_ROWS)
    chicken = [line for line in lines if "CHIKEN" in line.name]
    # Both weighed purchases survive; the 13-digit in-store code (GS1 prefix
    # 21) is not a quantity, the weight x unit-price pair is.
    assert [(line.qty, line.unit, line.price_rm) for line in chicken] == [
        (0.444, "kg", 10.97),
        (0.456, "kg", 11.26),
    ]


def test_summary_and_masked_card_rows_never_become_items():
    lines = parse_receipt_lines(JAYA_GROCER_ROWS)
    names = [line.name for line in lines]
    assert names == [
        "QL DELI FRESH EGGS 15'S",
        "PEAR-GOLDEN 2S (CHN)C10",
        "AQINA CHIKEN BONELESS THIGH ABF",
        "AQINA CHIKEN BONELESS THIGH ABF",
        "G/GARDEN CHERRY TOMATO-HONEY 275G P15",
    ]
    assert all("SubTotal" not in name and "MASTER" not in name for name in names)


def test_alphanumeric_invoice_number_is_a_stable_receipt_identity():
    identity = extract_receipt_identity(JAYA_GROCER_ROWS)
    assert identity is not None
    assert identity.merchant == "JAYA GROCER"
    assert identity.receipt_number == "JGSG2626019002345"
    assert identity.date == "2026-09-17"
    assert identity.time == "19:11:31"
    assert identity.total == "48.75"


def test_pure_digit_long_number_is_still_not_a_receipt_number():
    rows = [
        "PASAR RAYA MAJU", "RECEIPT NO: 9557240612681", "23/09/2026 12:17",
        "AYAM 12.50", "BAWANG MERAH 1.38", "TOTAL 13.88",
    ]
    identity = extract_receipt_identity(rows)
    # A barcode-like pure number disables dedup identity rather than inventing one.
    assert identity is None


def test_glued_date_time_rows_still_yield_identity():
    # Paddle may glue the time straight onto the year ("17/09/202619:11:31");
    # identity extraction must survive that shape.
    rows = [
        row.replace("17/09/2026 19:11:31", "17/09/202619:11:31")
        for row in JAYA_GROCER_ROWS
    ]
    identity = extract_receipt_identity(rows)
    assert identity is not None
    assert identity.date == "2026-09-17"
    assert identity.time == "19:11:31"
    assert identity.receipt_number == "JGSG2626019002345"
