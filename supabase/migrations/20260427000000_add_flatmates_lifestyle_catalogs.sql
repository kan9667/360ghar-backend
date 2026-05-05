-- ============================================================
-- 20260427000000: Add flatmates lifestyle & preference catalogs
-- ============================================================
-- Inserts catalog entries for quiz questions, icebreakers,
-- work styles, gender options, food habits, pets, smoking,
-- and furnishing options into the existing app_catalogs table.
-- ============================================================

INSERT INTO app_catalogs (key, version, payload, is_active)
VALUES
    (
        'flatmates_lifestyle_quiz',
        1,
        $${
            "questions": [
                {
                    "id": "q1",
                    "text": "What time do you usually wake up?",
                    "dimension": "sleep_schedule",
                    "options": [
                        {"id": "before_7", "label": "Before 7 AM"},
                        {"id": "7_to_9", "label": "7 – 9 AM"},
                        {"id": "after_9", "label": "After 9 AM"}
                    ]
                },
                {
                    "id": "q2",
                    "text": "How tidy are you?",
                    "dimension": "cleanliness",
                    "options": [
                        {"id": "laid_back", "label": "Laid-back"},
                        {"id": "balanced", "label": "Balanced"},
                        {"id": "meticulous", "label": "Meticulous"}
                    ]
                },
                {
                    "id": "q3",
                    "text": "How often do you have guests over?",
                    "dimension": "guests_policy",
                    "options": [
                        {"id": "rarely", "label": "Rarely"},
                        {"id": "occasionally", "label": "Occasionally"},
                        {"id": "comfortable", "label": "Very often"}
                    ]
                },
                {
                    "id": "q4",
                    "text": "What best describes your food habits?",
                    "dimension": "food_habits",
                    "options": [
                        {"id": "veg", "label": "Vegetarian"},
                        {"id": "eggetarian", "label": "Eggetarian"},
                        {"id": "non_veg", "label": "Non-Vegetarian"},
                        {"id": "vegan", "label": "Vegan"}
                    ]
                },
                {
                    "id": "q5",
                    "text": "How do you feel about smoking / drinking at home?",
                    "dimension": "smoking_drinking",
                    "options": [
                        {"id": "never", "label": "Not okay at all"},
                        {"id": "occasionally", "label": "Occasionally is fine"},
                        {"id": "regularly", "label": "Regularly is fine"}
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
        TRUE
    ),
    (
        'flatmates_icebreakers',
        1,
        $${
            "prompts": [
                {"id": "ib1", "text": "What's your go-to midnight snack?"},
                {"id": "ib2", "text": "Are you a morning person or a night owl?"},
                {"id": "ib3", "text": "What's one thing you can't live without at home?"},
                {"id": "ib4", "text": "Favourite way to unwind after work?"},
                {"id": "ib5", "text": "Do you prefer cooking or ordering in?"},
                {"id": "ib6", "text": "What's your weekend usually look like?"},
                {"id": "ib7", "text": "Netflix, Prime, or something else?"},
                {"id": "ib8", "text": "What kind of music do you listen to?"},
                {"id": "ib9", "text": "Do you like having people over?"},
                {"id": "ib10", "text": "Early bird or snooze-button person?"}
            ]
        }$$::jsonb,
        TRUE
    ),
    (
        'flatmates_work_styles',
        1,
        $${
            "items": [
                {"id": "wfh", "label": "Work from Home"},
                {"id": "office", "label": "Office"},
                {"id": "hybrid", "label": "Hybrid"}
            ]
        }$$::jsonb,
        TRUE
    ),
    (
        'flatmates_gender_options',
        1,
        $${
            "items": [
                {"id": "no_preference", "label": "No Preference"},
                {"id": "male_only", "label": "Male Only"},
                {"id": "female_only", "label": "Female Only"},
                {"id": "other", "label": "Other"}
            ]
        }$$::jsonb,
        TRUE
    ),
    (
        'flatmates_food_habits',
        1,
        $${
            "items": [
                {"id": "veg", "label": "Vegetarian"},
                {"id": "non_veg", "label": "Non-Vegetarian"},
                {"id": "eggetarian", "label": "Eggetarian"},
                {"id": "no_preference", "label": "No Preference"}
            ]
        }$$::jsonb,
        TRUE
    ),
    (
        'flatmates_pets_options',
        1,
        $${
            "items": [
                {"id": "yes", "label": "Yes, I have pets"},
                {"id": "no", "label": "No pets"},
                {"id": "no_preference", "label": "No Preference"}
            ]
        }$$::jsonb,
        TRUE
    ),
    (
        'flatmates_smoking_options',
        1,
        $${
            "items": [
                {"id": "no", "label": "No"},
                {"id": "yes", "label": "Yes"},
                {"id": "no_preference", "label": "No Preference"}
            ]
        }$$::jsonb,
        TRUE
    ),
    (
        'flatmates_furnishing',
        1,
        $${
            "items": [
                {"id": "any", "label": "Any"},
                {"id": "furnished", "label": "Furnished"},
                {"id": "semi_furnished", "label": "Semi Furnished"},
                {"id": "unfurnished", "label": "Unfurnished"}
            ]
        }$$::jsonb,
        TRUE
    )
ON CONFLICT (key) DO UPDATE
SET version = EXCLUDED.version,
    payload = EXCLUDED.payload,
    is_active = EXCLUDED.is_active;
