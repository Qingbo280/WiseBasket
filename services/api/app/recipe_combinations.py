from packages.optimizer.wisebasket_optimizer.v2.domain import (
    CookingStep,
    IngredientRole,
    MealType,
    RecipeIngredient,
    ReviewedRecipe,
    ReviewStatus,
    assess_recipe,
)


MEAL_ROLES = frozenset({
    IngredientRole.MAIN_PROTEIN,
    IngredientRole.STAPLE,
    IngredientRole.MAIN_VEGETABLE,
})

DEFAULT_COMPONENT_PAIRS = (
    ("garlic-prawn-stir-fry", "garlic-broccoli-stir-fry"),
    ("garlic-prawn-stir-fry", "garlic-long-beans"),
    ("long-bean-egg-stir-fry", "potato-onion-stir-fry"),
    ("malaysian-chicken-curry-with-rice", "cabbage-mamak-stir-fry"),
    ("red-tilapia-soy-with-rice", "cauliflower-stir-fry"),
    ("red-tilapia-soy-with-rice", "okra-eggplant-stir-fry"),
    ("sambal-eggplant-with-rice", "steamed-egg"),
    ("soy-sauce-chicken-with-rice", "french-bean-garlic-stir-fry"),
    ("soy-sauce-chicken-with-rice", "winged-bean-stir-fry"),
    ("soy-sauce-eggs-with-rice", "garlic-spinach-stir-fry"),
    ("squid-soy-stir-fry", "mixed-vegetable-stir-fry"),
    ("tofu-prawn-stir-fry", "mustard-greens-stir-fry"),
)

ROLE_PRIORITY = {
    IngredientRole.MAIN_PROTEIN: 0,
    IngredientRole.STAPLE: 1,
    IngredientRole.MAIN_VEGETABLE: 2,
    IngredientRole.SUPPORTING_VEGETABLE: 3,
    IngredientRole.COOKING_ESSENTIAL: 4,
    IngredientRole.SEASONING: 5,
    IngredientRole.OPTIONAL: 6,
}


def required_roles(recipe: ReviewedRecipe) -> frozenset[IngredientRole]:
    return frozenset(
        item.role
        for item in recipe.ingredients
        if item.required
    )


def ordered_components(
    first: ReviewedRecipe,
    second: ReviewedRecipe,
) -> tuple[ReviewedRecipe, ReviewedRecipe]:
    if first.meal_type is MealType.MAIN_DISH and second.meal_type is MealType.SIDE:
        return first, second
    if second.meal_type is MealType.MAIN_DISH and first.meal_type is MealType.SIDE:
        return second, first
    return tuple(sorted((first, second), key=lambda item: item.recipe_id))


def merge_ingredients(
    components: tuple[ReviewedRecipe, ReviewedRecipe],
) -> tuple[RecipeIngredient, ...]:
    by_food: dict[str, RecipeIngredient] = {}
    for component in components:
        for item in component.ingredients:
            existing = by_food.get(item.food_id)
            if existing is None:
                by_food[item.food_id] = item
                continue
            role = min(
                (existing.role, item.role),
                key=lambda value: ROLE_PRIORITY[value],
            )
            by_food[item.food_id] = RecipeIngredient(
                food_id=item.food_id,
                quantity_kg=existing.quantity_kg + item.quantity_kg,
                role=role,
                required=existing.required or item.required,
            )
    return tuple(by_food[food_id] for food_id in sorted(by_food))


def merge_steps(
    components: tuple[ReviewedRecipe, ReviewedRecipe],
) -> tuple[CookingStep, ...]:
    steps = []
    for component in components:
        for step in component.steps:
            steps.append(CookingStep(
                step_number=len(steps) + 1,
                instruction=f"{component.name}: {step.instruction}",
                food_ids=step.food_ids,
            ))
    return tuple(steps)


def combine_recipes(
    first: ReviewedRecipe,
    second: ReviewedRecipe,
) -> ReviewedRecipe:
    components = ordered_components(first, second)
    return ReviewedRecipe(
        recipe_id="meal-set--" + "--".join(item.recipe_id for item in components),
        name=" + ".join(item.name for item in components),
        meal_type=MealType.COMPLETE_MEAL,
        base_servings=components[0].base_servings,
        version=max(item.version for item in components),
        review_status=ReviewStatus.APPROVED,
        optimizer_eligible=True,
        quantity_basis=components[0].quantity_basis,
        ingredients=merge_ingredients(components),
        steps=merge_steps(components),
        max_weekly_occurrences=1,
    )


def build_complete_meal_candidates(
    recipes: tuple[ReviewedRecipe, ...],
    component_pairs: tuple[tuple[str, str], ...] = DEFAULT_COMPONENT_PAIRS,
) -> tuple[ReviewedRecipe, ...]:
    complete = [
        recipe
        for recipe in recipes
        if recipe.meal_type is MealType.COMPLETE_MEAL
        and assess_recipe(recipe).optimizer_eligible
    ]
    components = {
        recipe.recipe_id: recipe
        for recipe in recipes
        if recipe.review_status is ReviewStatus.APPROVED
        and recipe.meal_type in {MealType.MAIN_DISH, MealType.SIDE}
    }
    meal_sets = []
    for first_id, second_id in component_pairs:
        first = components.get(first_id)
        second = components.get(second_id)
        if first is None or second is None:
            continue
        if MealType.MAIN_DISH not in {first.meal_type, second.meal_type}:
            continue
        if first.base_servings != second.base_servings:
            continue
        if first.quantity_basis is not second.quantity_basis:
            continue
        if not MEAL_ROLES <= required_roles(first) | required_roles(second):
            continue
        candidate = combine_recipes(first, second)
        if assess_recipe(candidate).optimizer_eligible:
            meal_sets.append(candidate)
    return tuple(sorted((*complete, *meal_sets), key=lambda item: item.recipe_id))
