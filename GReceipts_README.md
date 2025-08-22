# GetReceipts.org

A comprehensive knowledge management platform for publishing, analyzing, and discussing claims with AI-powered consensus tracking, knowledge artifacts, and interactive visualizations.

**Enhanced with [Knowledge_Chipper](https://github.com/msg43/Knowledge_Chipper) integration for automated knowledge extraction from audio/video content.**

GetReceipts.org
Receipts, made shareable


The Problem
Online debates are loud, messy, and full of cherry-picked “proof.”
What’s missing? A living, neutral record of claims and counterclaims:
•	What smart people are actually saying
•	Who supports them, who disputes them
•	How strong the evidence really is
 
The Solution
GetReceipts.org is the world’s first Wikipedia for claims and counterclaims.
•	Receipts for Every Claim
Every claim is documented with sources, supporters, and opponents.
•	Consensus Meter 🌡️
A viral-friendly badge (red → green) shows how strongly a claim is supported by credible sources.
•	Faction Flairs 🎭
See at a glance which thinkers, schools, or communities align or oppose.
•	Receipts, Everywhere
One-click snippets let you drop receipts into Reddit, X, or blogs.
•	Transparent Re-Check 🔍
Each badge shows the reviewing model (e.g., GPT-4o), and you can instantly compare with Claude, Gemini, or your own LLM.
 
🌡️ Example Receipt
Claim: “Climate change is real.”
🌡️ Consensus Meter:   (97% supported by top-tier sources)
📚 Sources: IPCC, NASA, 300+ studies
👍 Supported by: 97% of climatologists
👎 Disputed by: Isolated think tanks
🎭 Faction Flairs: 🌍 Mainstream Science | 🔥Climate Contrarians
🔗 View full receipt →
 


🚀 Why It Will Spread
•	Receipts in Your Pocket → Drop into any debate, instantly credible.
•	Viral Visuals → Consensus badges & faction flairs become recognizable shorthand.
•	Not Just Fact-Checking → It’s a living belief map: what smart people are saying, and where the divides really are.
 
🌌 The Vision
GetReceipts.org grows into the world’s first global belief graph — showing not just what’s argued, but who stands together, who disagrees, and why.

## ✨ Key Features

### 🧠 **Knowledge Management**
- **AI-Powered Claim Extraction**: Automatic extraction of factual claims from Knowledge_Chipper transcriptions
- **Knowledge Artifacts**: People, jargon, and mental models automatically catalogued and cross-referenced
- **Smart Categorization**: Claims organized by topics, domains, and relationships

### 🕸️ **Interactive Visualizations**
- **Claims Network Graph**: Interactive D3.js visualization showing relationships between claims
- **Relationship Types**: Supports, contradicts, extends, and contextualizes connections
- **Dynamic Filtering**: Explore claims by consensus level, topic, or relationship strength

### 👥 **Community Engagement**
- **Multi-Dimensional Voting**: Upvote/downvote + credible/disputed ratings
- **Threaded Comments**: Full discussion system with nested replies and comment voting
- **User Reputation**: Community-driven credibility scoring
- **Real-time Updates**: Live consensus tracking and engagement metrics

### 📊 **Advanced Analytics**
- **Consensus Meter 🌡️**: Visual representation of agreement levels (red → yellow → green)
- **Evidence Strength**: Weighted scoring based on source credibility and review quality
- **Engagement Scoring**: Comprehensive metrics including votes, comments, and relationships
- **Faction Analysis**: See which communities and experts align or oppose

### 🔗 **Knowledge_Chipper Integration**
- **Seamless Import**: Direct integration with Knowledge_Chipper's SQLite artifacts
- **RF-1 Enhanced Format**: Extended schema supporting rich knowledge artifacts
- **Automated Processing**: Claims, people, jargon, and mental models auto-imported
- **Source Tracking**: Full provenance from original audio/video content

## Tech Stack

- **Frontend**: Next.js 15.5 + React 19 + TypeScript + Tailwind CSS v4
- **UI Components**: shadcn/ui + Radix UI + Lucide React
- **Visualization**: D3.js for interactive graph networks
- **Database**: Drizzle ORM + PostgreSQL + pgvector + Enhanced schema
- **Backend**: Supabase (Auth/Storage) + Next.js API Routes  
- **Testing**: Vitest + Testing Library
- **Validation**: Zod (Enhanced RF-1 format)
- **AI Integration**: Knowledge_Chipper Python SDK
- **Deployment**: Vercel

## Quick Start

### 1. Install Dependencies
```bash
npm install
```

### 2. Environment Setup
Copy `env.example` to `.env.local` and fill in your values:

```bash
cp env.example .env.local
```

Required environment variables:
- `NEXT_PUBLIC_SUPABASE_URL` - Your Supabase project URL
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` - Your Supabase anonymous key
- `SUPABASE_SERVICE_ROLE` - Your Supabase service role key (server-side only)
- `DATABASE_URL` - PostgreSQL connection string

### 3. Database Setup
```bash
# Apply enhanced schema (includes knowledge artifacts and user engagement)
psql $DATABASE_URL -f enhanced_schema_migration.sql

# Generate Drizzle migrations
npm run db:generate

# Run migrations
npm run db:migrate

# Seed demo data (optional)
npm run db:seed
```

### 4. Development Server
```bash
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000) to see the app.

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run start` - Start production server
- `npm run lint` - Run ESLint
- `npm run test` - Run tests with Vitest
- `npm run db:generate` - Generate Drizzle migrations
- `npm run db:migrate` - Run database migrations
- `npm run db:seed` - Seed database with demo data

## API Endpoints

### Core Endpoints
- `POST /api/receipts` - Submit RF-1 formatted claims (enhanced with knowledge artifacts)
- `GET /api/badge/[slug].svg` - Generate dynamic consensus badges
- `GET /api/claims/[slug]` - Get claim data with sources, reviews, and relationships

### Knowledge & Analytics
- `GET /api/knowledge/[claimId]` - Retrieve knowledge artifacts (people, jargon, mental models)
- `GET /api/graph/claims` - Get claims network data for graph visualization
- `POST /api/claims/[claimId]/vote` - Submit user votes (up/down/credible/disputed)
- `GET /api/claims/[claimId]/comments` - Get comments and discussions
- `POST /api/claims/[claimId]/comments` - Submit new comments

### Integration
- Enhanced RF-1 format supports Knowledge_Chipper artifacts
- Automatic relationship detection and graph building
- Real-time consensus updates

## Pages

- `/` - Home page with trending claims and network overview
- `/submit` - Submit RF-1 formatted claims (supports enhanced format)
- `/claim/[slug]` - **Enhanced claim pages** with:
  - Knowledge artifacts (people, jargon, mental models)
  - Interactive claims network graph
  - Community voting and discussion
  - Related claims and relationships
  - Evidence strength analysis
- `/embed/[slug]` - Embeddable claim cards with consensus badges

## Database Setup

### Supabase Setup
1. Create a new Supabase project
2. In the SQL Editor, run:
   ```sql
   create extension if not exists vector;
   ```
3. Apply the enhanced schema:
   ```sql
   -- Run the provided migration script
   \i enhanced_schema_migration.sql
   ```
4. Get your project URL and keys from Settings > API
5. Add them to your `.env.local` file

### Local PostgreSQL Setup
If using local PostgreSQL instead of Supabase:
```bash
# Create database
createdb getreceipts

