-- SQL function to delete vectors by file ID
-- Run this in Supabase SQL editor if the function doesn't exist

CREATE OR REPLACE FUNCTION delete_vectors_by_file_id(target_file_id TEXT)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Delete all rows where metadata->>'id' matches the target file ID
    DELETE FROM documents 
    WHERE metadata->>'id' = target_file_id;
    
    -- Get the number of deleted rows
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Grant execute permission to service role
GRANT EXECUTE ON FUNCTION delete_vectors_by_file_id(TEXT) TO service_role;