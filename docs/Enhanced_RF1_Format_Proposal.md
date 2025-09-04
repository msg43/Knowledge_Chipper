# Enhanced RF-1 Format Proposal

## Overview
Proposal to enhance the RF-1 format sent from Knowledge Chipper to GetReceipts to include ALL valuable HCE data.

## Current RF-1 Format vs. Enhanced Format

### 🔄 **Enhanced RF-1 Structure**

```json
{
  // ✅ EXISTING FIELDS (keep as-is)
  "claim_text": "Large language models exhibit emergent capabilities",
  "claim_long": "...",
  "topics": ["factual", "ai"],
  "sources": [...],
  "supporters": [...],
  "opponents": [...],
  "provenance": {...},
  "knowledge_artifacts": {
    "people": [...],
    "jargon": [...],
    "mental_models": [...],
    "claim_relationships": [...]
  },
  
  // 🆕 ENHANCED FIELDS (add these)  
  "source_data": {
    "source_id": "ep_20241201_interview_yoshua_bengio", 
    "title": "Yoshua Bengio on AI Safety and Future of Deep Learning",
    "source_type": "youtube",
    "recorded_at": "2024-12-01T14:30:00Z", 
    "duration": "3600",
    "transcript_segments": [
      {
        "segment_id": "seg_001",
        "speaker": "Host",
        "timestamp_start": "00:00:30",
        "timestamp_end": "00:01:15", 
        "text": "Today we're talking with Yoshua Bengio about...",
        "topic_guess": "introduction"
      },
      {
        "segment_id": "seg_002", 
        "speaker": "Yoshua Bengio",
        "timestamp_start": "00:01:15",
        "timestamp_end": "00:02:45",
        "text": "Thank you for having me. I think AI safety is...",
        "topic_guess": "ai_safety"
      }
    ],
    "source_milestones": [
      {
        "milestone_id": "ch_001",
        "title": "Introduction",
        "timestamp_start": "00:00:00",
        "timestamp_end": "00:15:30", 
        "summary": "Introduction and background on AI safety concerns"
      },
      {
        "milestone_id": "ch_002",
        "title": "Main Discussion", 
        "timestamp_start": "00:15:30",
        "timestamp_end": "00:45:15",
        "summary": "Discussion of emergent capabilities and scaling laws"
      }
    ]
  },
  
  "enhanced_claim_data": {
    "first_mention_timestamp": "00:23:45",
    "first_mention_speaker": "Yoshua Bengio",
    "complete_scores": {
      "importance": 0.92,
      "novelty": 0.78,
      "controversy": 0.45,
      "confidence_final": 0.88,
      "fragility": 0.23,
      "evidence_strength": 0.85,
      "specificity": 0.67
    },
    "context_segments": [
      {
        "segment_id": "seg_015",
        "relevance_score": 0.95,
        "speaker": "Yoshua Bengio",
        "text": "When I say emergent capabilities, I mean..."
      }
    ],
    
    // 🆕 TEMPORALITY ANALYSIS
    "temporality_score": 4,
    "temporality_confidence": 0.82,
    "temporality_rationale": "This claim about AI's emergent capabilities represents a long-term technological trend with 10+ year relevance, as it describes fundamental patterns in AI development.",
    
    // 🆕 STRUCTURED CATEGORIES  
    "structured_categories": [
      "Artificial Intelligence",
      "Machine Learning", 
      "Technology Research"
    ],
    "category_relevance_scores": {
      "Artificial Intelligence": 0.95,
      "Machine Learning": 0.88,
      "Technology Research": 0.72
    }
  },
  
  "enhanced_evidence": [
    {
      // ✅ EXISTING EVIDENCE FIELDS (precise quote)
      "quote_exact": "Research shows sudden capability jumps at specific scales",
      "timestamp_exact": "00:23:45-00:24:12",
      "youtube_link_exact": "https://youtube.com/watch?v=abc&t=1425s",
      
      // 🆕 ENHANCED EVIDENCE FIELDS (conversational context)
      "quote_context": "When we look at the scaling laws and how transformers have evolved, research shows sudden capability jumps at specific scales. This suggests we need to be very careful about how we approach these capability thresholds.",
      "timestamp_context": "00:23:30-00:24:45",
      "youtube_link_context": "https://youtube.com/watch?v=abc&t=1410s",
      "context_type": "conversational_boundary",
      
      // 🆕 SPEAKER & METADATA
      "speaker": "Yoshua Bengio",
      "segment_id": "seg_015",
      "evidence_type": "supporting",
      "confidence_score": 0.91
    }
  ]
}
```

