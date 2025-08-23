# HCE Migration Guide: From Summarization to Claim Analysis

## Overview

Knowledge Chipper has been upgraded from basic summarization to advanced **Claim Analysis** using the Hybrid Claim Extractor (HCE) system. This guide helps you understand the changes and migrate your workflows.

## What's New

### 🔍 **Enhanced Analysis Output**
- **Before**: Simple text summaries
- **After**: Structured claim analysis with confidence tiers (A/B/C)

### 📊 **Rich Metadata**
- **Claims by Confidence**: High (A), Medium (B), Supporting (C) tiers
- **Entity Extraction**: People, concepts, and jargon automatically identified
- **Relationship Mapping**: Connections between claims and contradictions detected
- **Evidence Citations**: Supporting evidence for each claim

### 🎛️ **Advanced Controls**
- **Claim Filtering**: Filter by confidence tier, claim type, or limit count
- **Analysis Depth**: 5-level depth slider for processing intensity
- **Real-Time Analytics**: Live display of extraction results during processing

## Migration Steps

### 1. **Existing Files**
Your existing summary files remain unchanged. New processing will use the HCE format automatically.

### 2. **Updated Tabs**
- **"Document Summarization"** → **"Summarization"**
- New claim filtering controls added
- Real-time analytics display during processing

### 3. **Enhanced Output Format**
New markdown files include:
```markdown
# Claim Analysis: [Title]

## Executive Summary
[Key high-confidence claims]

## Key Claims by Category
### 🥇 Tier A Claims (High Confidence)
### 🥈 Tier B Claims (Medium Confidence)

## People
[Automatically extracted people with descriptions]

## Concepts  
[Key concepts and jargon identified]

## Evidence Citations
[Supporting evidence for claims]

## Tags
#claim-analysis #hce-processed [concept tags]

## Related People
- [[Person Name]] (Obsidian wikilinks)
```

### 4. **Database Migration**
The system automatically:
- Preserves all existing data
- Marks old summaries as `processing_type: legacy`
- Stores new HCE data in `hce_data_json` field
- Maintains backward compatibility

## New Features Guide

### **Claim Filtering Controls**
1. **Minimum Claim Tier**: Choose quality threshold
   - "All": Include all claims
   - "Tier A": Only high-confidence claims (85%+)
   - "Tier B+": Medium and high confidence (65%+)

2. **Max Claims per Document**: Limit output size
   - Set to 0 for unlimited
   - Higher values = more detail but longer processing

3. **Analysis Options**:
   - ✅ **Include Contradiction Analysis**: Find conflicting claims
   - ✅ **Include Relationship Mapping**: Map claim connections

### **Process Tab Enhancements**
1. **Analysis Depth Slider**: Control processing intensity
   - Level 1: Quick (surface-level claims)
   - Level 3: Balanced (recommended)
   - Level 5: Comprehensive (all possible claims)

2. **Enhanced Results**: See real-time claim statistics
   - Total claims extracted by tier
   - People and concepts identified
   - Contradictions and relations found
   - Top claims preview

### **Obsidian Integration**
New files automatically include:
- **Tags**: `#claim-analysis`, `#concept/[name]`, `#high-confidence`
- **Wikilinks**: `[[Person Name]]` for automatic linking
- **Structured sections**: Compatible with Obsidian MOCs

## Workflow Examples

### **Research Analysis Workflow**
1. Upload research papers or transcripts
2. Set Analysis Depth to "Deep (4)" for thorough extraction
3. Enable contradiction analysis to find conflicting claims
4. Review Tier A claims for key findings
5. Use generated tags and wikilinks in Obsidian

### **Content Review Workflow**
1. Process multiple documents on same topic
2. Set Minimum Tier to "Tier A" for high-confidence claims only
3. Limit to 50 claims per document for focused results
4. Review contradictions section for inconsistencies
5. Export to MOC for knowledge mapping

### **Quick Analysis Workflow**
1. Set Analysis Depth to "Quick (1)" for fast processing
2. Set Max Claims to 20 for concise results
3. Focus on executive summary section
4. Use for rapid content triage

## Troubleshooting

### **Common Questions**

**Q: My old summaries look different**
A: Old summaries remain unchanged. New processing uses the enhanced HCE format. You can reprocess files to get the new format.

**Q: Processing seems slower**
A: HCE does more sophisticated analysis. Use "Quick" analysis depth for faster processing, or enable embedding cache for better performance.

**Q: Too many claims extracted**
A: Use claim filtering controls:
- Set "Minimum Claim Tier" to "Tier A" for only high-confidence claims
- Set "Max Claims per Document" to limit output size
- Adjust confidence thresholds in advanced settings

**Q: Missing people or concepts**
A: Try increasing Analysis Depth or lowering confidence thresholds. The system learns and improves entity recognition over time.

### **Performance Tips**
1. **Enable Embedding Cache**: Speeds up processing of similar content
2. **Use Appropriate Analysis Depth**: Level 3 (Balanced) is optimal for most use cases
3. **Filter by Tier**: Use "Tier A" filtering for executive summaries
4. **Batch Processing**: Process multiple files together for efficiency

## Migration Validation

Run the validation script to check your migration:
```bash
python scripts/validate_hce_migration.py
```

This will verify:
- Data integrity across old and new formats
- Database schema compatibility
- Performance metrics
- Migration completeness

## Support

If you encounter issues:
1. Check the validation script output
2. Review the output logs for error details
3. Try reprocessing problematic files
4. Use "Quick" analysis depth as a fallback

The new HCE system provides dramatically improved analysis quality while maintaining full backward compatibility with your existing workflows.
