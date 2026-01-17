flowchart TD
    subgraph Inputs ["Input Stage"]
        Trans[Transcript]
        Meta[Metadata]
        
        Meta --> ContextAgg{Build Context<br/>Aggregate}
        ContextAgg -->|1. Tags| QueryTags
        ContextAgg -->|2. Local Summary| QuerySum
        ContextAgg -->|3. Title| QueryTitle
        ContextAgg -.->|4. Desc Fallback| QueryDesc
    end

    subgraph TasteHub ["Taste Engine (Vector DB)"]
        direction TB
        TasteDB[(ChromaDB)]
        Golden[Golden Set JSON] -.->|Startup| TasteDB
    end

    subgraph Phase1 ["Phase 1: Prevention"]
        QueryTags & QuerySum & QueryTitle & QueryDesc --> Query{Query Vectors}
        Query <--> TasteDB
        Query -->|Retrieve Examples| Inject[Inject into Prompt]
        
        Trans --> LLM_Extract[LLM Extraction<br/>(Pass 1)]
        Inject --> LLM_Extract
    end

    subgraph Phase2 ["Phase 2: Truth (The Critic)"]
        LLM_Extract --> RawJSON[Raw Claims]
        RawJSON --> Critic[LLM Critic<br/>(Pass 1.5)]
        
        Critic -->|Check Logic| Validates{"Is this a<br/>Hallucination?"}
        Validates -->|Yes (Error)| Drop[Drop Entity]
        Validates -->|No (Valid)| ValidJSON[Validated Claims]
    end

    subgraph Phase3 ["Phase 3: Taste (The Filter)"]
        ValidJSON --> VectorCheck{Vector Check}
        VectorCheck <--> TasteDB
        
        VectorCheck -->|Sim > 0.95<br/>(Rejected)| AutoDiscard[Auto-Discard]
        VectorCheck -->|Sim > 0.95<br/>(Accepted)| Boost[Boost Score +2.0]
        VectorCheck -->|Sim 0.80-0.95<br/>(Rejected)| Flag[Flag 'Suspicious']
        VectorCheck -->|Else| Keep[Keep Standard]
    end

    subgraph Output ["Output & Feedback Loop"]
        AutoDiscard & Boost & Flag & Keep --> FinalList[Final List]
        FinalList --> Synthesize[Synthesis Pass]
        Synthesize --> WebUI[Web UI Review]
        
        WebUI -->|User Action| Decisions{Accept / Reject}
        Decisions -->|Sync| API[/feedback/sync]
        API --> Queue[(Pending Queue)]
        
        Queue --> Worker[Async Worker]
        Worker -->|Embed & Update| TasteDB
    end

    style TasteDB fill:#FFD700,stroke:#333,stroke-width:2px
    style Critic fill:#90EE90,stroke:#333,stroke-width:2px
    style VectorCheck fill:#87CEEB,stroke:#333,stroke-width:2px
    style Worker fill:#FF7F50,stroke:#333,stroke-width:2px