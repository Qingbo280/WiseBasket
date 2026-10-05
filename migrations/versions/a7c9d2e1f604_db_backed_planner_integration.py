"""db backed planner integration

Revision ID: a7c9d2e1f604
Revises: 9b1c2d3e4f50
Create Date: 2026-08-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7c9d2e1f604"
down_revision: Union[str, Sequence[str], None] = "9b1c2d3e4f50"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Canonical placeholder seed REMOVED 2026-09 namespace rebuild: the
    # foundation now seeds the full new-namespace catalogue, so the old
    # apple/pork loin/shrimp stand-in rows (SF022-SF025) must never be
    # created. Only the structural DDL below remains.
    op.execute(
        """
        insert into hard_exclusion_food (exclusion_code, canonical_food_id)
        values
            ('NO_PORK', 'SF009'),
            ('SHELLFISH', 'SF022'),
            ('VEGETARIAN', 'SF006'),
            ('VEGETARIAN', 'SF051')
        on conflict (exclusion_code, canonical_food_id) do nothing
        """
    )

    op.create_index("ix_auth_session_refresh_token_hash", "auth_session", ["refresh_token_hash"], unique=True)
    op.create_index("ix_planning_request_household_id", "planning_request", ["household_id"])
    op.create_index("ix_generated_plan_planning_request_id", "generated_plan", ["planning_request_id"])
    op.create_index("ix_generated_plan_item_plan_id", "generated_plan_item", ["plan_id"])
    op.create_index(
        "ix_food_price_observation_latest_lookup",
        "food_price_observation",
        ["location_id", "canonical_food_id", sa.text("observed_date desc")],
        postgresql_where=sa.text("quality_status = 'PASS' and canonical_food_id is not null and price_rm_per_100g_edible is not null"),
    )
    op.create_unique_constraint(
        "uq_plan_store_option_plan_option",
        "plan_store_option",
        ["plan_id", "plan_store_option_id"],
    )
    op.create_foreign_key(
        "fk_generated_plan_selected_store_same_plan",
        "generated_plan",
        "plan_store_option",
        ["plan_id", "selected_store_option_id"],
        ["plan_id", "plan_store_option_id"],
        use_alter=True,
    )

    op.execute(
        """
        create or replace view v_latest_food_price as
        select *
        from (
            select fpo.*,
                   row_number() over (
                     partition by fpo.canonical_food_id, fpo.location_id
                     order by fpo.observed_date desc, fpo.price_observation_id desc
                   ) as rn
            from food_price_observation fpo
            where fpo.quality_status = 'PASS'
              and fpo.canonical_food_id is not null
              and fpo.price_rm_per_100g_edible is not null
        ) latest
        where rn = 1
        """
    )
    op.execute("drop view if exists v_optimizer_food_candidate")
    op.execute(
        """
        create view v_optimizer_food_candidate as
        select cf.canonical_food_id,
               cf.canonical_name,
               cf.canonical_name_ms,
               cf.category,
               fn.source_dataset_version as nutrition_source_dataset_version,
               fn.basis_g,
               fn.energy_kcal,
               fn.protein_g,
               fn.fat_g,
               fn.carbohydrate_g,
               fn.fibre_g,
               fn.iron_mg,
               fn.calcium_mg,
               fn.vitamin_a_ug,
               fn.vitamin_c_mg,
               lfp.location_id,
               lfp.observed_date,
               lfp.source_dataset_version,
               lfp.price_observation_id,
               lfp.price_rm_per_100g_edible,
               lfp.purchase_mass_g,
               uc.source_unit as pack_label,
               lfp.quality_status as price_quality_status,
               fn.quality_status as nutrition_quality_status
        from canonical_food cf
        join food_nutrition fn on fn.canonical_food_id = cf.canonical_food_id
        join v_latest_food_price lfp on lfp.canonical_food_id = cf.canonical_food_id
        left join unit_conversion uc
               on uc.canonical_food_id = cf.canonical_food_id
              and uc.conversion_type = 'PURCHASE_MASS'
              and uc.production_eligible = true
        where cf.status = 'ACTIVE'
          and fn.is_current = true
          and fn.quality_status in ('PASS', 'WARN')
          and lfp.quality_status = 'PASS'
          and lfp.price_rm_per_100g_edible is not null
          and exists (
              select 1
              from source_food_mapping sfm
              where sfm.canonical_food_id = cf.canonical_food_id
                and sfm.mapping_status in ('EXACT', 'ACCEPTED_EQUIVALENT', 'NEEDS_CONVERSION')
                and sfm.verification_status = 'VERIFIED'
                and sfm.review_status = 'APPROVED'
          )
        """
    )


def downgrade() -> None:
    op.execute("drop view if exists v_optimizer_food_candidate")
    op.execute(
        """
        create view v_optimizer_food_candidate as
        select cf.canonical_food_id,
               cf.canonical_name,
               cf.category,
               fn.basis_g,
               fn.energy_kcal,
               fn.protein_g,
               fn.fat_g,
               fn.carbohydrate_g,
               fn.fibre_g,
               fn.iron_mg,
               fn.calcium_mg,
               fn.vitamin_a_ug,
               fn.vitamin_c_mg,
               lfp.location_id,
               lfp.observed_date,
               lfp.price_rm_per_100g_edible,
               lfp.quality_status as price_quality_status,
               fn.quality_status as nutrition_quality_status
        from canonical_food cf
        join food_nutrition fn on fn.canonical_food_id = cf.canonical_food_id
        join v_latest_food_price lfp on lfp.canonical_food_id = cf.canonical_food_id
        where cf.status = 'ACTIVE'
          and fn.is_current = true
          and fn.quality_status in ('PASS', 'WARN')
          and lfp.quality_status = 'PASS'
        """
    )
    op.drop_constraint("fk_generated_plan_selected_store_same_plan", "generated_plan", type_="foreignkey")
    op.drop_constraint("uq_plan_store_option_plan_option", "plan_store_option", type_="unique")
    op.drop_index("ix_food_price_observation_latest_lookup", table_name="food_price_observation", postgresql_where=sa.text("quality_status = 'PASS' and canonical_food_id is not null and price_rm_per_100g_edible is not null"))
    op.drop_index("ix_generated_plan_item_plan_id", table_name="generated_plan_item")
    op.drop_index("ix_generated_plan_planning_request_id", table_name="generated_plan")
    op.drop_index("ix_planning_request_household_id", table_name="planning_request")
    op.drop_index("ix_auth_session_refresh_token_hash", table_name="auth_session")
    op.execute("delete from hard_exclusion_food where canonical_food_id in ('SF009','SF022','SF006','SF051')")
