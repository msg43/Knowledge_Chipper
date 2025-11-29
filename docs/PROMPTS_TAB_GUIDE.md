# Prompts Tab User Guide

## Overview

The enhanced Prompts Tab provides comprehensive management of system prompts and pipeline configuration. You can:

- **View and edit** all system prompts
- **Import new prompts** from external files
- **Delete unused prompts** with safety checks
- **Assign prompts** to specific pipeline stages
- **Track prompt usage** across the system

## Interface Layout

The Prompts Tab is divided into two main sections:

### Left Panel: Pipeline Stage Assignments

Shows all processing stages in the HCE pipeline with their current prompt assignments:

#### Pipeline Stages:

1. **Unified Miner ⭐ ACTIVE** - Extracts ALL entities in one pass: claims, jargon, people, and mental models from content segments (v2 schema with full evidence structure)
   - Uses dynamic prompt selection based on Content Type and Selectivity settings
   - Content-Type-Specific Prompts:
     - `unified_miner_transcript_own.txt` for Transcript (Own)
     - `unified_miner_transcript_third_party.txt` for Transcript (Third-party)
     - `unified_miner_document.txt` for Document (PDF/eBook)
   - Selectivity-Based Prompts:
     - `unified_miner_liberal.txt` for liberal extraction
     - `unified_miner_moderate.txt` for moderate extraction
     - `unified_miner_conservative.txt` for conservative extraction
   - Fallback: `unified_miner.txt` (used when content-type/selectivity prompts don't exist)
   - All prompt variants are shown with "Edit" buttons for direct access

2. **Flagship Evaluator ⭐ ACTIVE** - Reviews and ranks ALL extracted entities (claims, jargon, people, concepts) by importance and quality in parallel
   - Uses a single prompt: `flagship_evaluator.txt`
   - Dropdown menu to select assigned prompt
   - "View Assigned Prompt" button to load and inspect the prompt

3. **Skimmer (Optional)** - Performs high-level overview to identify key milestones
   - NOT used in main pipeline but available for custom workflows
   - Dropdown menu to select assigned prompt
   - "View Assigned Prompt" button to load and inspect the prompt

### Right Panel: Prompt Library & Editor

Manages the complete collection of available prompts:

#### Features:

- **Import Prompt** button - Load new prompts from your file system
- **Delete Prompt** button - Remove unused prompts (with safety checks)
- **Prompt List** - Shows all available prompts with icons:
  - ⚙️ = HCE system prompt (used by pipeline)
  - 📄 = Config prompt (general purpose)
- **Usage Indicator** - Highlighted label showing which pipeline stages use the selected prompt
- **Prompt Editor** - Large text editor for viewing and modifying prompt content
- **Save Changes** - Saves modifications to the prompt file
- **Revert Changes** - Discards unsaved edits

## How to Use

### Viewing Prompts

1. Select any prompt from the list in the right panel
2. The prompt content appears in the editor below
3. The usage indicator shows which pipeline stages (if any) use this prompt
4. Active pipeline prompts are highlighted in blue; unused prompts in gray

### Editing Prompts

1. Select a prompt from the list
2. Edit the content in the text editor
3. The "Save Changes" button becomes enabled
4. Click "Save Changes" to update the prompt
5. If the prompt is used by pipeline stages, you'll see a warning that changes take effect on the next run
6. Click "Revert Changes" to discard modifications

### Importing New Prompts

1. Click the **📥 Import Prompt** button
2. Select a `.txt` file from your computer
3. Choose the destination:
   - **Yes** → HCE Prompts directory (for pipeline use)
   - **No** → Config Prompts directory (for general use)
4. If a file with the same name exists, you'll be asked to confirm overwrite
5. The new prompt appears in the list and can be assigned to pipeline stages

### Deleting Prompts

1. Select the prompt you want to delete
2. Click the **🗑️ Delete Prompt** button
3. If the prompt is currently assigned to any pipeline stage, deletion is blocked with a warning
4. You must first reassign those stages to different prompts
5. Confirm the deletion (this cannot be undone)
6. The prompt is removed from the list

### Assigning Prompts to Pipeline Stages

**For Flagship Evaluator and Skimmer:**
1. In the left panel, find the pipeline stage you want to configure
2. Click the dropdown menu under that stage
3. Select a prompt from the list
4. A confirmation dialog shows the assignment was successful
5. The change takes effect immediately for future processing runs
6. The prompt file is copied to the stage's expected location

**For Unified Miner:**
- Unified Miner uses automatic prompt selection based on Content Type and Selectivity settings
- To edit prompts, use the "Edit" buttons next to each prompt variant in the Unified Miner section
- The system automatically selects the appropriate prompt during processing:
  1. First checks for content-type-specific prompt (if Content Type is set)
  2. Then checks for selectivity-based prompt (if Selectivity is set)
  3. Falls back to `unified_miner.txt` if neither exists

### Viewing Stage Assignments

1. Click the **"View Assigned Prompt"** button for any stage
2. The right panel automatically selects and displays that prompt
3. The usage indicator confirms the stage assignment
4. You can edit the prompt directly from there

### Refreshing Assignments

Click the **🔄 Refresh Assignments** button to:
- Reload all prompts from disk
- Update the dropdown menus
- Rescan which prompts are assigned to which stages
- Useful after external file modifications

## Safety Features

### Deletion Protection

You cannot delete a prompt that is currently assigned to any pipeline stage. This prevents accidentally breaking the processing pipeline.

### Usage Tracking

The system clearly shows:
- Which stages use each prompt (blue highlight)
- Which prompts are unassigned (gray)
- Warning when saving changes to active pipeline prompts

### Revert Changes

Unsaved modifications can always be reverted back to the saved file content.

### Assignment Confirmation

Every time you assign a prompt to a pipeline stage, you receive clear confirmation of the change.

## Prompt Directories

The system manages prompts in two locations:

### HCE Prompts
`src/knowledge_system/processors/hce/prompts/`
- System prompts used by the processing pipeline
- Automatically loaded by processor modules
- These are the prompts assigned to pipeline stages

### Config Prompts
`config/prompts/`
- User-defined or experimental prompts
- Can be used for custom processing
- Not automatically loaded by the system

## Tips & Best Practices

1. **Backup before editing** - Make a copy of important prompts before significant changes
2. **Test new prompts** - Import new prompts to the config directory first, test them, then assign to pipeline stages
3. **Document changes** - Add comments in your prompts explaining modifications
4. **Use descriptive names** - Name imported prompts clearly (e.g., `unified_miner_detailed.txt`)
5. **Version prompts** - Keep variations with version numbers (e.g., `skim_v2.txt`)
6. **Monitor impact** - After changing a pipeline prompt, check the Review tab to see how results differ

## Troubleshooting

### Prompt doesn't appear in dropdown
- Make sure the file has a `.txt` extension
- Check that it's in either the HCE prompts or config prompts directory
- Click "🔄 Refresh Assignments" to reload

### Can't delete a prompt
- Check which stages are using it (shown in usage indicator)
- Assign those stages to different prompts first
- Then try deleting again

### Changes not taking effect
- Make sure you clicked "Save Changes" after editing
- For pipeline prompts, changes apply to the next processing run
- Already-processed content won't be affected

### Prompt editor shows wrong content
- Click "Revert Changes" to reload from disk
- Check that you selected the correct prompt from the list
- Use "View Assigned Prompt" button to navigate to the right prompt

## Advanced Usage

### Creating Custom Pipeline Variants

1. Import a base prompt (e.g., `unified_miner.txt`)
2. Edit it for your specific use case
3. Save with a descriptive name
4. Assign to the appropriate pipeline stage
5. Process content and compare results
6. Keep or revert based on quality

### A/B Testing Prompts

1. Process content with prompt A
2. Note the results (claims extracted, quality scores)
3. Assign prompt B to the same stage
4. Reprocess the same content
5. Compare results in the Review tab
6. Choose the better performing prompt

### Sharing Prompts

Export prompts by:
1. Selecting the prompt in the list
2. Noting the file path from the usage indicator
3. Copying that file to share with others

Import received prompts:
1. Click "📥 Import Prompt"
2. Select the received `.txt` file
3. Choose appropriate directory
4. Test before assigning to pipeline stages

## Technical Details

### Prompt Assignment Mechanism

When you assign a prompt to a pipeline stage:
1. The system finds the source prompt file
2. Reads its content
3. Writes that content to the stage's expected prompt path
4. The processing module loads it automatically on next run

### Usage Detection

The system detects prompt usage by:
1. Reading each pipeline stage's prompt file
2. Comparing content to available prompts
3. Matching identical content to identify assignments
4. This works even if files are at different paths

### Supported File Types

Currently only `.txt` files are supported for prompts. Future versions may support:
- Markdown files with structured sections
- YAML files with embedded metadata
- Template files with variable substitution
