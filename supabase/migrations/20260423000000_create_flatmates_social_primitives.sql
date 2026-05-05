ALTER TABLE users
    ADD COLUMN IF NOT EXISTS flatmates_mode TEXT,
    ADD COLUMN IF NOT EXISTS flatmates_profile_status TEXT NOT NULL DEFAULT 'draft',
    ADD COLUMN IF NOT EXISTS flatmates_onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS flatmates_bio TEXT,
    ADD COLUMN IF NOT EXISTS flatmates_budget_min DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS flatmates_budget_max DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS flatmates_move_in_timeline TEXT,
    ADD COLUMN IF NOT EXISTS flatmates_city TEXT,
    ADD COLUMN IF NOT EXISTS flatmates_locality TEXT,
    ADD COLUMN IF NOT EXISTS flatmates_sleep_schedule TEXT,
    ADD COLUMN IF NOT EXISTS flatmates_cleanliness TEXT,
    ADD COLUMN IF NOT EXISTS flatmates_food_habits TEXT,
    ADD COLUMN IF NOT EXISTS flatmates_smoking_drinking TEXT,
    ADD COLUMN IF NOT EXISTS flatmates_guests_policy TEXT,
    ADD COLUMN IF NOT EXISTS flatmates_work_style TEXT,
    ADD COLUMN IF NOT EXISTS flatmates_last_active_at TIMESTAMPTZ;

