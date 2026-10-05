"""Synthetic pixels only: no real receipt or sensitive text leaves this test."""

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import receipt_redaction, receipt_service  # noqa: E402


def _image() -> bytes:
    ok, encoded = cv2.imencode(".jpg", np.full((220, 420, 3), 255, dtype=np.uint8))
    assert ok
    return encoded.tobytes()


def test_redaction_returns_strict_identity_privately_but_masks_header_pixels(monkeypatch):
    monkeypatch.setattr(receipt_redaction, "_verify_masked", lambda *args: None)
    monkeypatch.setattr(receipt_redaction, "_machine_code_boxes", lambda _: [])
    rows = [
        "PASAR RAYA MAJU", "RECEIPT NO: R-2048", "23/09/2026 12:17",
        "AYAM 12.50", "BAWANG MERAH 1.38", "TOTAL 13.88",
    ]
    monkeypatch.setattr(receipt_redaction, "extract_paddle_tokens", lambda _: [
        {"text": row, "box": [10, 10 + index * 30, 260, 28 + index * 30]}
        for index, row in enumerate(rows)
    ])

    result = receipt_redaction.redact_receipt(_image())

    assert result.identity is not None
    assert result.identity.receipt_number == "R-2048"
    assert [line["name"] for line in result.purchase_lines] == ["AYAM", "BAWANG MERAH"]
    assert all("RECEIPT" not in line["name"] and "TOTAL" not in line["name"] for line in result.purchase_lines)
    pixels = cv2.imdecode(np.frombuffer(result.image_bytes, np.uint8), cv2.IMREAD_COLOR)
    assert pixels[45, 40].min() > 240  # header is white on cloud-bound pixels
    assert pixels[180, 40].min() > 240  # total/footer is also white


def test_redaction_masks_whole_context_row_and_phone(monkeypatch):
    monkeypatch.setattr(receipt_redaction, "_item_band", lambda rows, height: (0, height, []))
    monkeypatch.setattr(receipt_redaction, "_verify_masked", lambda *args: None)
    monkeypatch.setattr(receipt_redaction, "extract_paddle_tokens", lambda _: [
        {"text": "NAME", "box": [10, 30, 80, 50]},
        {"text": "EXAMPLE PERSON", "box": [85, 30, 260, 50]},
        {"text": "012-3456789", "box": [10, 75, 175, 95]},
    ])
    monkeypatch.setattr(receipt_redaction, "_machine_code_boxes", lambda _: [])
    result = receipt_redaction.redact_receipt(_image())
    decoded = cv2.imdecode(np.frombuffer(result.image_bytes, np.uint8), cv2.IMREAD_COLOR)
    assert result.mask_counts == {"phone": 1, "long_number": 0, "context": 1, "machine_code": 0}
    assert decoded[40, 110].max() < 10  # person's value, not just NAME label
    assert decoded[85, 90].max() < 10
    assert decoded[180, 300].min() > 240


def test_private_purchase_evidence_retains_weighted_and_pack_continuations(monkeypatch):
    from packages.receipt_purchase_rules import ground_purchase_quantity
    from decimal import Decimal

    monkeypatch.setattr(receipt_redaction, "_verify_masked", lambda *args: None)
    monkeypatch.setattr(receipt_redaction, "_machine_code_boxes", lambda _: [])
    texts = ["SHOP", "ABF CHICKEN DRUMSTIC", "0.556 kg x 20.50 11.40Z",
             "DL KANGKUNG 3OUG", "2 pktx 4.50 9.00 Z", "TOTAL 20.40"]
    monkeypatch.setattr(receipt_redaction, "extract_paddle_tokens", lambda _: [
        {"text": row, "box": [10, 10 + index * 30, 300, 28 + index * 30]}
        for index, row in enumerate(texts)
    ])
    evidence = receipt_redaction.redact_receipt(_image()).purchase_lines
    assert len(evidence) == 2
    assert ground_purchase_quantity("ABF CHICKEN DRUMSTIC", 1, "kg", 11.40, evidence) == (Decimal("0.556"), "kg")
    assert ground_purchase_quantity("DL KANGKUNG 300G", 1, None, 9, evidence) == (Decimal("0.600"), "kg")


def test_sensitive_token_without_coordinates_fails_closed(monkeypatch):
    monkeypatch.setattr(receipt_redaction, "extract_paddle_tokens", lambda _: [
        {"text": "0123456789", "box": []},
    ])
    monkeypatch.setattr(receipt_redaction, "_machine_code_boxes", lambda _: [])
    with pytest.raises(receipt_redaction.RedactionError):
        receipt_redaction.redact_receipt(_image())


