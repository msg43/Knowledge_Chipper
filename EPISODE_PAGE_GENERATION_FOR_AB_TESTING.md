# Episode Page Generation for AB Testing

**Created:** January 12, 2026  
**Status:** ✅ Complete and Tested

## Overview

The daemon now automatically generates full episode markdown files after each extraction, making it easy to perform AB testing between different LLM providers, models, and configurations.

## What Was Added

### 1. Automatic Episode Page Generation

After each successful extraction (Stage 3), the system now:
1. Saves all extraction results to the database in HCE-compatible format
2. Generates a complete episode markdown file with:
   - YAML frontmatter (metadata, title, URL, processing info)
   - Executive summary (from Pass 2 synthesis)
   - Claims grouped by speaker (with evidence quotes and timestamps)
   - People mentioned (with descriptions)
   - Jargon terms (with definitions)
   - Concepts/Mental Models (with descriptions)

### 2. Files Generated

Episode pages are saved to: `output/summaries/Summary_{title}_{source_id}.md`

Example filename: `output/summaries/Summary_Peter_Attia_Interview_dQw4w9WgXcQ.md`

### 3. Comprehensive Content

Each episode page includes:

**Header Section:**
- Title (H1)
- Thumbnail image (embedded YouTube thumbnail)

**Metadata Section:**
- Channel name
- Published date
- Duration (human-readable)
- View count
- Video URL (as clickable link)
- Processing timestamp
- LLM model and provider
- Processing cost and token usage

**YouTube AI Summary:**
- YouTube's own AI-generated summary (if available)
- Clearly separated from our analysis

**Executive Summary (AI Analysis):**
- Our comprehensive synthesis from Pass 2
- World-class narrative analysis
- Thematic organization of key insights

**Claims Section:**
- Grouped by speaker
- Each claim includes:
  - Claim text
  - Type (factual, opinion, etc.)
  - Tier (A/B/C with confidence label)
  - Evidence quotes with YouTube timestamp links

**People Section:**
- Names with descriptions
- Context about their role/mention

**Jargon Section:**
- Technical terms with definitions
- Domain classification

**Concepts Section:**
- Mental models and frameworks
- Descriptions and implications

### 4. Format Compatibility

The generated markdown uses the **exact same format** as the original Knowledge_Chipper episode pages:
- Same YAML structure
- Same heading hierarchy
- Same claim formatting
- Same evidence linking (with YouTube timestamps)
- Same speaker grouping
- Enhanced with metadata, thumbnails, and dual summaries

This ensures perfect compatibility for AB testing comparisons.

## Implementation Details

### Files Modified

1. **`daemon/services/processing_service.py`** - Main processing service
   - Added `_save_extraction_to_database()` - Stores TwoPassResult in database as HCE-compatible format
   - Added `_generate_episode_page()` - Generates full episode markdown via FileGenerationService
   - Added `_importance_to_tier()` - Converts importance scores (0-10) to tiers (A/B/C)
   - Updated `_process_job()` - Calls new methods after extraction stage

2. **`CHANGELOG.md`** - Documented new feature

### How It Works

```python
# After extraction completes (line 634 in processing_service.py):

1. Save to database:
   - Convert TwoPassResult → Summary record with hce_data_json
   - Store claims, jargon, people, concepts in database tables
   - Generate summary_id for tracking

2. Generate episode page:
   - Call FileGenerationService.generate_summary_markdown()
   - This internally uses _generate_hce_markdown() for consistent formatting
   - Returns path to generated markdown file
   - Path stored in job_data["episode_markdown_file"]
```

### Database Storage Format

The extraction results are stored in a `Summary` record with:
- `summary_id`: Unique identifier
- `source_id`: Links to media source
- `summary_text`: Long summary from Pass 2 synthesis
- `summary_type`: "two_pass"
- `hce_data_json`: Full structured data with claims, jargon, people, concepts
- `llm_model` and `llm_provider`: For tracking which models produced which results

## AB Testing Workflow

### 1. Run Extraction with Model A
```bash
# Via web UI: Select OpenAI GPT-4o
# Or via API:
curl -X POST http://localhost:8765/process \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://youtube.com/watch?v=VIDEO_ID",
    "extract_claims": true,
    "llm_provider": "openai",
    "llm_model": "gpt-4o"
  }'
```

Result: `output/summaries/Summary_Title_VIDEO_ID.md` (OpenAI version)

### 2. Run Extraction with Model B
```bash
# Via web UI: Select Anthropic Claude Sonnet 4.5
# Or via API:
curl -X POST http://localhost:8765/process \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://youtube.com/watch?v=VIDEO_ID",
    "extract_claims": true,
    "llm_provider": "anthropic",
    "llm_model": "claude-sonnet-4-20250514"
  }'
```

Result: Overwrites previous file OR save to different directory for comparison

### 3. Compare Results

Use any diff tool to compare:
```bash
# Visual diff
diff -u output_openai/Summary_Title_VIDEO_ID.md \
        output_anthropic/Summary_Title_VIDEO_ID.md

# Or use a visual diff tool like Beyond Compare, Kaleidoscope, etc.
```

### 4. Evaluate Quality

Compare:
- **Claim quality**: Are claims accurate, well-formed, properly scoped?
- **Evidence selection**: Are the best quotes chosen as evidence?
- **Speaker attribution**: Are speakers correctly identified?
- **Jargon extraction**: Are technical terms properly defined?
- **Summary quality**: Is the executive summary comprehensive and insightful?
- **Completeness**: Are all important claims captured?

## Benefits

### 1. Easy AB Testing
- No need to manually extract data from database
- Complete episode pages ready for comparison
- Same format as original code for familiarity

### 2. Version Control Friendly
- Markdown files can be committed to git
- Easy to see diffs between model outputs
- Historical record of model performance

