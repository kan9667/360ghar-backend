-- ============================================================
-- 20260608000001: Enforce strict PostgreSQL Enums for lifestyle
-- ============================================================
-- Creates enum types for lifestyle data and converts the
-- flatmates_* columns in the users table to use these strict enums.
-- ============================================================

-- Create Enums
CREATE TYPE flatmates_sleep_schedule_type AS ENUM ('early_bird', 'flexible', 'night_owl');
CREATE TYPE flatmates_cleanliness_type AS ENUM ('minimal', 'tidy', 'spotless');
CREATE TYPE flatmates_guests_policy_type AS ENUM ('no_overnight_guests', 'occasional_ok', 'open_house');
CREATE TYPE flatmates_food_habits_type AS ENUM ('vegetarian', 'vegan', 'non_vegetarian', 'eggetarian', 'no_preference');
CREATE TYPE flatmates_smoking_drinking_type AS ENUM ('neither', 'smoke_outside', 'drink_occasionally', 'both_fine');
CREATE TYPE flatmates_work_style_type AS ENUM ('wfh', 'office', 'hybrid');

-- Alter the users table to convert VARCHAR to ENUMs using an explicit cast
ALTER TABLE users
  ALTER COLUMN flatmates_sleep_schedule TYPE flatmates_sleep_schedule_type USING flatmates_sleep_schedule::flatmates_sleep_schedule_type,
  ALTER COLUMN flatmates_cleanliness TYPE flatmates_cleanliness_type USING flatmates_cleanliness::flatmates_cleanliness_type,
  ALTER COLUMN flatmates_guests_policy TYPE flatmates_guests_policy_type USING flatmates_guests_policy::flatmates_guests_policy_type,
  ALTER COLUMN flatmates_food_habits TYPE flatmates_food_habits_type USING flatmates_food_habits::flatmates_food_habits_type,
  ALTER COLUMN flatmates_smoking_drinking TYPE flatmates_smoking_drinking_type USING flatmates_smoking_drinking::flatmates_smoking_drinking_type,
  ALTER COLUMN flatmates_work_style TYPE flatmates_work_style_type USING flatmates_work_style::flatmates_work_style_type;
