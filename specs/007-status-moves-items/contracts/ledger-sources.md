# Contract: added item sources in the availability ledger (007, FR-018)

| Source | Entry kind | Items | Quantity | Detail must state | `src` |
|---|---|---|---|---|---|
| Route 221 house | `npc_item_gift` | Black Belt, Expert Belt, Focus Sash | UNLIMITED | daily flag; rotation order; "a party Pokémon at the day's random level (2-99)" | `scripts_route_221_house.s:39` |
| Pastoria City SW house | `npc_item_gift` | the 17 berries with item ids [id(Occa), id(Occa)+17) | UNLIMITED | daily flag; 1/17 per day | `scripts_pastoria_city_southwest_house.s:20` |
| Amity Square partner pickup | `npc_item_gift` | the 9 berries written to `VAR_FOLLOWER_MON_PICKUP_ITEM_ID` | UNLIMITED | repeatable after 200 steps; allowed partner species | `scripts_amity_square.s:375` |
| Amity Square Gift Man | `npc_item_gift` | the `ITEM_*` entries of `sBerryAndAccessoryManOptions` | UNLIMITED | daily flag; 5 per gift | `scripts_amity_square.s:940` |

- Every item list is extracted from the decomp script or C table. None is typed by hand.
- The phase comes from the ledger's existing rules. No `uncertain` gate is added.
- `availability.json` is regenerated with `uv run platsim extract`.
- **Counts under default options:** `held_items_unlimited` 77 (was 66), `held_items_unavailable_count` 44 (was 55). TM and species counts are unchanged.
- **The validator** accepts these items exactly when `item_copies` / `team_item_copies` say so. Its logic is unchanged.
- **Dataflow sentinel:** only these give sites, plus the News Press, Flower Shop and Route 208 berry sites, change their resolved items.
