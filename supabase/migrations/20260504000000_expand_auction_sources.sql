-- Expand auction_source enum with new government, aggregator, and bank sources
-- Also add indexes for city and source filtering

-- Central / Quasi-Govt
ALTER TYPE auction_source ADD VALUE IF NOT EXISTS 'ibbi' AFTER 'ecourts';
ALTER TYPE auction_source ADD VALUE IF NOT EXISTS 'baanknet' AFTER 'ibbi';

-- Delhi
ALTER TYPE auction_source ADD VALUE IF NOT EXISTS 'dda' AFTER 'baanknet';
ALTER TYPE auction_source ADD VALUE IF NOT EXISTS 'dfc_delhi' AFTER 'dda';

-- Gurugram / Haryana
ALTER TYPE auction_source ADD VALUE IF NOT EXISTS 'hsvp' AFTER 'dfc_delhi';
ALTER TYPE auction_source ADD VALUE IF NOT EXISTS 'hsvp_procure247' AFTER 'hsvp';
ALTER TYPE auction_source ADD VALUE IF NOT EXISTS 'dtcp' AFTER 'hsvp_procure247';

-- Meerut / UP
ALTER TYPE auction_source ADD VALUE IF NOT EXISTS 'mda' AFTER 'dtcp';
ALTER TYPE auction_source ADD VALUE IF NOT EXISTS 'yeida' AFTER 'mda';

-- Aggregators
ALTER TYPE auction_source ADD VALUE IF NOT EXISTS 'bank_eauctions' AFTER 'yeida';
ALTER TYPE auction_source ADD VALUE IF NOT EXISTS 'eauctions_india' AFTER 'bank_eauctions';
ALTER TYPE auction_source ADD VALUE IF NOT EXISTS 'auction_bazaar' AFTER 'eauctions_india';
ALTER TYPE auction_source ADD VALUE IF NOT EXISTS 'eauction_dekho' AFTER 'auction_bazaar';
ALTER TYPE auction_source ADD VALUE IF NOT EXISTS 'findauction' AFTER 'eauction_dekho';
ALTER TYPE auction_source ADD VALUE IF NOT EXISTS 'findauction_prop' AFTER 'findauction';
ALTER TYPE auction_source ADD VALUE IF NOT EXISTS 'auction_tiger' AFTER 'findauction_prop';

-- Individual Banks
ALTER TYPE auction_source ADD VALUE IF NOT EXISTS 'sbi' AFTER 'auction_tiger';
ALTER TYPE auction_source ADD VALUE IF NOT EXISTS 'pnb' AFTER 'sbi';
ALTER TYPE auction_source ADD VALUE IF NOT EXISTS 'bob' AFTER 'pnb';
ALTER TYPE auction_source ADD VALUE IF NOT EXISTS 'canara' AFTER 'bob';
ALTER TYPE auction_source ADD VALUE IF NOT EXISTS 'hdfc' AFTER 'canara';
ALTER TYPE auction_source ADD VALUE IF NOT EXISTS 'icici' AFTER 'hdfc';
ALTER TYPE auction_source ADD VALUE IF NOT EXISTS 'union' AFTER 'icici';
ALTER TYPE auction_source ADD VALUE IF NOT EXISTS 'yes_bank' AFTER 'union';

-- Indexes for faster city and source filtering
CREATE INDEX IF NOT EXISTS idx_bank_auctions_city ON bank_auctions (city);
CREATE INDEX IF NOT EXISTS idx_bank_auctions_source ON bank_auctions (source);
CREATE INDEX IF NOT EXISTS idx_court_auctions_city ON court_auctions (city);

-- Update city column defaults from 'Gurugram' to 'Delhi NCR' to match ORM models
ALTER TABLE bank_auctions ALTER COLUMN city SET DEFAULT 'Delhi NCR';
ALTER TABLE court_auctions ALTER COLUMN city SET DEFAULT 'Delhi NCR';
ALTER TABLE auction_alerts ALTER COLUMN city SET DEFAULT 'Delhi NCR';
