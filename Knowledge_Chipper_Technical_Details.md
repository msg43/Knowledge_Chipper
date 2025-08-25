# Knowledge Chipper Technical Implementation Details

## Code Patterns & Conventions

### Processor Pattern
All input processors inherit from `BaseProcessor`:

```python
class BaseProcessor:
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        
    def process(self, input_data: Any, dry_run: bool = False, **kwargs) -> dict:
        """Main processing method - must be implemented by subclasses"""
        raise NotImplementedError
        
    def validate_input(self, input_data: Any) -> bool:
        """Validate input before processing"""
        return True
```

### Worker Pattern for GUI
GUI operations use PyQt6 workers for non-blocking processing:

```python
class ProcessingWorker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def run(self):
        try:
            # Long-running operation
            result = self.process_data()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
```

### Configuration Management
Settings use Pydantic for validation:

```python
class Settings(BaseSettings):
    output_directory: Path = Path.home() / "Documents" / "KnowledgeSystem" / "output"
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```

## Database Patterns

### SQLAlchemy Models
```python
class Video(Base):
    __tablename__ = "videos"
    
    id = Column(Integer, primary_key=True)
    video_id = Column(String, unique=True, nullable=False)
    title = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    transcripts = relationship("Transcript", back_populates="video")
    summaries = relationship("Summary", back_populates="video")
```

### Database Service Pattern
```python
class DatabaseService:
    def __init__(self, db_path: Path):
        self.engine = create_engine(f"sqlite:///{db_path}")
        self.Session = sessionmaker(bind=self.engine)
        
    def add_video(self, video_data: dict) -> Video:
        with self.Session() as session:
            video = Video(**video_data)
            session.add(video)
            session.commit()
            return video
```

## HCE Integration Details

### Claim Extraction Pipeline
The HCE system follows a multi-stage pipeline:

1. **Segmentation**: Break content into processable chunks
2. **Mining**: Extract raw claims from segments
3. **Linking**: Connect claims to evidence
4. **Deduplication**: Remove redundant claims
5. **Reranking**: Score claims by importance
6. **Routing**: Assign confidence tiers (A/B/C)
7. **Judging**: Final validation pass
8. **Relations**: Map claim relationships

### Adapter Pattern for Backward Compatibility
```python
class HCEAdapter:
    """Adapts HCE output to legacy format"""
    
    def convert_to_legacy_summary(self, hce_output: PipelineOutput) -> dict:
        # Convert claims to summary format
        summary_text = self._format_claims_as_summary(hce_output.claims)
        
        # Maintain legacy structure
        return {
            "summary": summary_text,
            "metadata": {
                "model": hce_output.metadata.model,
                "tokens": hce_output.metadata.total_tokens,
                "cost": hce_output.metadata.cost
            }
        }
```

## Error Handling Patterns

### Custom Exceptions
```python
class KnowledgeChipperError(Exception):
    """Base exception for all custom errors"""
    pass

class TranscriptionError(KnowledgeChipperError):
    """Raised when transcription fails"""
    pass

class APIError(KnowledgeChipperError):
    """Raised when API calls fail"""
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code
```

### Retry Logic
```python
def retry_with_backoff(max_attempts: int = 3, backoff_factor: float = 2.0):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    time.sleep(backoff_factor ** attempt)
            return None
        return wrapper
    return decorator
```

## Progress Tracking

### Progress Manager Pattern
```python
class ProgressTracker:
    def __init__(self, total_items: int):
        self.total = total_items
        self.current = 0
        self.start_time = time.time()
        
    def update(self, increment: int = 1):
        self.current += increment
        
    @property
    def percentage(self) -> float:
        return (self.current / self.total) * 100 if self.total > 0 else 0
        
    @property
    def eta(self) -> Optional[float]:
        if self.current == 0:
            return None
        elapsed = time.time() - self.start_time
        rate = self.current / elapsed
        remaining = self.total - self.current
        return remaining / rate if rate > 0 else None
```

## Model Management

