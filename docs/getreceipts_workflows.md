# GetReceipts (Web App) - Comprehensive Workflows

## Main Workflow Diagram

```mermaid
graph TB
    subgraph "User Authentication Flow"
        Landing[User Visits Site] --> AuthCheck{Authenticated?}
        AuthCheck -->|No| AnonMode[Anonymous Mode<br/>localStorage Bookmarks]
        AuthCheck -->|Yes| AuthMode[Authenticated Mode<br/>Database Bookmarks]

        AnonMode --> SignUpPrompt{Want to<br/>Sign Up?}
        SignUpPrompt -->|Yes| SignUpPage[/auth/signin]
        SignUpPage --> SupabaseAuth[Supabase Auth<br/>Email/Password or OAuth]
        SupabaseAuth --> CreateUser[(Create User Record)]
        CreateUser --> MigrateBookmarks[Migrate Local Bookmarks<br/>to Database]

        SignUpPrompt -->|No| BrowseClaims
        AuthMode --> BrowseClaims[Browse Claims]
    end

    subgraph "Knowledge_Chipper Desktop Upload"
        Desktop[Knowledge_Chipper Desktop] --> DeviceAuth[Device Authentication<br/>X-Device-ID Header<br/>X-Device-Key Header]
        DeviceAuth --> CheckDevice{Device<br/>Registered?}
        CheckDevice -->|No| RegisterDevice[Register New Device<br/>bcrypt Hash Key]
        CheckDevice -->|Yes| AuthSuccess[Authentication Success]
        RegisterDevice --> AuthSuccess

        AuthSuccess --> UploadAPI[POST /api/knowledge-chipper/upload]
        UploadAPI --> ValidateRF1[Validate RF-1 Format<br/>with Zod Schema]
        ValidateRF1 --> ParseData[Parse Enhanced RF-1:<br/>Claims, People,<br/>Jargon, Mental Models]
        ParseData --> VersionCheck{Check for<br/>Duplicate<br/>source_id?}
        VersionCheck -->|Exists| IncrementVersion[Increment Version<br/>Set replaces_claim_id]
        VersionCheck -->|New| Version1[Set version=1]
        IncrementVersion --> BulkInsert
        Version1 --> BulkInsert[Bulk Insert to Supabase]
        BulkInsert --> LinkDevice[Link Records<br/>to device_id]
        LinkDevice --> ReturnSuccess[Return Success Response]
    end

    subgraph "Claim Browsing & Discovery"
        BrowseClaims --> HomePage[Home Page /]
        HomePage --> DisplayOptions{Display Mode?}
        DisplayOptions --> TrendingClaims[Trending Claims<br/>Sorted by Engagement]
        DisplayOptions --> NetworkGraph[Interactive Graph<br/>D3.js Visualization]
        DisplayOptions --> SearchClaims[Search Claims]

        NetworkGraph --> FilterGraph{Filter By?}
        FilterGraph --> ConsensusFilter[Consensus Level]
        FilterGraph --> TopicFilter[Topic/Domain]
        FilterGraph --> RelationFilter[Relationship Type]

        SearchClaims --> SearchDB[(Query Supabase)]
        TrendingClaims --> SearchDB
        SearchDB --> DisplayResults[Display Results<br/>with Consensus Badge]
    end

    subgraph "Individual Claim Page"
        DisplayResults --> ClickClaim[Click Claim]
        ClickClaim --> ClaimPage[/claim/[slug]]

        ClaimPage --> FetchData[Parallel Data Fetch]
        FetchData --> GetClaim[Get Claim Data]
        FetchData --> GetKnowledge[Get Knowledge Artifacts]
        FetchData --> GetRelations[Get Relationships]
        FetchData --> GetComments[Get Comments]
        FetchData --> GetVotes[Get Vote Counts]

        GetClaim --> RenderClaim[Render Claim Display]
        GetKnowledge --> KnowledgeTabs[Knowledge Tabs:<br/>People, Jargon,<br/>Mental Models]
        GetRelations --> RelationGraph[Interactive<br/>Relationship Graph]
        GetComments --> CommentThread[Threaded Comments<br/>with Voting]
        GetVotes --> ConsensusMeter[Consensus Meter<br/>Visual Badge]

        RenderClaim --> UserActions{User Action?}
        UserActions -->|Vote| VotingFlow
        UserActions -->|Comment| CommentFlow
        UserActions -->|Bookmark| BookmarkFlow
        UserActions -->|Share| ShareFlow
        UserActions -->|Export| ExportFlow
    end

    subgraph "Voting System"
        VotingFlow[Vote on Claim] --> VoteType{Vote Type?}
        VoteType --> UpvoteDown[Upvote/Downvote]
        VoteType --> CredibleDisputed[Credible/Disputed]

        UpvoteDown --> CheckAuth{Authenticated?}
        CredibleDisputed --> CheckAuth
        CheckAuth -->|Yes| SubmitVote[POST /api/claims/[id]/vote]
        CheckAuth -->|No| PromptSignIn[Prompt to Sign In]

        SubmitVote --> UpdateVoteCounts[(Update Vote Counts<br/>in Supabase)]
        UpdateVoteCounts --> RecalcConsensus[Recalculate<br/>Consensus Score]
        RecalcConsensus --> UpdateBadge[Update Consensus Badge]
        UpdateBadge --> RealTimeUpdate[Real-Time UI Update]
    end

    subgraph "Comment System"
        CommentFlow[Add Comment] --> WriteComment[Write Comment Text]
        WriteComment --> ReplyTo{Reply to<br/>Comment?}
        ReplyTo -->|Yes| ThreadedReply[Threaded Reply]
        ReplyTo -->|No| TopLevel[Top-Level Comment]

        ThreadedReply --> SubmitComment[POST /api/claims/[id]/comments]
        TopLevel --> SubmitComment
        SubmitComment --> StoreComment[(Store in Supabase<br/>with parent_id)]
        StoreComment --> NotifyUsers[Notify Referenced Users]
        NotifyUsers --> RefreshThread[Refresh Comment Thread]

        CommentThread --> VoteComment{Vote on<br/>Comment?}
        VoteComment -->|Yes| CommentVote[Comment Voting]
        CommentVote --> UpdateCommentScore[(Update Comment Score)]
    end

    subgraph "Bookmark System"
        BookmarkFlow[Bookmark Item] --> BookmarkType{User Type?}
        BookmarkType -->|Anonymous| LocalStorage[Save to localStorage]
        BookmarkType -->|Authenticated| DatabaseBookmark[Save to Supabase]

        LocalStorage --> JSONExport[JSON Export Option]
        DatabaseBookmark --> CrossDevice[Cross-Device Sync]
        CrossDevice --> Dashboard

        Dashboard[/dashboard] --> MyBookmarks[View Bookmarks]
        MyBookmarks --> FilterBookmarks[Filter by Type:<br/>Claims, People,<br/>Episodes, Sources]
        FilterBookmarks --> ExportBookmarks[Export Options:<br/>JSON, Markdown, ZIP]
    end

    subgraph "Badge Generation"
        ShareFlow[Share Claim] --> BadgeRequest[GET /api/badge/[slug].svg]
        BadgeRequest --> FetchConsensus[Fetch Consensus Score]
        FetchConsensus --> GenerateSVG[Generate Dynamic SVG<br/>Color: Red→Yellow→Green]
        GenerateSVG --> CacheBadge[Cache Badge]
        CacheBadge --> ReturnSVG[Return SVG Badge]

        ReturnSVG --> EmbedOptions{Embed Where?}
        EmbedOptions --> Reddit[Reddit/Forums]
        EmbedOptions --> Twitter[X/Twitter]
        EmbedOptions --> Blog[Blog/Website]
    end

    subgraph "Knowledge Graph Visualization"
        NetworkGraph --> D3Init[Initialize D3.js]
        D3Init --> FetchGraphData[GET /api/graph/claims]
        FetchGraphData --> BuildGraph[Build Node/Edge Data]
        BuildGraph --> LayoutAlgorithm[Force-Directed Layout]
        LayoutAlgorithm --> RenderGraph[Render Interactive Graph]

        RenderGraph --> GraphInteraction{User Interaction?}
        GraphInteraction --> NodeClick[Click Node]
        GraphInteraction --> EdgeClick[Click Edge]
        GraphInteraction --> ZoomPan[Zoom/Pan]

        NodeClick --> HighlightConnected[Highlight Connected<br/>Claims]
        EdgeClick --> ShowRelation[Show Relationship<br/>Details]
    end

    subgraph "Knowledge Artifacts Display"
        KnowledgeTabs --> PeopleTab[People Tab]
        KnowledgeTabs --> JargonTab[Jargon Tab]
        KnowledgeTabs --> ModelsTab[Mental Models Tab]

        PeopleTab --> DisplayPeople[Display People<br/>with Expertise]
        DisplayPeople --> PeopleLinks[Link to Other Claims<br/>by Same Person]

        JargonTab --> DisplayJargon[Display Jargon<br/>with Definitions]
        DisplayJargon --> JargonUsage[Show Usage Context]

        ModelsTab --> DisplayModels[Display Mental Models<br/>with Descriptions]
        DisplayModels --> ModelRelations[Show Model<br/>Relationships]
    end

    subgraph "OAuth Integration (Knowledge_Chipper)"
        Desktop --> OAuthFlow[OAuth Flow Initiated]
        OAuthFlow --> BrowserPopup[Browser Popup Opens]
        BrowserPopup --> WebLogin[User Signs In<br/>at GetReceipts]
        WebLogin --> TokenGenerate[Generate Supabase JWT]
        TokenGenerate --> ReturnToken[Return Token to Desktop]
        ReturnToken --> AuthUpload[Authenticated Upload<br/>Claims Linked to User]
        AuthUpload --> UserDashboard[View in Dashboard]
    end

    subgraph "Database Architecture"
        BulkInsert --> Tables[(Supabase Tables)]
        Tables --> ClaimsTable[claims<br/>id, canonical, consensus_score,<br/>device_id, version]
        Tables --> PeopleTable[people<br/>name, expertise]
        Tables --> JargonTable[jargon<br/>term, definition]
        Tables --> ModelsTable[mental_models<br/>name, description]
        Tables --> RelationsTable[claim_relationships<br/>source_id, target_id, type]
        Tables --> VotesTable[votes<br/>user_id, claim_id, type]
        Tables --> CommentsTable[comments<br/>claim_id, user_id, parent_id]
        Tables --> BookmarksTable[bookmarks<br/>user_id, item_type, item_id]
        Tables --> DevicesTable[devices<br/>device_id, device_key_hash,<br/>user_id]
    end

    style SupabaseAuth fill:#e1f5e1
    style BulkInsert fill:#e1f5e1
    style SearchDB fill:#e1f5e1
    style UpdateVoteCounts fill:#e1f5e1
    style StoreComment fill:#e1f5e1
    style DatabaseBookmark fill:#e1f5e1
    style Tables fill:#e1f5e1
    style D3Init fill:#ffe1e1
    style NetworkGraph fill:#ffe1e1
    style ConsensusMeter fill:#e1e1ff
    style BadgeRequest fill:#e1e1ff
```