def test_empty_ocr_and_zero_area_box_fail_closed(monkeypatch):
    monkeypatch.setattr(receipt_redaction, "_machine_code_boxes", lambda _: [])
    monkeypatch.setattr(receipt_redaction, "extract_paddle_tokens", lambda _: [])
    with pytest.raises(receipt_redaction.RedactionError, match="could not be checked"):
        receipt_redaction.redact_receipt(_image())
    monkeypatch.setattr(receipt_redaction, "extract_paddle_tokens", lambda _: [
        {"text": "STAFF EXAMPLE PERSON", "box": [0, 0, 0, 0]},
    ])
    with pytest.raises(receipt_redaction.RedactionError, match="location"):
        receipt_redaction.redact_receipt(_image())


def test_staff_and_landline_are_masked_but_public_ean_is_not(monkeypatch):
    monkeypatch.setattr(receipt_redaction, "_item_band", lambda rows, height: (0, height, []))
    monkeypatch.setattr(receipt_redaction, "_verify_masked", lambda *args: None)
    monkeypatch.setattr(receipt_redaction, "extract_paddle_tokens", lambda _: [
        {"text": "STAFF EXAMPLE PERSON", "box": [10, 20, 260, 40]},
        {"text": "TEL 03-1234 5678", "box": [10, 60, 250, 80]},
        {"text": "RICE 2.00", "box": [10, 110, 200, 130]},
        {"text": "9557305000262", "box": [10, 150, 200, 170]},
    ])
    monkeypatch.setattr(receipt_redaction, "_machine_code_boxes", lambda _: [])
    result = receipt_redaction.redact_receipt(_image())
    decoded = cv2.imdecode(np.frombuffer(result.image_bytes, np.uint8), cv2.IMREAD_COLOR)
    assert result.mask_counts == {"phone": 1, "long_number": 0, "context": 1, "machine_code": 0}
    assert decoded[30, 100].max() < 10
    assert decoded[70, 100].max() < 10
    assert decoded[120, 100].min() > 240
    assert decoded[160, 100].min() > 240


def test_enhanced_profile_repeats_ocr_and_never_reuses_normal_boxes(monkeypatch):
    monkeypatch.setattr(receipt_redaction, "_item_band", lambda rows, height: (0, height, []))
    monkeypatch.setattr(receipt_redaction, "_verify_masked", lambda *args: None)
    calls = []

    def tokens(image):
        calls.append(image)
        box = [10, 30, 80, 50] if len(calls) == 1 else [180, 130, 250, 150]
        return [{"text": "NAME", "box": box}]

    monkeypatch.setattr(receipt_redaction, "extract_paddle_tokens", tokens)
    monkeypatch.setattr(receipt_redaction, "_machine_code_boxes", lambda _: [])
    receipt_redaction.redact_receipt(_image(), "normal")
    result = receipt_redaction.redact_receipt(_image(), "enhanced")
    decoded = cv2.imdecode(np.frombuffer(result.image_bytes, np.uint8), cv2.IMREAD_COLOR)
    assert len(calls) == 2
    assert decoded[140, 210].max() < 10
    assert decoded[40, 30].min() > 240


def test_bad_image_fails_closed():
    with pytest.raises(receipt_redaction.RedactionError):
        receipt_redaction.redact_receipt(b"not an image")


def test_qr_region_is_detected_and_masked(monkeypatch):
    monkeypatch.setattr(receipt_redaction, "_item_band", lambda rows, height: (0, height, []))
    monkeypatch.setattr(receipt_redaction, "_verify_masked", lambda *args: None)
    qr = cv2.QRCodeEncoder_create().encode("synthetic-example")
    qr = cv2.resize(qr, (160, 160), interpolation=cv2.INTER_NEAREST)
    image = np.full((240, 240, 3), 255, dtype=np.uint8)
    image[40:200, 40:200] = cv2.cvtColor(qr, cv2.COLOR_GRAY2BGR)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    monkeypatch.setattr(receipt_redaction, "extract_paddle_tokens", lambda _: [
        {"text": "RICE 2.00", "box": [10, 10, 120, 30]},
    ])
    result = receipt_redaction.redact_receipt(encoded.tobytes())
    decoded = cv2.imdecode(np.frombuffer(result.image_bytes, np.uint8), cv2.IMREAD_COLOR)
    assert result.mask_counts["machine_code"] >= 1
    assert decoded[100, 100].max() < 10
    assert decoded[10, 10].min() > 240


