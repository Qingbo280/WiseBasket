"""Compare independent food interpretations by their printed receipt rows."""
import logging

from packages.receipt_matching import (
    expand_receipt_label, match_text_candidates, normalize_receipt_item_label,
)

log = logging.getLogger(__name__)


def compare_reader_rows(parser, llm):
    if any(not row.get('source_row_ids') for row in parser):
        return parser
    result, used = [], set()
    for original in parser:
        source = set(original['source_row_ids'])
        overlaps = [i for i, row in enumerate(llm) if source.intersection(row['source_row_ids'])]
        used.update(overlaps)
        if not overlaps:
            result.append(original)
            continue
        other = llm[overlaps[0]]
        ambiguous = len(overlaps) != 1 or sum(
            bool(set(row['source_row_ids']).intersection(other['source_row_ids'])) for row in parser
        ) != 1
        merged = dict(original)
        for field in (() if ambiguous else ('qty', 'unit', 'price_rm')):
            if merged.get(field) is None:
                merged[field] = other.get(field)
        result.append({**merged, '_parser_line': original, '_llm_line': other,
                       '_reader_conflict': ambiguous})
    result.extend(row for i, row in enumerate(llm) if i not in used)
    return sorted(result, key=lambda row: min(row['source_row_ids']))


def _match(row, aliases):
    raw = str(row.get('name') or '')
    cleaned = normalize_receipt_item_label(raw)
    labels = [label for label in (raw, cleaned, expand_receipt_label(cleaned or raw),
                                 row.get('expanded_name')) if label]
    return match_text_candidates(labels, aliases)


def match_compared_row(row, aliases):
    parser = _match(row.get('_parser_line', row), aliases)
    llm = _match(row['_llm_line'], aliases) if '_llm_line' in row else parser
    if parser[0]:
        if row.get('_reader_conflict') or (llm[0] and parser[0] != llm[0]):
            log.info('Receipt reader disagreement rows=%s parser_food=%s llm_food=%s; preserving parser match',
                     row.get('source_row_ids'), parser[0], llm[0])
        return parser
    if row.get('_reader_conflict') or (parser[0] and llm[0] and parser[0] != llm[0]):
        candidates = {}
        for food_id, score in (*parser[2], *llm[2]):
            candidates[food_id] = max(score, candidates.get(food_id, 0))
        return None, None, sorted(candidates.items(), key=lambda item: (-item[1], item[0]))[:4]
    return parser if parser[0] else llm


def has_reader_conflict(row, aliases):
    if row.get('_reader_conflict'):
        return True
    if '_llm_line' not in row:
        return False
    parser, llm = _match(row['_parser_line'], aliases), _match(row['_llm_line'], aliases)
    return bool(parser[0] and llm[0] and parser[0] != llm[0])
