"""WiseBasket recipe-first optimizer.

The V1 basket-first optimizer was retired on 21 September 2026. There is no
compatibility ``optimize`` export: new code must use the explicit V2 modules.
Keeping that failure loud prevents an old basket solve from silently returning
while the recipe-first planner is being rebuilt.
"""

__all__: list[str] = []