# Apply schema
psql getreceipts -f enhanced_schema_migration.sql

# Update DATABASE_URL in .env.local
DATABASE_URL="postgresql://username:password@localhost:5432/getreceipts"
```

## Deployment

### Vercel Deployment
1. Push code to GitHub
2. Import repository in Vercel
3. Set environment variables in Vercel dashboard
4. Deploy

**Important**: Never expose `SUPABASE_SERVICE_ROLE` to the client-side.

## Knowledge_Chipper Integration

GetReceipts seamlessly integrates with [Knowledge_Chipper](https://github.com/msg43/Knowledge_Chipper) to automatically extract and organize knowledge from audio/video content.

### Setup Integration

1. **Add to Knowledge_Chipper**: Copy `knowledge_chipper_integration.py` to your Knowledge_Chipper project

2. **Configure Export**: Add to your processing pipeline:
   ```python
   from knowledge_chipper_integration import GetReceiptsExporter
   
   # After processing a session
   exporter = GetReceiptsExporter("http://localhost:3000")
   result = exporter.export_session_data(session_data)
   ```

3. **Data Flow**:
   ```
   Audio/Video → Knowledge_Chipper → Enhanced RF-1 → GetReceipts
                   │                                    │
                   ├─ Transcription              ├─ Claims Database
                   ├─ People                     ├─ Knowledge Artifacts  
                   ├─ Jargon                     ├─ Relationship Graph
                   └─ Mental Models              └─ Community Discussion
   ```

### What Gets Imported
- **Claims**: Factual statements extracted from content
- **People**: Experts, authors, and key figures mentioned
- **Jargon**: Domain-specific terminology with definitions
- **Mental Models**: Conceptual frameworks and their relationships
- **Sources**: Original audio/video with full provenance tracking

## Project Structure

```
src/
├── app/
│   ├── api/          # Enhanced API routes
│   │   ├── receipts/ # RF-1 claim submission (enhanced)
│   │   ├── knowledge/# Knowledge artifacts endpoints
│   │   ├── graph/    # Graph visualization data
│   │   ├── badge/    # Dynamic consensus badges
│   │   └── claims/   # Claim data and voting
│   ├── claim/        # Enhanced claim detail pages
│   ├── embed/        # Embeddable claim cards
│   └── submit/       # Submit page (supports enhanced RF-1)
├── components/
│   ├── ui/           # shadcn/ui base components
│   ├── KnowledgeArtifacts.tsx    # Knowledge display
│   ├── ClaimGraph.tsx            # Interactive graph
│   ├── VotingWidget.tsx          # Community voting
│   └── CommentsSection.tsx       # Discussion system
├── db/               # Enhanced database schema
└── lib/              # Utilities and enhanced RF-1 validation
```

## Enhanced Schema

The database now supports:
- **Knowledge Artifacts**: People, jargon, mental models from Knowledge_Chipper
- **Claim Relationships**: Supports, contradicts, extends, contextualizes
- **User Engagement**: Voting, comments, reputation scoring
- **Graph Analytics**: Network analysis and visualization data

## Example Usage

### 1. Knowledge_Chipper → GetReceipts Workflow

```python
# In Knowledge_Chipper, after processing a lecture/podcast
session_data = {
    'summary': {
        'key_points': [
            {
                'summary': 'Large language models exhibit emergent capabilities',
                'details': 'Research shows sudden capability jumps at specific scales',
                'categories': ['AI', 'Machine Learning'],
                'evidence': ['GPT-3 paper', 'PaLM results']
            }
        ]
    },
    'people': [{'name': 'Dr. Jane Smith', 'expertise': ['AI Research']}],
    'jargon': [{'term': 'Emergent Capabilities', 'definition': '...'}],
    'source_url': 'https://youtube.com/watch?v=ai-lecture'
}