### 3. Human Review Friendly
- Beautiful markdown format readable in any editor
- Can be opened in Obsidian for rich linking
- Can be converted to PDF or HTML for sharing

### 4. Testing Different Configurations
- Compare different LLM providers (OpenAI vs Anthropic vs Google)
- Compare different models (GPT-4o vs Claude Sonnet vs Gemini)
- Compare different temperature settings
- Compare different importance thresholds

## Example Output

```markdown
---
title: Summary of Peter Attia on Longevity and Exercise
source_id: dQw4w9WgXcQ
url: https://youtube.com/watch?v=dQw4w9WgXcQ
channel: Joe Rogan Experience
duration: 2h 0m
duration_seconds: 7200
published_at: '2024-03-15T14:30:00Z'
description: Dr. Peter Attia discusses the science of longevity, optimal exercise protocols, and the importance of VO2 max for healthspan...
thumbnail_url: https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg
view_count: 1500000
processed_at: '2026-01-12T11:00:00Z'
llm_provider: anthropic
llm_model: claude-sonnet-4-20250514
processing_cost: 0.1234
total_tokens: 85000
total_claims: 42
high_importance_claims: 15
tier_distribution:
  A: 15
  B: 18
  C: 9
---

# Peter Attia on Longevity and Exercise

![Thumbnail](https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg)

## Metadata

**Channel:** Joe Rogan Experience
**Published:** 2024-03-15
**Duration:** 2h 0m
**Views:** 1,500,000
**URL:** [https://youtube.com/watch?v=dQw4w9WgXcQ](https://youtube.com/watch?v=dQw4w9WgXcQ)
**Processed:** 2026-01-12 11:00:00
**LLM:** claude-sonnet-4-20250514 (anthropic)
**Processing Cost:** $0.1234
**Total Tokens:** 85,000

## YouTube AI Summary

Dr. Peter Attia joins Joe Rogan to explore the science of longevity, 
discussing how exercise, particularly cardio fitness measured by VO2 max, 
is the single strongest predictor of all-cause mortality. They cover optimal 
training protocols, the importance of muscle mass in aging, and practical 
strategies for extending healthspan.

---

## Executive Summary (AI Analysis)

Peter Attia discusses the latest research on longevity, emphasizing the 
critical importance of VO2 max for healthspan. He argues that exercise is 
the single most important intervention for extending healthy lifespan, 
surpassing even diet and sleep in its protective effects. The conversation 
explores specific training protocols, including Zone 2 cardio and high-intensity 
intervals, with detailed recommendations for different age groups...

[3-5 paragraphs of world-class synthesis]

## CLAIMS

### Claims by Peter Attia

#### 1. VO2 max is the strongest predictor of all-cause mortality
- *Type:* factual
- *Tier:* A (High Confidence)

##### Evidence
1. "People in the top 2% of VO2 max have a 5x lower risk of death 
   compared to the bottom 25%" [[00:15:30](https://youtube.com/watch?v=dQw4w9WgXcQ&t=930s)]
2. "This is a stronger predictor than smoking, diabetes, or 
   cardiovascular disease" [[00:16:15](https://youtube.com/watch?v=dQw4w9WgXcQ&t=975s)]

[... more claims ...]

## PEOPLE

- **Peter Attia**: Longevity physician and host of The Drive podcast
- **Joe Rogan**: Podcast host and comedian
- **Peter Diamandis**: Mentioned as expert on exponential technologies

## JARGON

- **VO2 max** (health): Maximum rate of oxygen consumption during exercise, 
  measured in mL/kg/min
- **Healthspan**: Number of years lived in good health, as opposed to lifespan
- **Zone 2 training**: Aerobic exercise at 60-70% of max heart rate

## CONCEPTS

- **Marginal Decade**: The last 10 years of life where health typically 
  declines rapidly
- **Centenarian Decathlon**: Training for the activities you want to do 
  in your 90s

---
*Generated from Knowledge System database on 2026-01-12 11:00:00*
*Processed using HCE (Hybrid Claim Extractor) v2.0*
```

## Testing Checklist

Before using for production AB testing, verify:

- [x] Episode page is generated after extraction completes
- [x] File is saved to `output/summaries/` directory
- [x] YAML frontmatter includes all metadata
- [x] Executive summary is present and well-formatted
- [x] Claims are properly grouped by speaker
- [x] Evidence quotes include YouTube timestamp links
- [x] People, jargon, and concepts sections are complete
- [x] File path is stored in job_data for tracking

## Future Enhancements

Possible future improvements:
1. **Side-by-side HTML output** - Generate HTML with both versions side-by-side
2. **Automated quality metrics** - Calculate claim quality scores automatically
3. **Batch AB testing** - Run multiple videos through multiple models
4. **Model performance dashboard** - Track which models perform best on which content types
5. **Cost tracking** - Include API cost comparison in output

## Troubleshooting

### Episode page not generated
- Check `logs/` for error messages
- Verify database write succeeded
- Confirm `output/summaries/` directory exists and is writable

### Incomplete data in episode page
- Check if extraction completed successfully
- Verify all claims have required fields (claim_text, importance, etc.)
- Check database Summary record has hce_data_json populated

### Format doesn't match original
- Verify using FileGenerationService.generate_summary_markdown()
- Don't call _generate_hce_markdown() directly
- Check that database Summary record has correct format

## Related Documentation

- `docs/FILE_ORGANIZATION.md` - Output file structure
- `CURRENT_ACTIVE_PROMPTS.md` - Two-pass prompt architecture
- `src/knowledge_system/services/file_generation.py` - Markdown generation code
- `daemon/services/processing_service.py` - Processing pipeline

---

**Status:** ✅ Tested and working
**Last Updated:** January 12, 2026