## 📈 **Value of Enhanced Data**

### 1. **Full Transcript Access**
- **Search across entire episodes** - not just claim snippets
- **Speaker attribution** - know who said what
- **Conversation flow** - understand context and discussion dynamics
- **Topic tracking** - see how topics evolve throughout episode

### 2. **Episode Structure**
- **Chapter navigation** - jump to specific sections
- **Milestone summaries** - quick episode overview
- **Duration tracking** - time-based analytics

### 3. **Enhanced Speaker Data**
- **Speaker expertise tracking** - build profiles of who says what
- **Citation accuracy** - proper attribution for quotes
- **Conversation analysis** - who drives which topics

### 4. **Richer Evidence Context**
- **Context quotes** - see what was said before/after
- **Speaker credibility** - weight evidence by speaker expertise
- **Confidence scoring** - evidence quality assessment

## 🎯 **Impact on GetReceipts Schema**

The enhanced format would require these additional tables:

```sql
-- Episode and transcript data
CREATE TABLE episodes (
  id UUID PRIMARY KEY,
  episode_id TEXT UNIQUE,
  title TEXT,
  recorded_at TIMESTAMP,
  duration INTEGER -- seconds
);

CREATE TABLE transcript_segments (
  id UUID PRIMARY KEY,
  episode_id UUID REFERENCES episodes(id),
  segment_id TEXT,
  speaker TEXT,
  timestamp_start TEXT,
  timestamp_end TEXT,
  text TEXT,
  topic_guess TEXT
);

CREATE TABLE episode_milestones (
  id UUID PRIMARY KEY,
  episode_id UUID REFERENCES episodes(id),
  milestone_id TEXT,
  timestamp_start TEXT,
  timestamp_end TEXT,
  summary TEXT
);

-- Enhanced speakers tracking
CREATE TABLE speakers (
  id UUID PRIMARY KEY,
  name TEXT UNIQUE,
  expertise_areas TEXT[],
  credibility_score REAL
);

-- Link segments to speakers
ALTER TABLE transcript_segments 
ADD COLUMN speaker_id UUID REFERENCES speakers(id);

-- Enhanced evidence with context
ALTER TABLE evidence 
ADD COLUMN speaker_id UUID REFERENCES speakers(id),
ADD COLUMN context_before TEXT,
ADD COLUMN context_after TEXT,
ADD COLUMN confidence_score REAL;
```

## 🔄 **Migration Strategy**

### Phase 1: Enhanced RF-1 Format
1. Update Knowledge_Chipper `getreceipts_exporter.py` to include enhanced data
2. Keep current format as fallback for compatibility

### Phase 2: GetReceipts Schema Update  
1. Add new tables for episodes, segments, milestones
2. Update RF-1 parsing to handle enhanced format
3. Maintain backward compatibility

### Phase 3: New Features
1. **Source pages** - comprehensive source view with:
   - Source milestones/chapters/TOC with timestamped navigation
   - All claims from that source with speaker attribution
   - Direct links (YouTube, document sections) for every claim and milestone
   - Speaker profiles showing their contributions to the source
2. **Speaker profile pages** - track expertise and claims across all sources
3. **Conversational context** - smart evidence boundaries based on topic flow  
4. **Advanced search** - search across sources, claims, speakers, and topics

## 🚀 **Benefits**

1. **Source-centric browsing** - users can explore complete source conversations/documents  
2. **Conversational context** - smart evidence boundaries preserve natural discussion flow
3. **Speaker expertise tracking** - build credibility profiles across sources
4. **Precise + contextual evidence** - both exact quotes and conversational context
5. **Knowledge longevity assessment** - 1-5 temporality scale prioritizes lasting insights
6. **Semantic categorization** - Wikidata-style topic classification at claim and episode levels
7. **Enhanced discoverability** - search across sources, claims, speakers, topics, and categories
8. **Multi-format support** - seamless navigation for YouTube, RSS, documents

## 📝 **Implementation Notes**

- Enhanced format is **backward compatible** - existing fields unchanged
- **Gradual rollout** - can implement incrementally
- **Size considerations** - full transcripts will increase payload size significantly
- **Privacy implications** - need to consider speaker consent for full transcript sharing
