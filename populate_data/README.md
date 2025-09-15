# Data Populators

This folder contains scripts to seed the database with initial or sample data used during development and testing. All entity populators now pull from JSON seed files under `populate_data/data/` so you can tweak sample content without touching Python code.

## JSON Seed Files
- `populate_data/data/agents.json` – 360Ghar agent profiles with metadata such as languages, experience level, and working hours.
- `populate_data/data/amenities.json` – canonical amenity definitions grouped by category.
- `populate_data/data/users.json` – onboarding users; `supabase_user_id` is optional and gets generated when omitted or `null`.
- `populate_data/data/faqs.json` – frequently asked questions for the public help centre.
- `populate_data/data/pages.json` – CMS-style pages for policies, terms, and other static copy.
- `populate_data/data/app_versions.json` – app versions for 360ghar_real_estate and 360ghar_short_stays across iOS, Android, and web platforms.

Update these files to adjust default records. Every populator parses the JSON, validates the payload, and skips entries that already exist in the database when possible.

## Comprehensive Loader

Populate all primary entities (agents, users, amenities, properties, FAQs) with a single command:

```bash
PYTHONPATH=/Users/sakshammittal/Documents/360ghar/backend python populate_data/load_comprehensive_data.py
```

Useful flags:

- `--quick` – reduce property volume for faster local runs.
- `--clear` – remove JSON-defined test data (agents, users, amenities, properties, FAQs) before exiting.

Behind the scenes the loader executes other populators in the correct dependency order, then assigns agents to users. FAQ content is upserted (`question` is treated as the unique key) so you can iterate on copy while keeping identifiers stable.

To remove seeded records without re-populating:

```bash
PYTHONPATH=/Users/sakshammittal/Documents/360ghar/backend python populate_data/clear_all_data.py
```

## Pages

The `PagePopulator` creates or updates CMS-like pages from `populate_data/data/pages.json`.

- Create pages (skip existing):

  ```bash
  PYTHONPATH=/Users/sakshammittal/Documents/360ghar/backend python populate_data/populate_pages.py
  ```

- Create or update existing pages (upsert by `unique_name`):

  ```bash
  PYTHONPATH=/Users/sakshammittal/Documents/360ghar/backend python populate_data/populate_pages.py --update
  ```

- Clear all pages:

  ```bash
  PYTHONPATH=/Users/sakshammittal/Documents/360ghar/backend python populate_data/populate_pages.py --clear
  ```

- Use a custom JSON file:

  ```bash
  PYTHONPATH=/Users/sakshammittal/Documents/360ghar/backend python populate_data/populate_pages.py --file path/to/pages.json
  ```

Notes:
- Pages are identified by `unique_name` and created if missing. With `--update`, existing pages are updated in place.
- Ensure your database is running and `ASYNC_DATABASE_URL` is configured in `.env`.

## FAQs

The `FAQPopulator` seeds the `faqs` table from `populate_data/data/faqs.json`.

- Create FAQs (skip existing):

  ```bash
  PYTHONPATH=/Users/sakshammittal/Documents/360ghar/backend python populate_data/populate_faqs.py
  ```

- Create or update FAQs (use `question` as the unique key):

  ```bash
  PYTHONPATH=/Users/sakshammittal/Documents/360ghar/backend python populate_data/populate_faqs.py --update
  ```

- Clear JSON-defined FAQs:

  ```bash
  PYTHONPATH=/Users/sakshammittal/Documents/360ghar/backend python populate_data/populate_faqs.py --clear
  ```

- Use a custom JSON file:

  ```bash
  PYTHONPATH=/Users/sakshammittal/Documents/360ghar/backend python populate_data/populate_faqs.py --file path/to/faqs.json
  ```

## App Versions

The `load_app_versions.py` script populates app version information for both 360ghar_real_estate and 360ghar_short_stays apps across all platforms.

- Load app versions:

  ```bash
  PYTHONPATH=/Users/sakshammittal/Documents/360ghar/backend python populate_data/load_app_versions.py
  ```

- Clear existing app versions before loading:

  ```bash
  PYTHONPATH=/Users/sakshammittal/Documents/360ghar/backend python populate_data/load_app_versions.py --clear
  ```

Notes:
- Creates initial version records for both apps (1.0.0) on iOS, Android, and web platforms
- Includes release notes, download URLs, and mandatory update flags
- Use the `--clear` flag to remove all existing app versions before loading new ones

## Other Populators

`AgentPopulator`, `UserPopulator`, `AmenityPopulator`, and `FAQPopulator` can also be invoked from your own async scripts or a REPL if you need granular control. Each class accepts optional `file_path` overrides so you can supply alternate JSON files when required.