## Key Features

### Web Application (Next.js 15)
- **Next.js 15 + React 19** with TypeScript
- **Supabase Backend** for auth, database, and storage
- **shadcn/ui + Tailwind v4** for modern UI components
- **D3.js** for interactive knowledge graph visualization
- **Row-Level Security (RLS)** for data privacy
- **Server-side rendering** with client-side interactivity

### Authentication & Authorization
- **Dual Mode**: Anonymous (localStorage) and Authenticated (database)
- **OAuth Support**: Google and GitHub sign-in
- **Device Authentication**: Automatic credential generation for Knowledge_Chipper
- **Seamless Migration**: Local bookmarks sync to database on sign-in
- **JWT Tokens**: Secure Supabase authentication

### Knowledge Management
- **Enhanced RF-1 Format**: Claims with rich knowledge artifacts
- **Knowledge Artifacts**: People, jargon, mental models automatically catalogued
- **Relationship Tracking**: Supports, contradicts, extends, contextualizes
- **Version Control**: Track multiple versions of reprocessed claims
- **Provenance Tracking**: Full source attribution from desktop uploads

### Community Features
- **Multi-Dimensional Voting**: Upvote/downvote + credible/disputed
- **Consensus Meter**: Visual red→yellow→green badges
- **Threaded Comments**: Nested discussions with voting
- **User Reputation**: Community-driven credibility scoring
- **Faction Analysis**: See which communities align or oppose