# Export to GetReceipts
exporter = GetReceiptsExporter()
result = exporter.export_session_data(session_data)
# → Creates claims with full knowledge context in GetReceipts
```

### 2. Enhanced Claim Pages

Each claim now displays:
- **Consensus visualization** with interactive meter
- **Knowledge artifacts** in organized tabs (People, Jargon, Mental Models)
- **Interactive graph** showing claim relationships
- **Community voting** with multiple dimensions
- **Threaded discussions** with voting and reputation
- **Related claims** with relationship types and strength

### 3. API Usage

```javascript
// Submit enhanced RF-1 with knowledge artifacts
await fetch('/api/receipts', {
  method: 'POST',
  body: JSON.stringify({
    claim_text: "Large language models exhibit emergent capabilities",
    knowledge_artifacts: {
      people: [{ name: "Dr. Jane Smith", expertise: ["AI"] }],
      jargon: [{ term: "Emergent Capabilities", definition: "..." }],
      mental_models: [{ name: "Scaling Laws", description: "..." }]
    }
  })
});

// Get interactive graph data
const graph = await fetch('/api/graph/claims').then(r => r.json());
// → Use with D3.js for visualization

// Submit community vote
await fetch(`/api/claims/${claimId}/vote`, {
  method: 'POST',
  body: JSON.stringify({ vote_type: 'credible' })
});
```

## Performance & Scale

- **Optimized queries** with proper indexing for graph traversal
- **Parallel data fetching** for fast page loads
- **Efficient D3.js rendering** for large claim networks
- **Rate limiting** and validation for API endpoints
- **Real-time updates** with minimal re-renders

## Roadmap

- [ ] **Advanced Analytics**: Topic modeling and trend analysis
- [ ] **AI-Powered Moderation**: Automated quality scoring
- [ ] **Export Features**: Knowledge graph exports, citation generation
- [ ] **Mobile App**: React Native version with offline support
- [ ] **Federation**: Connect multiple GetReceipts instances
- [ ] **Advanced Visualizations**: Timeline views, topic clusters

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

For Knowledge_Chipper integration issues, see the [Knowledge_Chipper repository](https://github.com/msg43/Knowledge_Chipper).

## License

MIT License - see LICENSE file for details.
