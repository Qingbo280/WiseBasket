"""Narrow repair of barcode-price rows printed before their product names."""
from collections import defaultdict
from decimal import Decimal
import re

from packages.receipt_purchase_rules import _decimal, printed_measure, purchase_name_key
from packages.receipt_matching import normalize_label


def _paired_template(private: dict, cloud_rows: list[dict]) -> dict:
    """Keep the corresponding pack variant, not another row's specification."""
    measure = printed_measure(private["name"])
    matches = [row for row in cloud_rows if normalize_label(row["name_raw"]) == normalize_label(private["name"])]
    if not matches and measure is not None:
        matches = [row for row in cloud_rows if printed_measure(row["name_raw"]) == measure]
    if matches:
        return matches[0]
    if (len({normalize_label(row["name_raw"]) for row in cloud_rows}) == 1
            and printed_measure(cloud_rows[0]["name_raw"]) == measure):
        return cloud_rows[0]
    # Private spelling may be imperfect but cannot acquire another pack size.
    return dict(cloud_rows[0], name_raw=private["name"], name_expanded=None)


def _shifted_bag_rows(cloud_lines: list[dict], private_rows: list[dict]) -> set[int]:
    """A bag itself must lead a proved consecutive forward-shift chain."""
    bad = set()
    ordered = sorted(private_rows, key=lambda row: row["source_row_ids"][0])
    for index, cloud in enumerate(cloud_lines[:-2]):
        if not re.search(r"\b(?:pp\s*woven\s*bag|plastic\s+bag|shopping\s+bag|carrier\s+bag)\b", cloud["name_raw"], re.I):
            continue
        for offset in range(len(ordered) - 2):
            chain = ordered[offset:offset + 3]
            if any(chain[i + 1]["source_row_ids"][0] != chain[i]["source_row_ids"][1] + 1 for i in range(2)):
                continue
            if _decimal(cloud.get("line_total")) != _decimal(chain[0]["price_rm"]):
                continue
            if all(purchase_name_key(cloud_lines[index + step + 1]["name_raw"]) == purchase_name_key(chain[step]["name"])
                   and _decimal(cloud_lines[index + step + 1].get("line_total")) == _decimal(chain[step + 1]["price_rm"])
                   for step in range(2)):
                bad.add(index)
    return bad


def repair_barcode_paired_purchases(cloud_lines: list[dict], evidence: list[dict]) -> list[dict]:
    """Only exact purchase-name alignment plus adjacent private rows is authority.

    Missing provenance (old inference) does nothing. Unrelated cloud products
    remain untouched; duplicate purchases are retained, never collapsed.
    Prices are printed charges, not input to a quantity/price calculation.
    """
    paired: dict[str, list[dict]] = defaultdict(list)
    for row in evidence:
        ids = row.get("source_row_ids") or []
        if (row.get("price_basis") != "BARCODE_PRICE_BEFORE_NAME"
                or len(ids) != 2 or any(type(value) is not int for value in ids)
                or ids[0] < 1 or ids[1] != ids[0] + 1
                or _decimal(row.get("price_rm")) is None):
            continue
        key = purchase_name_key(str(row.get("name") or ""))
        if key:
            paired[key].append(row)
    cloud_by_key: dict[str, list[dict]] = defaultdict(list)
    for row in cloud_lines:
        cloud_by_key[purchase_name_key(row["name_raw"])].append(row)
    replacements = {}
    for key, private_rows in paired.items():
        rows = cloud_by_key.get(key, [])
        # Partial private evidence cannot delete additional cloud purchases.
        if not rows or len(private_rows) < len(rows):
            continue
        expected = [_decimal(row["price_rm"]) for row in private_rows]
        actual = [_decimal(row.get("line_total")) for row in rows]
        if expected == actual:
            continue
        replacements[key] = [dict(_paired_template(row, rows),
                                  quantity=Decimal(str(row["qty"])) if row.get("qty") is not None else None,
                                  unit=row.get("unit"), line_total=_decimal(row["price_rm"]),
                                  unit_price=None) for row in private_rows]
    if not replacements:
        return cloud_lines
    result = []
    emitted = set()
    shifted_bags = _shifted_bag_rows(cloud_lines, [row for rows in paired.values() for row in rows])
    for index, row in enumerate(cloud_lines):
        # A shifted bag charge is not a food purchase. This explicit nonfood
        # filter is activated only within a proven contradictory paired block.
        if index in shifted_bags:
            continue
        key = purchase_name_key(row["name_raw"])
        if key in replacements:
            if key not in emitted:
                result.extend(replacements[key])
                emitted.add(key)
        else:
            result.append(row)
    return result
