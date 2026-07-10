-- Add vendor tracking fields to maintenance_requests.
-- The AI agent and MCP tools reference these columns; they were missing
-- from the original schema, causing AttributeError at runtime.
ALTER TABLE maintenance_requests ADD COLUMN IF NOT EXISTS vendor_name TEXT;
ALTER TABLE maintenance_requests ADD COLUMN IF NOT EXISTS vendor_contact TEXT;
