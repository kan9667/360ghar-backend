-- ============================================================
-- 20260608000000: Normalize lifestyle enum values to canonical set
-- ============================================================
-- Maps all legacy/alternative values stored in users table to the
-- canonical values used by both the Flutter and Web UIs:
--
--   smoking_drinking:  neither, smoke_outside, drink_occasionally, both_fine
--   cleanliness:       minimal, tidy, spotless
--   guests_policy:     no_overnight_guests, occasional_ok, open_house
--   work_style:        wfh, office, hybrid
--   food_habits:       vegetarian, vegan, non_vegetarian, eggetarian, no_preference
--   sleep_schedule:    early_bird, flexible, night_owl
-- ============================================================

-- smoking_drinking
UPDATE users SET flatmates_smoking_drinking = 'neither'
  WHERE flatmates_smoking_drinking IN ('no', 'none', 'never');
UPDATE users SET flatmates_smoking_drinking = 'drink_occasionally'
  WHERE flatmates_smoking_drinking IN ('socially', 'occasionally');
UPDATE users SET flatmates_smoking_drinking = 'both_fine'
  WHERE flatmates_smoking_drinking IN ('regularly', 'no_preference');

-- cleanliness
UPDATE users SET flatmates_cleanliness = 'minimal'
  WHERE flatmates_cleanliness IN ('laid_back', 'messy');
UPDATE users SET flatmates_cleanliness = 'tidy'
  WHERE flatmates_cleanliness IN ('balanced', 'clean');
UPDATE users SET flatmates_cleanliness = 'spotless'
  WHERE flatmates_cleanliness IN ('meticulous', 'neat_freak');

-- guests_policy
UPDATE users SET flatmates_guests_policy = 'no_overnight_guests'
  WHERE flatmates_guests_policy IN ('rarely', 'no_overnight');
UPDATE users SET flatmates_guests_policy = 'occasional_ok'
  WHERE flatmates_guests_policy = 'occasionally';
UPDATE users SET flatmates_guests_policy = 'open_house'
  WHERE flatmates_guests_policy = 'comfortable';

-- work_style
UPDATE users SET flatmates_work_style = 'wfh'
  WHERE flatmates_work_style = 'wfh_mostly';
UPDATE users SET flatmates_work_style = 'office'
  WHERE flatmates_work_style = 'office_mostly';
UPDATE users SET flatmates_work_style = 'hybrid'
  WHERE flatmates_work_style = 'mixed';

-- food_habits
UPDATE users SET flatmates_food_habits = 'vegetarian'
  WHERE flatmates_food_habits = 'veg';
UPDATE users SET flatmates_food_habits = 'non_vegetarian'
  WHERE flatmates_food_habits = 'non_veg';

-- sleep_schedule
UPDATE users SET flatmates_sleep_schedule = 'early_bird'
  WHERE flatmates_sleep_schedule = 'before_7';
UPDATE users SET flatmates_sleep_schedule = 'flexible'
  WHERE flatmates_sleep_schedule = '7_to_9';
UPDATE users SET flatmates_sleep_schedule = 'night_owl'
  WHERE flatmates_sleep_schedule = 'after_9';

-- ============================================================
-- Update catalog entries to use canonical values
-- ============================================================
UPDATE app_catalogs
SET payload = $${
    "questions": [
        {
            "id": "q1",
            "text": "What time do you usually wake up?",
            "dimension": "sleep_schedule",
            "options": [
                {"id": "early_bird", "label": "Early bird (before 7 AM)"},
                {"id": "flexible", "label": "Flexible (7 – 9 AM)"},
                {"id": "night_owl", "label": "Night owl (after 9 AM)"}
            ]
        },
        {
            "id": "q2",
            "text": "How tidy are you?",
            "dimension": "cleanliness",
            "options": [
                {"id": "minimal", "label": "Minimal — lived-in is fine"},
                {"id": "tidy", "label": "Tidy — things in their place"},
                {"id": "spotless", "label": "Spotless — everything pristine"}
            ]
        },
        {
            "id": "q3",
            "text": "How often do you have guests over?",
            "dimension": "guests_policy",
            "options": [
                {"id": "no_overnight_guests", "label": "No overnight guests"},
                {"id": "occasional_ok", "label": "Occasional guests are ok"},
                {"id": "open_house", "label": "Open house — always welcome"}
            ]
        },
        {
            "id": "q4",
            "text": "What best describes your food habits?",
            "dimension": "food_habits",
            "options": [
                {"id": "vegetarian", "label": "Vegetarian"},
                {"id": "vegan", "label": "Vegan"},
                {"id": "non_vegetarian", "label": "Non-Vegetarian"},
                {"id": "eggetarian", "label": "Eggetarian"},
                {"id": "no_preference", "label": "No Preference"}
            ]
        },
        {
            "id": "q5",
            "text": "How do you feel about smoking / drinking at home?",
            "dimension": "smoking_drinking",
            "options": [
                {"id": "neither", "label": "Neither"},
                {"id": "smoke_outside", "label": "Smoke outside only"},
                {"id": "drink_occasionally", "label": "Drink occasionally"},
                {"id": "both_fine", "label": "Both are fine"}
            ]
        },
        {
            "id": "q6",
            "text": "What is your typical work setup?",
            "dimension": "work_style",
            "options": [
                {"id": "wfh", "label": "Work from home"},
                {"id": "office", "label": "Go to office"},
                {"id": "hybrid", "label": "Hybrid"}
            ]
        }
    ]
}$$::jsonb,
    version = 2
WHERE key = 'flatmates_lifestyle_quiz';

-- Update smoking options catalog
UPDATE app_catalogs
SET payload = $${
    "items": [
        {"id": "neither", "label": "Neither"},
        {"id": "smoke_outside", "label": "Smoke Outside"},
        {"id": "drink_occasionally", "label": "Drink Occasionally"},
        {"id": "both_fine", "label": "Both Fine"}
    ]
}$$::jsonb,
    version = 2
WHERE key = 'flatmates_smoking_options';

-- Update work styles catalog
UPDATE app_catalogs
SET payload = $${
    "items": [
        {"id": "wfh", "label": "Work from Home"},
        {"id": "office", "label": "Office"},
        {"id": "hybrid", "label": "Hybrid"}
    ]
}$$::jsonb,
    version = 2
WHERE key = 'flatmates_work_styles';

-- Update food habits catalog
UPDATE app_catalogs
SET payload = $${
    "items": [
        {"id": "vegetarian", "label": "Vegetarian"},
        {"id": "vegan", "label": "Vegan"},
        {"id": "non_vegetarian", "label": "Non-Vegetarian"},
        {"id": "eggetarian", "label": "Eggetarian"},
        {"id": "no_preference", "label": "No Preference"}
    ]
}$$::jsonb,
    version = 2
WHERE key = 'flatmates_food_habits';

-- Update pets catalog to use canonical values
UPDATE app_catalogs
SET payload = $${
    "items": [
        {"id": "have_pets", "label": "Yes, I have pets"},
        {"id": "no_pets", "label": "No pets"},
        {"id": "pet_friendly", "label": "Pet-friendly"}
    ]
}$$::jsonb,
    version = 2
WHERE key = 'flatmates_pets_options';