def test_item_band_removes_header_and_payment_footer(monkeypatch):
    monkeypatch.setattr(receipt_redaction, "_verify_masked", lambda *args: None)
    monkeypatch.setattr(receipt_redaction, "extract_paddle_tokens", lambda _: [
        {"text": "STAFF EXAMPLE PERSON", "box": [10, 10, 200, 30]},
        {"text": "RICE 2.00", "box": [10, 60, 200, 80]},
        {"text": "EGG 3.00", "box": [10, 90, 200, 110]},
        {"text": "TOTAL 5.00", "box": [10, 130, 200, 150]},
        {"text": "CARD NO 4111", "box": [10, 170, 200, 190]},
    ])
    monkeypatch.setattr(receipt_redaction, "_machine_code_boxes", lambda _: [])
    image = np.full((220, 420, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (250, 15), (270, 25), (0, 0, 0), -1)
    cv2.rectangle(image, (250, 65), (270, 75), (0, 0, 0), -1)
    cv2.rectangle(image, (250, 175), (270, 185), (0, 0, 0), -1)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    result = receipt_redaction.redact_receipt(encoded.tobytes())
    decoded = cv2.imdecode(np.frombuffer(result.image_bytes, np.uint8), cv2.IMREAD_COLOR)
    assert decoded[20, 260].min() > 240
    assert decoded[70, 260].max() < 30
    assert decoded[180, 260].min() > 240


def test_missing_item_or_summary_boundary_fails_closed(monkeypatch):
    monkeypatch.setattr(receipt_redaction, "extract_paddle_tokens", lambda _: [
        {"text": "RICE 2.00", "box": [10, 60, 200, 80]},
        {"text": "EGG 3.00", "box": [10, 90, 200, 110]},
    ])
    monkeypatch.setattr(receipt_redaction, "_machine_code_boxes", lambda _: [])
    with pytest.raises(receipt_redaction.RedactionError, match="boundary"):
        receipt_redaction.redact_receipt(_image())


def test_secondary_ocr_rejects_residual_staff_or_payment_identifier(monkeypatch):
    monkeypatch.setattr(receipt_redaction, "extract_paddle_tokens", lambda _: [
        {"text": "STAFF EXAMPLE PERSON", "box": [10, 20, 260, 40]},
    ])
    with pytest.raises(receipt_redaction.RedactionError, match="retain sensitive"):
        receipt_redaction._verify_masked(_image(), 420, 220)


def test_paddle_ocr_does_not_silently_drop_text_without_location(monkeypatch):
    class PartialBoxes:
        def predict(self, _path):
            return [{"res": {
                "rec_texts": ["RICE 2.00", "STAFF EXAMPLE PERSON"],
                "rec_boxes": [[10, 10, 120, 30]],
            }}]

    monkeypatch.setattr(receipt_service, "load_paddle_ocr", lambda: PartialBoxes())
    with pytest.raises(ValueError, match="counts differ"):
        receipt_service.extract_paddle_tokens(_image())


@pytest.mark.parametrize("box", [[], [0, 0, 0, 0], [0, 0, float("nan"), 10]])
def test_paddle_ocr_rejects_invalid_text_geometry(box):
    with pytest.raises(ValueError, match="invalid text location"):
        receipt_service.bounding_box(box)


def test_instore_variable_code_is_public_product_data(monkeypatch):
    assert receipt_redaction._is_instore_variable_code("2107369001126") is True
    assert receipt_redaction._is_instore_variable_code("210736900112") is False  # 12 digits
    assert receipt_redaction._is_instore_variable_code("9557240612681") is False  # prefix 95


def test_instore_variable_code_is_not_masked_but_luhn_twin_is(monkeypatch):
    """GS1 prefix-2 in-store codes stay visible; a payment-card-shaped
    13-digit value sharing the prefix is still masked (fail closed)."""
    monkeypatch.setattr(receipt_redaction, "_item_band", lambda rows, height: (0, height, []))
    monkeypatch.setattr(receipt_redaction, "_verify_masked", lambda *args: None)
    monkeypatch.setattr(receipt_redaction, "_machine_code_boxes", lambda _: [])
    monkeypatch.setattr(receipt_redaction, "extract_paddle_tokens", lambda _: [
        {"text": "2107369001126", "box": [10, 30, 200, 50]},
        {"text": "2107369001129", "box": [10, 70, 200, 90]},
    ])
    result = receipt_redaction.redact_receipt(_image())
    decoded = cv2.imdecode(np.frombuffer(result.image_bytes, np.uint8), cv2.IMREAD_COLOR)
    assert result.mask_counts["long_number"] == 1  # only the Luhn-valid twin
    assert decoded[40, 100].min() > 240  # in-store product code untouched
    assert decoded[80, 100].max() < 10  # payment-card-shaped digits masked