### Visualizations
- **Interactive Graph**: D3.js force-directed network
- **Dynamic Filtering**: By consensus, topic, or relationship type
- **Consensus Badges**: Embeddable SVG badges for sharing
- **Real-time Updates**: Live consensus and engagement tracking

### API Endpoints
- `POST /api/knowledge-chipper/upload` - Upload from desktop
- `POST /api/knowledge-chipper/device-auth` - Device authentication
- `GET /api/badge/[slug].svg` - Generate consensus badges
- `GET /api/claims/[slug]` - Get claim with artifacts
- `GET /api/graph/claims` - Get network graph data
- `POST /api/claims/[id]/vote` - Submit votes
- `GET /api/claims/[id]/comments` - Get discussions

### Database Schema (Supabase)
- **claims** - Core claims with consensus scores
- **people** - Experts and key figures
- **jargon** - Domain-specific terminology
- **mental_models** - Conceptual frameworks
- **claim_relationships** - Graph edges between claims
- **votes** - User voting records
- **comments** - Threaded discussions
- **bookmarks** - User-saved items
- **devices** - Knowledge_Chipper device registry

### Integration Architecture
**Web-Canonical with Ephemeral Local**
1. Desktop: Extract, process, upload (then hide locally)
2. Web: Store, edit, curate, share (source of truth)
3. One-way flow: No sync conflicts, simplified architecture
4. Version tracking: Automatic handling of reprocessed content
