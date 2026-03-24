## Refactoring

- **Split `app/main.py` into routers + services layer**
  - `main.py` had grown to ~970 lines mixing routes, business logic, constants, and helpers
  - Split into `app/routers/` (one file per resource domain: `campaigns`, `sightings`, `pokedex`, `rangers`, `trainers`, `regions`, `leaderboard`) and `app/services/` (`rarity.py`, `sighting_service.py`)
  - `main.py` now only contains app init and `include_router()` calls (~15 lines)
  - Motivation: large monolithic files are hard to navigate, review, and test; domain-scoped modules make ownership clear

- **Extracted `require_ranger` as a FastAPI `Depends`**
  - The inline auth pattern (check header → query Ranger → raise 401/403) was copy-pasted into five separate route handlers
  - Centralised into a single `require_ranger` dependency in `app/dependencies.py`, injected via `ranger: Ranger = Depends(require_ranger)`
  - Removes ~4 lines of boilerplate per endpoint and makes the auth contract visible in the OpenAPI schema
  - The 401/403 split (missing header vs. non-ranger user) now lives in exactly one place

- **Merged `_rarity_tier` and `_rarity_priority` into a single source of truth**
  - Two nearly-identical functions with parallel branching logic existed; changing a tier boundary required two edits that could drift
  - Replaced with a single `_TIERS` lookup table and a `rarity(is_mythical, is_legendary, capture_rate) -> RarityInfo` function returning both name and priority together
  - `rarity_tier()` and `rarity_priority()` are now thin wrappers; only one place to change if tier boundaries are adjusted

- **Made `is_confirmed` a hybrid property**
  - `Sighting.is_confirmed` was a plain `bool` column that could drift from `confirmed_by`/`confirmed_at` (e.g., `confirmed_by` set but `is_confirmed` still `False`)
  - Changed to a `@hybrid_property` derived from `confirmed_by IS NOT NULL`, with a SQL expression companion so `func.sum(Sighting.is_confirmed.cast(Integer))` continues to work in aggregation queries
  - The manual `sighting.is_confirmed = True` assignment was removed — setting `confirmed_by` is the single write that confirms a sighting

- **Split `GET /pokedex/{id_or_region}` into two explicit routes**
  - The original endpoint used a `try/except ValueError` to branch between returning a single `PokemonResponse` and a `list[PokemonResponse]` — two incompatible shapes from one path
  - Replaced with `GET /pokedex/{pokemon_id:int}` (single Pokémon) and `GET /pokedex/region/{region_name}` (list by region), each with its own response model and a consistent contract

- **Added pagination to unbounded list endpoints**
  - `GET /rangers/{id}/sightings` and `GET /pokedex` were unbounded; a prolific ranger or large Pokédex would dump every row
  - Both now accept `limit` (1–100, default 20) and `offset` and return a `PaginatedXxxResponse` envelope with a `total` count
  - Underlying queries use SQL `LIMIT`/`OFFSET` rather than Python slicing

- **Pushed catch summary aggregation to SQL**
  - `GET /trainers/{id}/pokedex/summary` previously loaded all caught-Pokémon rows into Python memory and used `len(rows)` for the count
  - Replaced with three SQL queries: a `COUNT` for total caught, a `GROUP BY type1` for type breakdown, a `GROUP BY generation` for generation breakdown — zero Python-side loops

- **`PATCH /campaigns` guarded by lifecycle status**
  - The update endpoint previously accepted field edits on campaigns in any status, including `completed` and `archived`
  - Now raises `409 Conflict` if the campaign is `completed` or `archived`; only status transitions are allowed at that point

- **`start_date < end_date` validator on `CampaignCreate`**
  - Added a Pydantic `@model_validator(mode="after")` rejecting campaigns where `end_date <= start_date` with a 422
  - Runs before the route handler — invalid input never reaches the DB

- **All POST endpoints return 201 Created**
  - Resource-creating endpoints previously returned 200; changed to 201 to match HTTP semantics
  - RPC-style action endpoints (`/transition`, `/confirm`) remain 200 — they mutate state rather than create a new resource

- **Region coherence check on sighting → campaign association**
  - A sighting submitted with a `campaign_id` now also validates that `sighting.region == campaign.region`
  - Previously a Johto sighting could be silently attached to a Kanto campaign; the error message names both regions to make the mismatch immediately actionable

- **Fixed `datetime.utcnow()` deprecation**
  - All `datetime.utcnow()` calls replaced with a `_utcnow()` helper returning `datetime.now(timezone.utc).replace(tzinfo=None)`
  - `replace(tzinfo=None)` strips the UTC tzinfo before storing, keeping SQLite's naive datetime expectation while using the non-deprecated API

- **Consistent `Pokémon` spelling and unused import cleanup**
  - All user-facing error messages use the accented form `Pokémon`
  - The unused `Any` import that existed in the old `main.py` was eliminated naturally during the structural split

---

## Design Decisions and Trade-offs

