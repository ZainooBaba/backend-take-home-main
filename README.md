# Endeavor AI Take Home Assessment

![Image of Professor Oak](oak_title_screen.png)

## Tech Stack Overview

- Language: **Python 3.12**
- Framework: **FastAPI**
- Database: **SQLite**
- ORM: **SQLAlchemy**
- **uv** to manage the Python environment
- Tests: **pytest**

## Quick Start

```bash
# Install dependencies
uv sync

# Run the seed script (note: it's currently broken — see Initial Task)
uv run python scripts/seed.py

# Start the dev server
uv run uvicorn app.main:app --reload

# Run tests
uv run pytest
```

## Situation

Congratulations! You've just moved up to Goldenrod City, where you have been hired as a senior backend engineer at the **Pokémon Research Institute**!

The institute coordinates field research across multiple regions. Professor Oak has been leading an effort to build the next-generation of the **Pokédex** -- that allows field researchers to log Pokémon sightings, organize research campaigns, and query aggregated findings.
This is in addition to its existing capabilities of viewing Pokémon information, location, and if the current user has captured the Pokémon (n.b. a Trainer/Ranger can see all Pokémon in the Pokédex, regardless of whether they've actually encountered that Pokémon before -- a notable distinction if you are familiar with the games).

The Pokédex serves two audiences: **Pokémon Trainers** use it to browse species information and keep track of the Pokémon they've caught, while **Pokémon Rangers** use it for field research, logging sightings and contributing to regional analysis. Both audiences share the same API, and the system needs to know *who* is making a request in order to personalize responses and enforce permissions.

Professor Oak put his colleague Professor Elm in charge of development, but he contracted the project out to a consultancy rather than building out his own team. While it works, the codebase has grown to have some rough edges. The Pokémon Rangers (i.e. field researchers) have also reported that **certain endpoints have become noticeably slow** as the dataset has grown (the database now contains over 50,000 sighting records across dozens of regions). Since Prof. Elm has hired you as a full-time dev, he needs your help to **clean up the existing code where you see fit**, **address the performance concerns**, and **implement several new features** that the Rangers and Trainers have been requesting.

The API is built with **Python**, **FastAPI**, and **SQLite** (via SQLAlchemy). A broken seed script is provided whose goal is to pre-populate the database with Pokémon species reference data and a large volume of historical sighting records. Since the script hasn't been used since the early days of the Pokédex, it has fallen out of compatibility with the current codebase and needs to be touched up to successfully seed the database.

---

## Domain Concepts

### Pokémon Trainers
Trainers are individuals who own Pokémon, primarily using them for battle with other trainers. Trainers can also be collectors, which is why they might own a Pokédex to help keep track of their assemblage. Trainers use the Pokédex to browse species data and **track which Pokémon they've personally caught**.

### Pokémon Rangers
Rangers are field researchers who go into the wild and record Pokémon observations. Each Ranger has a name, email, and a specialization (a Pokémon type they focus on, e.g., "Water" or "Fire"). Pokémon Rangers don't *own* Pokémon the same way that Trainers do; rather, they befriend them as needed in the field, releasing them back into the wild when they no longer require a Pokémon's help.

### Trainers vs. Rangers: Role Boundaries

Trainers and Rangers are **distinct roles** in the system. A Trainer cannot log field sightings, and a Ranger cannot use the catch-tracking features. The system should enforce this — if a request requires a Ranger (e.g., logging a sighting) and the `X-User-ID` belongs to a Trainer, the API should reject it with an appropriate error, and vice versa. A person in the real world could be both a Trainer and a Ranger, but they would have two separate registrations and two separate UUIDs.

### User Identity

The Pokédex uses a simple identity system. Every registered Trainer and Ranger is assigned a **UUID** upon registration. This UUID is how the API identifies who is making a request.

- Endpoints that need to know who the caller is (e.g., viewing your personal catch log, logging a sighting, confirming a peer's sighting) expect the user's UUID to be passed via the `X-User-ID` header.
- An existing lookup endpoint allows retrieving a user's UUID by their name.
- There is no password or token-based authentication — the UUID *is* the credential for the purposes of this system.


### Pokémon Species (Reference Data)
The known catalog of Pokémon. Since everyone knows Pokémon games made after 2010 are not real, the Pokédex is limited to the 493 Pokémon that span Generations I-IV (Kanto, Johto, Hoenn, and Sinnoh). Each species has a name, one or two types, a generation number, boolean flags for `is_legendary` and `is_mythical` (see Terminology), a boolean `is_baby` field (see Terminology), a `capture_rate` (0–255, higher means easier to catch), and an evolutionary chain. All of this data is provided to you in data/pokedex_entries.json.

> **Rarity tiers:** Several features reference rarity tiers. These are derived from the species data as follows:
>
> | Tier          | Rule                       |
> |---------------|----------------------------|
> | **Mythical**  | `is_mythical = true`       |
> | **Legendary** | `is_legendary = true`      |
> | **Rare**      | `capture_rate < 75`        |
> | **Uncommon**  | `75 <= capture_rate < 150` |
> | **Common**    | `capture_rate >= 150`      |
>
> The `is_legendary` and `is_mythical` flags take priority — a Pokémon with `capture_rate = 3` and `is_legendary = true` is Legendary, not Rare.

### Sightings
A record of a Ranger observing a Pokémon in the field. Each sighting includes:
- The Pokémon species observed
- The height (meters) and weight (kilograms) of the Pokémon
- Whether the Pokémon was **shiny** (see Terminology)
- The Ranger who made the observation
- Location (region name and route/area string)
- Date and time of the sighting
- Weather conditions at the time (`sunny`, `rainy`, `snowy`, `sandstorm`, `foggy`, `clear`)
- Time of day (`morning`, `day`, `night`)
- Notes (free-text field for behavioral observations)
- Whether the sighting has been confirmed by a fellow Ranger (see Feature 3)

### Research Campaigns *(new — see Feature 2)*
An organized research effort with a specific focus. Campaigns group related sightings together and follow a lifecycle from planning through completion.

---

## Existing Endpoints (Provided in Starter Code)

The following endpoints already exist, but they may or may not be working. You are free (and encouraged) to refactor them as you see fit.

### Identity & Lookup

| Method | Path                     | Description                                              |
|--------|--------------------------|----------------------------------------------------------|
| `POST` | `/trainers`              | Register a new Trainer (returns their UUID)              |
| `POST` | `/rangers`               | Register a new Pokémon Ranger (returns their UUID)       |
| `GET`  | `/users/lookup`          | Look up a user's UUID by name (query param `?name=...`)  |
| `GET`  | `/trainers/{trainer_id}` | Get a Trainer's profile                                  |
| `GET`  | `/rangers/{ranger_id}`   | Get a Ranger's profile                                   |

### Rangers & Sightings

| Method | Path                             | Description                              |
|--------|----------------------------------|------------------------------------------|
| `GET`  | `/rangers/{ranger_id}/sightings` | List all sightings submitted by a ranger |

### Pokémon Species (Reference Data)

| Method | Path                                   | Description                                                        |
|--------|----------------------------------------|--------------------------------------------------------------------|
| `GET`  | `/pokedex`                             | List all known Pokémon species                                     |
| `GET`  | `/pokedex/{pokemon_id}`                | Get details for a specific species                                 |
| `GET`  | `/pokedex/{region_name_or_generation}` | See Terminology for a mapping of region name to integer generation |
| `GET`  | `/pokedex/search`                      | Search species by name (fuzzy match)                               |

### Sightings

| Method   | Path                       | Description                        |
|----------|----------------------------|------------------------------------|
| `POST`   | `/sightings`               | Log a new Pokémon sighting         |
| `GET`    | `/sightings/{sighting_id}` | Get details of a specific sighting |
| `DELETE` | `/sightings/{sighting_id}` | Delete a sighting                  |

---

## Your Tasks

### Initial Task: Fix the data ingestion script

The onboarding script hasn't been touched since the days of Pokémon Red, Green, and Blue! As such, when you try running it you'll see that it does not work.
Please fix the script -- after you do so, it'll prepopulate the SQLite database with all the information you'll need for the remaining features.


### Feature 1: Sighting Filters & Pagination

**Request from**: Field Research Coordinator

> "Right now there's no way to browse sightings with any kind of filter. We need an endpoint that lets us query sightings by species, region, weather, time of day, date range, and ranger — ideally with support for combining multiple filters. We also need pagination since some regions have thousands of records."

Implement a `GET /sightings` endpoint (or rework the existing data model) that supports:
- Filtering by any combination of: `pokemon_id`, `region`, `weather`, `time_of_day`, `ranger_id`, and a `date_from` / `date_to` range
- Pagination via `limit` and `offset` (with sensible defaults)
- The response should include the total count of matching records alongside the page of results

---

### Feature 2: Research Campaigns

**Request from**: Professor Oak

> "Our rangers need a way to organize their work into campaigns. A campaign is a planned research effort — for example, 'Cerulean Cave Survey, February 2026' or 'Johto Migratory Pattern Study.' I need campaigns to have a clear lifecycle so we know what's active and what's been wrapped up."

Implement full CRUD for research campaigns and integrate them with the sighting system:

**Campaign fields:**
- Name and description
- Region the campaign is focused on
- Start and end dates
- Status, which follows this lifecycle: `draft → active → completed → archived`

**Requirements:**
- Rangers should be able to associate sightings with an active campaign when logging them (a sighting may optionally belong to a campaign)
- Only **active** campaigns should accept new sightings. Attempts to log a sighting against a non-active campaign should fail with a clear error.
- Completing a campaign should **lock** its associated sightings — they can no longer be edited or deleted.
- A campaign can only move forward through the lifecycle (e.g., `completed` cannot go back to `active`). Invalid transitions should be rejected.
- Add an endpoint to view a campaign's summary: total sightings, unique species observed, contributing Rangers, and date range of actual observations.

**Suggested endpoints** (you may adjust as you see fit):

| Method  | Path                                  | Description                               |
|---------|---------------------------------------|-------------------------------------------|
| `POST`  | `/campaigns`                          | Create a new campaign (starts in `draft`) |
| `GET`   | `/campaigns/{campaign_id}`            | Get campaign details                      |
| `PATCH` | `/campaigns/{campaign_id}`            | Update campaign metadata                  |
| `POST`  | `/campaigns/{campaign_id}/transition` | Move campaign to its next lifecycle state |
| `GET`   | `/campaigns/{campaign_id}/summary`    | Get aggregated stats for the campaign     |

---

### Feature 3: Peer Confirmation System

**Request from**: Data Integrity Team

> "We need a way for Rangers to corroborate each other's sightings. A confirmed sighting carries more weight in our analysis than an unconfirmed one. But we need to make sure the system can't be gamed — you shouldn't be able to confirm your own sighting."

Implement a peer confirmation system with the following rules:
- Any Ranger can confirm another Ranger's sighting
- A Ranger **cannot** confirm their own sighting
- A sighting can only be confirmed **once** (by a single peer)
- Confirmation should record *who* confirmed it and *when*
- The analysis endpoints (Features 4 and 5) should give confirmed sightings more weight or allow filtering by confirmation status

**Identity note:** The confirming Ranger should be identified via the `X-User-ID` header. The system should validate that the UUID belongs to a registered Ranger and that it differs from the sighting's original reporter.

**Suggested endpoints:**

| Method | Path                                    | Description                             |
|--------|-----------------------------------------|-----------------------------------------|
| `POST` | `/sightings/{sighting_id}/confirm`      | Confirm a peer's sighting               |
| `GET`  | `/sightings/{sighting_id}/confirmation` | Get confirmation details for a sighting |

---

### Feature 4: Regional Research Summary

**Request from**: Professor Oak

> "I need a way to get a high-level summary of research activity for a given region. How many total sightings, how many unique species observed, who the top Rangers are, and what the most commonly sighted Pokémon are. This will go into our quarterly reports."
>
> "Also — the data team mentioned the old endpoints have gotten pretty slow since our dataset grew. If you can look into that while you're in there, I'd appreciate it."

Implement a `GET /regions/{region_name}/summary` endpoint that returns:
- Total number of sightings in the region (with a breakdown of confirmed vs. unconfirmed)
- Number of unique species observed
- A list of the top 5 most-sighted Pokémon in the region (with counts)
- A list of the top 5 contributing rangers (with sighting counts)
- A breakdown of sightings by weather condition
- A breakdown of sightings by time of day

**Performance note:** The research team has reported that aggregate queries over large regions (like Kanto, which has 10,000+ sighting records) are unacceptably slow. The existing `GET /pokemon` listing endpoint also seems to bog down when the full dataset is loaded. Please investigate and address this.

---

### Feature 5: Pokémon Rarity & Encounter Rate Analysis

**Request from**: Data Analysis Team

> "We want to compare how often each rarity tier is actually being encountered versus what we'd expect. For a given region, show us the encounter rates broken down by rarity, and flag any species that seem anomalous."

Implement a `GET /regions/{region_name}/analysis` endpoint that returns:
- The total number of sightings in the region
- A breakdown by rarity tier (`common`, `uncommon`, `rare`, `legendary`, `mythical`), each showing:
  - The number of sightings for that tier
  - The percentage of total sightings
  - The list of species observed in that tier (with individual counts)
- A list of "anomalies" — species whose sighting frequency is notably high or low relative to others in the same rarity tier

**You decide** what constitutes an anomaly and **document your reasoning** in `NOTES.md`. The analysis team cares more about your approach being defensible than about any specific algorithm.

Consider whether confirmed vs. unconfirmed sightings should be weighted differently in this analysis.

---

### Feature 6: Ranger Leaderboard

**Request from**: Institute Director

> "We'd like a leaderboard to recognize our ace rangers. It should be flexible — global or scoped to a region, and optionally filtered to a date range. Bonus if we can see who's discovered the most intriguing specimens, not just who has the most sightings."

Implement a `GET /leaderboard` endpoint that supports:
- Optional filters: `region`, `date_from` / `date_to`, `campaign_id`
- Returns a ranked list of rangers, each entry including:
  - Total sightings count
  - Confirmed sightings count
  - Unique species count
  - The single rarest Pokémon they've observed (mythical > legendary > common, shiny > non-shiny)
- Configurable sorting: by `total_sightings`, `confirmed_sightings`, or `unique_species`
- Pagination

---

### Feature 7: Trainer Pokédex (Catch Tracking)

**Request from**: Trainer Relations Team

> "Trainers have been asking for a way to track their collection through the Pokédex. They want to mark Pokémon as caught, see their completion progress, and browse their personal catch log. Some of our more competitive trainers also want to see how their collection stacks up."

Implement a personal catch-tracking system for Trainers:

**Requirements:**
- A Trainer can mark a Pokémon species as caught (recording the date caught)
- A Trainer can unmark a Pokémon (they released it, traded it away, etc.)
- When a Trainer views a Pokédex entry (e.g., `GET /pokedex/{pokemon_id}`), the response should include whether *they* have caught that species — but only if the request includes their `X-User-ID` header. Without the header, the endpoint behaves the same as before (just species data).
- A Trainer should be able to view their personal catch summary: total caught, caught by type, caught by generation, and overall completion percentage (out of 493)
- A Trainer should be able to view their full catch log: which species they've caught and when

**Suggested endpoints** (you may adjust as you see fit):

| Method   | Path                                          | Description                                                        |
|----------|-----------------------------------------------|--------------------------------------------------------------------|
| `POST`   | `/trainers/{trainer_id}/pokedex/{pokemon_id}` | Mark a Pokémon as caught                                           |
| `DELETE` | `/trainers/{trainer_id}/pokedex/{pokemon_id}` | Remove a Pokémon from caught list                                  |
| `GET`    | `/trainers/{trainer_id}/pokedex`              | View Trainer's full catch log                                      |
| `GET`    | `/trainers/{trainer_id}/pokedex/summary`      | View Trainer's catch summary (completion %, breakdown by type/gen) |

**Identity note:** These endpoints should validate that the `X-User-ID` header matches the `trainer_id` in the path — a Trainer can only modify their own catch log. Anyone can *view* another Trainer's catch log and summary (it's public data), but only the owner can add or remove entries.

---

## Testing Your Solution

The `tests/` directory contains a public test suite covering the existing (starter) endpoints. You can run it with `uv run pytest`.

We also have a **private test suite** that we will use when evaluating your submission. These tests are **not included in the repository** — your solution should be driven by the requirements in this README, not by reverse-engineering test expectations.

### Candidate-Written Tests (Required)

At the bottom of `tests/test_public.py`, you'll find three test classes with docstrings describing scenarios you must test:

- `TestCandidateSightingFilters` — tests for the sighting filter/pagination endpoint
- `TestCandidateCampaignLifecycle` — tests for campaign state transitions and sighting association
- `TestCandidateConfirmation` — tests for the peer confirmation system

**You must implement these tests.** They should be meaningful — we're evaluating whether you understand the requirements well enough to write good tests, not just whether your code works. Write at least 2–3 tests per class.

You are also encouraged to write additional tests beyond what's required.

---

## Subjective Considerations

We want to be transparent about the subjective metrics that we'll consider in your solution:

1. **Code quality & refactoring instincts** — The existing codebase has issues. We want to see whether you identify and address them. We are not expecting you to rewrite everything, but we want to see that you recognize problems and prioritize the most impactful fixes. We value the use of Pydantic models, dependency injection, and proper separation of concerns.

2. **Data modeling & state management** — Particularly around the campaign lifecycle and the confirmation system. How do you enforce invariants? Where do you put that logic?

3. **Performance awareness** — Do your queries scale? Did you investigate and address the reported slowness?

4. **API design** — Are your endpoints well-structured? Do they use appropriate status codes, response models, and error handling? Are error messages helpful? We care about how your API behaves when things go wrong, not just when things go right — invalid role access, nonexistent resources, malformed input, and boundary violations all matter.

5. **Code organization** — How do you structure the project? Where does business logic live versus routing versus data access?

---

## Rules & Expectations

- You may use any libraries you'd like, but please stick to the basic tech stack that the existing code is written in
- Please create a git repository for your solution and use version control as you develop it
- You may add/append any datasets if you want -- see `[PokéAPI](https://pokeapi.co/)` if you need a source of Pokémon information
- You have **6** hours from the time this task is sent to you to email us back your completed solution, but we anticipate that this shouldn't take more than 2-3.
- **Prioritization is part of the assessment.** There are 7 features plus the seed script fix. If you can't complete everything, prioritize depth over breadth — we'd rather see 4 well-implemented features with clean code and tests than 7 rushed ones. Explain your prioritization in `NOTES.md`.
- Include a `NOTES.md` file describing:
  - Any refactoring you did and why
  - Design decisions and trade-offs (especially around anomaly detection and data modeling)
  - How you approached any performance issues
- Please submit your solution as a Git repository (or zip) with a clear README on how to run and test the project.

---

## Terminology

- A **Shiny** Pokémon is an extremely rare color variant of a species. In the games, the base encounter rate for a shiny Pokémon is approximately 1 in 8,192. A shiny sighting is considered more valuable than a non-shiny sighting of the same species.
- The concept of a Baby Pokémon was introduced in Gen II, as the "pre-evolution" for an existing Gen I Pokémon. Gens III and IV continued that trend by introducing more baby Pokémon.
- While there is technically no explicit criteria for what makes a Pokémon legendary, check out [this link](https://bulbapedia.bulbagarden.net/wiki/Legendary_Pok%C3%A9mon) if you want more information on legendaries and [this link](https://bulbapedia.bulbagarden.net/wiki/Mythical_Pok%C3%A9mon) for information on mythical Pokémon -- they are often conflated terms
- Gen I is the "Kanto" region, Gen II is the "Johto" region, Gen III is the "Hoenn" region, and Gen IV is the "Sinnoh" region