### Model URI System
```python
def parse_model_uri(uri: str) -> tuple[str, str]:
    """Parse model URI format: provider://model_name"""
    if "://" not in uri:
        raise ValueError(f"Invalid model URI: {uri}")
    provider, model = uri.split("://", 1)
    return provider, model

def get_model_client(uri: str) -> Any:
    provider, model = parse_model_uri(uri)
    
    if provider == "openai":
        return OpenAI()
    elif provider == "anthropic":
        return Anthropic()
    elif provider == "ollama":
        return Ollama()
    else:
        raise ValueError(f"Unknown provider: {provider}")
```

## File I/O Patterns

### Safe File Operations
```python
def safe_write_file(path: Path, content: str, backup: bool = True):
    """Write file with atomic operation and optional backup"""
    temp_path = path.with_suffix('.tmp')
    
    try:
        # Write to temp file
        temp_path.write_text(content, encoding='utf-8')
        
        # Backup existing file if requested
        if backup and path.exists():
            backup_path = path.with_suffix('.bak')
            shutil.copy2(path, backup_path)
        
        # Atomic rename
        temp_path.rename(path)
        
    except Exception:
        # Clean up temp file on error
        if temp_path.exists():
            temp_path.unlink()
        raise
```

## Performance Optimization Patterns

### Batch Processing
```python
def process_in_batches(items: list, batch_size: int, processor: Callable):
    """Process items in batches for memory efficiency"""
    results = []
    
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        batch_results = processor(batch)
        results.extend(batch_results)
        
        # Allow other operations between batches
        time.sleep(0.1)
        
    return results
```

### Concurrent Processing
```python
async def process_files_concurrently(files: list[Path], max_concurrent: int = 4):
    """Process multiple files with controlled concurrency"""
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_with_semaphore(file: Path):
        async with semaphore:
            return await process_file_async(file)
    
    tasks = [process_with_semaphore(f) for f in files]
    return await asyncio.gather(*tasks)
```

## Testing Patterns

### Fixture Usage
```python
@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing"""
    with patch('openai.OpenAI') as mock:
        client = mock.return_value
        client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content="Test response"))]
        )
        yield client

def test_summarization(mock_openai_client):
    processor = SummarizerProcessor()
    result = processor.process("Test input")
    assert "Test response" in result["summary"]
```

## Logging Patterns

### Structured Logging
```python
from loguru import logger

# Configure logger
logger.add(
    "logs/app_{time}.log",
    rotation="1 day",
    retention="7 days",
    format="{time} | {level} | {module}:{function}:{line} | {message}",
    level="INFO"
)

# Usage
logger.info("Processing file", file=file_path, size=file_size)
logger.error("API call failed", error=str(e), status_code=e.status_code)
```

## GUI Event Handling

### Signal/Slot Pattern
```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.connect_signals()
        
    def connect_signals(self):
        # Connect button clicks
        self.process_button.clicked.connect(self.on_process_clicked)
        
        # Connect worker signals
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_processing_finished)
        self.worker.error.connect(self.on_processing_error)
```

## Configuration Templates

### Dynamic Template System
```python
def load_prompt_template(analysis_type: str) -> str:
    """Load prompt template based on analysis type"""
    # Convert analysis type to filename
    filename = analysis_type.lower().replace("(", "").replace(")", "").strip()
    template_path = Path("config/prompts") / f"{filename}.txt"
    
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
        
    return template_path.read_text()
```

## Memory Management

### Resource Cleanup
```python
class ResourceManager:
    def __init__(self):
        self.resources = []
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        for resource in self.resources:
            try:
                resource.cleanup()
            except Exception as e:
                logger.error(f"Failed to cleanup resource: {e}")
                
    def add_resource(self, resource):
        self.resources.append(resource)
```

## State Management

### State Persistence
```python
class StateManager:
    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.state = self._load_state()
        
    def _load_state(self) -> dict:
        if self.state_file.exists():
            return json.loads(self.state_file.read_text())
        return {}
        
    def save_state(self):
        self.state_file.write_text(json.dumps(self.state, indent=2))
        
    def update(self, key: str, value: Any):
        self.state[key] = value
        self.save_state()
```

---

These patterns and implementation details represent the core architectural decisions and coding standards used throughout the Knowledge Chipper codebase. Understanding these patterns will help in maintaining consistency when adding new features or modifying existing functionality.