- **Anomaly detection: intra-tier z-score**
  - Algorithm: for each rarity tier with at least two distinct species in a region, compute population mean and standard deviation of per-species sighting counts; flag species where `|z| >= 2.0`
  - `mean = Σ(count_i) / n`, `stdev = sqrt(Σ(count_i - mean)² / n)`, `z = (count_i - mean) / stdev`
  - **Why intra-tier?** Comparing a Common Pokémon's count to a Legendary's count is not meaningful — Legendaries are expected to be rare by definition. Constraining comparisons within a tier controls for the base rarity effect and surfaces anomalies relative to peers with similar expected encounter rates
  - **Why z-score threshold of 2.0?** Corresponds to the outermost ~5% of a normal distribution — sensitive enough to surface real patterns in a dataset of tens of thousands of sightings while avoiding false positives on small samples
  - **Edge cases handled:** tiers with only one species (z-score undefined with n=1) are excluded; tiers with identical counts (`stdev = 0`) are skipped; empty regions return `total_sightings: 0, tiers: [], anomalies: []` rather than 404
  - **Confirmed vs. unconfirmed:** raw counts are used. Weighting confirmed sightings would skew analysis toward rangers with active peer networks rather than ground-truth encounter rates; confirmation is better applied as a query-time filter

- **Campaign status as string with app-layer enforcement**
  - SQLite has no native enum type; a CHECK constraint silently allows invalid values in some SQLite versions
  - Valid lifecycle transitions are enforced in the application via `VALID_TRANSITIONS = {"draft": "active", "active": "completed", "completed": "archived"}`
  - The DB stores current state; the service layer owns the rules

- **Sighting locking via campaign status**
  - Completed-campaign sightings are locked by checking `campaign.status in ("completed", "archived")` at delete time rather than adding a `locked` boolean column to `Sighting`
  - The truth is already in the campaign row — duplicating it as a column would introduce a consistency risk

- **Confirmation stored on `Sighting` (not a separate table)**
  - Added `confirmed_by` (FK → rangers) and `confirmed_at` (datetime) directly to the `Sighting` row
  - Since each sighting can only be confirmed once by a single peer, the relationship is 1:1 — a join table would add latency for no normalization benefit

- **`TrainerCatch` with composite primary key**
  - `(trainer_id, pokemon_id)` as a composite primary key enforces "a trainer can only catch each species once" at the database level — no separate unique constraint needed on top of a surrogate key
  - No indexes were added beyond the implicit PK index since catch queries always filter by `trainer_id` (leftmost key), which the composite PK covers

- **Duplicate catch returns 409, not silent upsert**
  - When a trainer POSTs a Pokémon they've already caught, the endpoint returns 409 Conflict rather than silently succeeding
  - This makes it clear to the caller that no state change occurred; 409 is more honest and easier to debug

- **`is_caught` as optional field on `PokemonResponse`**
  - Remains `None` for anonymous requests and ranger callers (rangers don't have catch logs), preventing breaking changes for existing callers
  - Set to `True`/`False` only when the `X-User-ID` header maps to a Trainer — the new field is additive and null when not applicable

- **Leaderboard: two queries rather than a window function**
  - Main aggregation: `GROUP BY ranger_id` with JOINed Ranger name, computing `COUNT(id)`, `SUM(is_confirmed)`, and `COUNT(DISTINCT pokemon_id)`, sorted and paginated
  - Rarest Pokémon: single `SELECT DISTINCT (ranger_id, pokemon_id, pokemon attributes)` for only the current page's rangers; Python iterates once tracking the highest-priority species per ranger
  - `ROW_NUMBER()` / `FIRST_VALUE()` window functions would require a subquery or self-join; fetching distinct pairs and Python-grouping over at most `limit × num_species` rows is simpler and correct
  - Invalid `sort_by` values return 400 rather than silently falling back — surprising silent fallbacks are harder to debug

- **Rarity priority scale (consistent across Features 4, 5, 6)**
  - `5` mythical, `4` legendary, `3` rare (capture_rate < 75), `2` uncommon (capture_rate < 150), `1` common
  - Single `_TIERS` table in `app/services/rarity.py` ensures consistent semantics across the regional analysis, anomaly detection, and leaderboard endpoints

---

## Performance

- **Eliminated N+1 queries with JOINs**
  - The original `get_ranger_sightings` queried the Pokemon table for each sighting in a loop
  - Replaced with `db.query(Sighting, Pokemon, Ranger).join(Pokemon, ...).join(Ranger, ...)` — one query regardless of result size
  - The same JOIN pattern was applied to all sighting list endpoints

- **Paginated all unbounded list endpoints**
  - `GET /pokedex`, `GET /rangers/{id}/sightings`, and `GET /sightings` all use SQL `LIMIT`/`OFFSET` with a separate `COUNT(*)` query for the total
  - Prevents full-table scans returning thousands of rows to the client

- **Added missing foreign key indexes**
  - All filter columns on `sightings` are indexed individually (`region`, `pokemon_id`, `ranger_id`, `date`, `weather`, `time_of_day`, `campaign_id`)
  - Composite indexes on `(region, pokemon_id)` and `(region, date)` cover the two most common multi-column filter paths
  - Pokemon indexes on `generation` and `name` cover the two filtered access paths on that table
  - Without these indexes, every filter would require a full table scan

- **SQL aggregation instead of Python aggregation**
  - Campaign summary (`total_sightings`, `unique_species`, `contributing_rangers`, date range) computed in a single aggregation query, not by fetching rows into Python
  - Catch summary (`by_type`, `by_generation`) pushed to SQL `GROUP BY` queries; previously loaded all rows into Python memory
  - Regional analysis counts computed with `GROUP BY pokemon_id` — one query per region rather than one per species

- **Leaderboard rarest-Pokémon bounded by page size**
  - The DISTINCT pokemon pairs query is scoped to only the `ranger_ids` on the current page (at most `limit` rangers)
  - Avoids loading all species for all rangers when only a page of results is needed

- **`COUNT(DISTINCT ranger_id)` for leaderboard total**
  - Uses a single scan on the sightings table (`COUNT(DISTINCT ranger_id)`) rather than loading all rows to count unique rangers
