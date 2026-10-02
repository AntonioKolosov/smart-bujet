DO $$
DECLARE
    readonly_password text := current_setting('custom.mcp_readonly_password', true);
BEGIN
    IF readonly_password IS NULL OR readonly_password = '' THEN
        readonly_password := 'readonly_pass'; -- Fallback to default
    END IF;

    -- Create role mcp_readonly if it does not exist
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcp_readonly') THEN
        EXECUTE format('CREATE ROLE mcp_readonly WITH LOGIN PASSWORD %L', readonly_password);
    END IF;

    -- Grant permissions
    GRANT USAGE ON SCHEMA public TO mcp_readonly;
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcp_readonly;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO mcp_readonly;
END $$;
