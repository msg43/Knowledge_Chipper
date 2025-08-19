-- Add HCE-specific columns to summaries table

-- Add processing_type to track whether summary was created by legacy or HCE
ALTER TABLE summaries ADD COLUMN processing_type TEXT DEFAULT 'legacy' CHECK (processing_type IN ('legacy', 'hce'));

-- Add hce_data_json to store structured HCE output
ALTER TABLE summaries ADD COLUMN hce_data_json TEXT;

-- Create index on processing_type for efficient filtering
CREATE INDEX idx_summaries_processing_type ON summaries(processing_type);

-- Update metadata column if it doesn't exist
-- (Some installations might not have this column yet)
ALTER TABLE summaries ADD COLUMN IF NOT EXISTS metadata_json TEXT;
