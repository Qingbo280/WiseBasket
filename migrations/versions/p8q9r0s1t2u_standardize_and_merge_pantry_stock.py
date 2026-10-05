"""Canonicalize pantry units and consolidate duplicate available food rows."""
from alembic import op


revision = "p8q9r0s1t2u"
down_revision = "o7p8q9r0s1t"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Pantry is current stock, not a purchase ledger. Keep the oldest row as
    # the aggregate and soft-remove duplicate AVAILABLE rows. Unlike units (or
    # a missing amount) become unknown instead of being falsely summed.
    op.execute(
        """
        with normalized as (
            select pantry_item_id, household_id, canonical_food_id, quantity,
                case lower(coalesce(unit, ''))
                    when 'g' then 'kg' when 'gram' then 'kg' when 'grams' then 'kg'
                    when 'kg' then 'kg' when 'kilogram' then 'kg' when 'kilograms' then 'kg'
                    when 'ml' then 'l' when 'millilitre' then 'l' when 'milliliter' then 'l'
                    when 'l' then 'l' when 'litre' then 'l' when 'liter' then 'l'
                    when 'pc' then 'pcs' when 'pcs' then 'pcs' when 'piece' then 'pcs'
                    when 'pieces' then 'pcs' when 'biji' then 'pcs' when 'unit' then 'pcs'
                    when 'pack' then 'pack' when 'packet' then 'pack' when 'pkt' then 'pack'
                    else null
                end as normalized_unit,
                case lower(coalesce(unit, ''))
                    when 'g' then quantity / 1000 when 'gram' then quantity / 1000
                    when 'grams' then quantity / 1000 when 'ml' then quantity / 1000
                    when 'millilitre' then quantity / 1000 when 'milliliter' then quantity / 1000
                    else quantity
                end as normalized_quantity
            from pantry_item where status = 'AVAILABLE'
        ), grouped as (
            select household_id, canonical_food_id, min(pantry_item_id) as keeper_id,
                count(*) as row_count,
                case when count(*) = 1 and min(normalized_unit) is not null then min(normalized_quantity)
                     when bool_and(quantity is not null) and count(distinct normalized_unit) = 1
                          and min(normalized_unit) is not null then sum(normalized_quantity)
                     else null end as merged_quantity,
                case when count(*) = 1 and min(normalized_unit) is not null then min(normalized_unit)
                     when bool_and(quantity is not null) and count(distinct normalized_unit) = 1
                          and min(normalized_unit) is not null then min(normalized_unit)
                     else null end as merged_unit
            from normalized group by household_id, canonical_food_id
        )
        update pantry_item p set quantity = g.merged_quantity, unit = g.merged_unit
        from grouped g where p.pantry_item_id = g.keeper_id;
        """
    )

    # asyncpg prepares each Alembic operation independently and rejects a
    # string containing multiple SQL commands. Keep duplicate soft-removal as
    # its own operation while preserving the surrounding migration transaction.
    op.execute(
        """
        with grouped as (
            select household_id, canonical_food_id, min(pantry_item_id) as keeper_id
            from pantry_item where status = 'AVAILABLE'
            group by household_id, canonical_food_id
        )
        update pantry_item p set status = 'REMOVED'
        from grouped g
        where p.status = 'AVAILABLE'
          and p.household_id = g.household_id
          and p.canonical_food_id = g.canonical_food_id
          and p.pantry_item_id <> g.keeper_id;
        """
    )


def downgrade() -> None:
    # Consolidation is intentionally irreversible: it represents the user's
    # requested current-stock model rather than historical purchase rows.
    pass
