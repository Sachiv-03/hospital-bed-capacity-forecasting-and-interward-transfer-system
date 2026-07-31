-- Step 4: PostgreSQL Database Initialization Script
-- Hospital Bed Capacity Forecasting & Intelligent Inter-Ward Transfer System

-- Create Database if not exists
SELECT 'CREATE DATABASE hospital_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'hospital_db')\gexec

-- Connect to database
\c hospital_db;

-- Create User if not exists
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = 'hospital_user') THEN
      CREATE ROLE hospital_user WITH LOGIN PASSWORD 'hospital_password';
   END IF;
END
$do$;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE hospital_db TO hospital_user;
GRANT ALL ON SCHEMA public TO hospital_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO hospital_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO hospital_user;

-- Create extension for UUID generation if needed in future phases
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Log completion
RAISE NOTICE 'Database hospital_db and user hospital_user initialized successfully.';
