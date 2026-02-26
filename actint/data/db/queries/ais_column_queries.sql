-- AIS Column Information Queries
-- SQLite column schema inspection queries

-- ============================================================================
-- Get column names and types for ais_positions table
-- ============================================================================
PRAGMA table_info(ais_positions);

-- ============================================================================
-- Get column names and types for vessels table
-- ============================================================================
PRAGMA table_info(vessels);

-- ============================================================================
-- Get column names and types for fleets table
-- ============================================================================
PRAGMA table_info(fleets);

-- ============================================================================
-- Get all table names in database
-- ============================================================================
SELECT name 
FROM sqlite_master 
WHERE type='table' AND name NOT LIKE 'sqlite_%'
ORDER BY name;

-- ============================================================================
-- Get table names and their creation SQL
-- ============================================================================
SELECT 
    name AS table_name,
    sql AS create_statement
FROM sqlite_master
WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
ORDER BY name;