ALTER TABLE user_swipes
    ALTER COLUMN property_id DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS target_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS context_property_id INTEGER REFERENCES properties(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS target_type TEXT NOT NULL DEFAULT 'property',
    ADD COLUMN IF NOT EXISTS swipe_action TEXT NOT NULL DEFAULT 'like';

CREATE INDEX IF NOT EXISTS idx_user_swipes_target_user
    ON user_swipes (user_id, target_user_id);

CREATE INDEX IF NOT EXISTS idx_user_swipes_target_type
    ON user_swipes (user_id, target_type);

CREATE UNIQUE INDEX IF NOT EXISTS idx_user_swipes_unique_target_user
    ON user_swipes (user_id, target_user_id)
    WHERE target_user_id IS NOT NULL;

ALTER TABLE visits
    ADD COLUMN IF NOT EXISTS counterparty_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS conversation_id INTEGER,
    ADD COLUMN IF NOT EXISTS match_id INTEGER,
    ADD COLUMN IF NOT EXISTS visit_context TEXT NOT NULL DEFAULT 'property_tour';

CREATE TABLE IF NOT EXISTS user_matches (
    id BIGSERIAL PRIMARY KEY,
    user_one_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_two_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    context_property_id INTEGER REFERENCES properties(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_user_matches_unique_pair
    ON user_matches (user_one_id, user_two_id);

CREATE INDEX IF NOT EXISTS idx_user_matches_status
    ON user_matches (status);

CREATE TABLE IF NOT EXISTS user_conversations (
    id BIGSERIAL PRIMARY KEY,
    user_one_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_two_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_by_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    context_property_id INTEGER REFERENCES properties(id) ON DELETE SET NULL,
    source TEXT NOT NULL DEFAULT 'listing_interest',
    status TEXT NOT NULL DEFAULT 'active',
    last_message_preview TEXT,
    last_message_at TIMESTAMPTZ,
    context_data JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_user_conversations_unique_pair
    ON user_conversations (user_one_id, user_two_id);

CREATE INDEX IF NOT EXISTS idx_user_conversations_last_message
    ON user_conversations (last_message_at DESC NULLS LAST);

ALTER TABLE visits
    ADD CONSTRAINT visits_conversation_id_fkey
        FOREIGN KEY (conversation_id) REFERENCES user_conversations(id) ON DELETE SET NULL;

ALTER TABLE visits
    ADD CONSTRAINT visits_match_id_fkey
        FOREIGN KEY (match_id) REFERENCES user_matches(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS user_messages (
    id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES user_conversations(id) ON DELETE CASCADE,
    sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body TEXT,
    attachment_url TEXT,
    message_type TEXT NOT NULL DEFAULT 'text',
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_user_messages_conversation
    ON user_messages (conversation_id, created_at);

CREATE INDEX IF NOT EXISTS idx_user_messages_unread
    ON user_messages (conversation_id, read_at);

CREATE TABLE IF NOT EXISTS user_blocks (
    id BIGSERIAL PRIMARY KEY,
    blocker_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blocked_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_user_blocks_unique_pair
    ON user_blocks (blocker_user_id, blocked_user_id);

CREATE TABLE IF NOT EXISTS user_reports (
    id BIGSERIAL PRIMARY KEY,
    reporter_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reported_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    conversation_id BIGINT REFERENCES user_conversations(id) ON DELETE SET NULL,
    property_id INTEGER REFERENCES properties(id) ON DELETE SET NULL,
    reason TEXT NOT NULL DEFAULT 'other',
    status TEXT NOT NULL DEFAULT 'open',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_user_reports_reported_user
    ON user_reports (reported_user_id, status);

CREATE INDEX IF NOT EXISTS idx_user_reports_reporter_user
    ON user_reports (reporter_user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS app_catalogs (
    id BIGSERIAL PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    version INTEGER NOT NULL DEFAULT 1,
    payload JSONB NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

INSERT INTO app_catalogs (key, version, payload, is_active)
VALUES
    (
        'flatmates_modes',
        1,
        $${
            "items": [
                {"id": "co_hunter", "label": "Find a Flat / Flatmate", "description": "I want to find a place or a flatmate to stay with"},
                {"id": "room_poster", "label": "List My Flat / Find Flatmate", "description": "I want to list my flat or find a flatmate"},
                {"id": "open_to_both", "label": "Open to Both", "description": "I'm flexible, open to both finding a place and listing my flat"}
            ]
        }$$::jsonb,
        TRUE
    ),
    (
        'flatmates_move_in_timelines',
        1,
        $${
            "items": [
                {"id": "immediately", "label": "Immediately"},
                {"id": "within_2_weeks", "label": "Within 2 Weeks"},
                {"id": "within_1_month", "label": "Within 1 Month"},
                {"id": "just_exploring", "label": "Just Exploring"}
            ]
        }$$::jsonb,
        TRUE
    ),
    (
        'flatmates_onboarding_quiz',
        1,
        $${
            "dimensions": [
                {"id": "sleep_schedule", "label": "Sleep Schedule", "options": ["early_bird", "balanced", "night_owl"]},
                {"id": "cleanliness", "label": "Cleanliness", "options": ["laid_back", "balanced", "meticulous"]},
                {"id": "food_habits", "label": "Food Habits", "options": ["veg", "vegan", "eggetarian", "non_veg"]},
                {"id": "smoking_drinking", "label": "Smoking / Drinking", "options": ["never", "occasionally", "regularly"]},
                {"id": "guests_policy", "label": "Guests Policy", "options": ["rarely", "occasionally", "comfortable"]},
                {"id": "work_style", "label": "Work Style", "options": ["office", "hybrid", "wfh"]}
            ]
        }$$::jsonb,
        TRUE
    ),
    (
        'flatmates_vibe_tags',
        1,
        $${
            "items": [
                "Bachelor-friendly",
                "Quiet",
                "Active Community",
                "Family-dominant",
                "Pet-friendly",
                "Visitor-friendly"
            ]
        }$$::jsonb,
        TRUE
    ),
    (
        'flatmates_popular_cities',
        1,
        $${
            "items": [
                {"id": "bangalore", "label": "Bangalore", "state": "Karnataka"},
                {"id": "hyderabad", "label": "Hyderabad", "state": "Telangana"},
                {"id": "pune", "label": "Pune", "state": "Maharashtra"},
                {"id": "chennai", "label": "Chennai", "state": "Tamil Nadu"},
                {"id": "mumbai", "label": "Mumbai", "state": "Maharashtra"}
            ]
        }$$::jsonb,
        TRUE
    ),
    (
        'flatmates_room_types',
        1,
        $${
            "items": [
                {"id": "private_room", "label": "Private Room"},
                {"id": "shared_room", "label": "Shared Room"},
                {"id": "master_bedroom", "label": "Master Bedroom"}
            ]
        }$$::jsonb,
        TRUE
    ),
    (
        'flatmates_society_types',
        1,
        $${
            "items": [
                {"id": "gated", "label": "Gated Society"},
                {"id": "independent", "label": "Independent Building"},
                {"id": "co_living", "label": "Co-living"},
                {"id": "pg", "label": "PG"}
            ]
        }$$::jsonb,
        TRUE
    ),
    (
        'flatmates_flat_configs',
        1,
        $${
            "items": [
                {"id": "1BHK", "label": "1 BHK"},
                {"id": "2BHK", "label": "2 BHK"},
                {"id": "3BHK", "label": "3 BHK"},
                {"id": "4BHK+", "label": "4 BHK+"},
                {"id": "studio", "label": "Studio"}
            ]
        }$$::jsonb,
        TRUE
    ),
    (
        'flatmates_listing_amenities',
        1,
        $${
            "items": [
                {"id": "furnished", "label": "Furnished"},
                {"id": "semi_furnished", "label": "Semi Furnished"},
                {"id": "wifi", "label": "Wi-Fi"},
                {"id": "parking", "label": "Parking"},
                {"id": "security", "label": "24/7 Security"},
                {"id": "lift", "label": "Lift"},
                {"id": "washing_machine", "label": "Washing Machine"},
                {"id": "attached_bathroom", "label": "Attached Bathroom"},
                {"id": "balcony", "label": "Balcony"},
                {"id": "ac", "label": "AC"}
            ]
        }$$::jsonb,
        TRUE
    ),
    (
        'flatmates_non_negotiables',
        1,
        $${
            "items": [
                {"id": "food_veg_only", "label": "Vegetarian only"},
                {"id": "no_smoking", "label": "No smoking"},
                {"id": "no_drinking", "label": "No drinking"},
                {"id": "no_overnight_guests", "label": "No overnight guests"},
                {"id": "no_pets", "label": "No pets"},
                {"id": "no_parties", "label": "No parties"},
                {"id": "min_tidy", "label": "Keeps common areas tidy"}
            ]
        }$$::jsonb,
        TRUE
    ),
    (
        'flatmates_report_reasons',
        1,
        $${
            "items": [
                {"id": "spam", "label": "Spam"},
                {"id": "fake_profile", "label": "Fake Profile"},
                {"id": "abuse", "label": "Abuse"},
                {"id": "inappropriate", "label": "Inappropriate Content"},
                {"id": "other", "label": "Other"}
            ]
        }$$::jsonb,
        TRUE
    )
ON CONFLICT (key) DO UPDATE
SET version = EXCLUDED.version,
    payload = EXCLUDED.payload,
    is_active = EXCLUDED.is_active;
