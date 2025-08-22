# Knowledge_Chipper → GetReceipts Integration Guide

## 🎯 GOAL
Integrate your Knowledge_Chipper project with GetReceipts to automatically export processed audio/video content as structured claims with knowledge artifacts (people, jargon, mental models) for community discussion and consensus tracking.

## 📋 PREREQUISITES
- ✅ `knowledge_chipper_integration.py` file already moved to Knowledge_Chipper project
- ✅ GetReceipts running on `http://localhost:3000` 
- ✅ Knowledge_Chipper processes audio/video and extracts artifacts

## 🚀 IMPLEMENTATION TASKS

### Task 1: Install Dependencies
Add to your Knowledge_Chipper requirements:
```bash
pip install requests
```

### Task 2: Identify Integration Points
Find these files in your Knowledge_Chipper codebase and modify them:

#### A) Main Processing Pipeline
**File to find**: Your main processing file (likely `main.py`, `cli.py`, or similar)
**Look for**: The function that orchestrates the full processing workflow

**Add this import at the top:**
```python
from knowledge_chipper_integration import GetReceiptsExporter
import time
from pathlib import Path
```

**Modify your main processing function:**
```python
def process_file_with_export(file_path, export_to_getreceipts=True):
    """Enhanced processing with optional GetReceipts export"""
    
    # === YOUR EXISTING PROCESSING (keep as-is) ===
    transcription_result = transcribe_audio(file_path)  # Your existing function
    summary_result = generate_summary(transcription_result)  # Your existing function
    people_data = extract_people(transcription_result)  # Your existing function
    jargon_data = extract_jargon(transcription_result)  # Your existing function
    models_data = extract_mental_models(transcription_result)  # Your existing function
    
    # === NEW: GETRECEIPTS EXPORT ===
    if export_to_getreceipts:
        try:
            session_data = build_getreceipts_session_data(
                transcription_result, summary_result, people_data, 
                jargon_data, models_data, file_path
            )
            
            exporter = GetReceiptsExporter("http://localhost:3000")
            result = exporter.export_session_data(session_data)
            
            print(f"✅ Exported to GetReceipts: {result.get('claims_submitted', 0)} claims")
            if 'results' in result:
                for claim_result in result['results']:
                    if 'url' in claim_result:
                        print(f"   📄 View claim: http://localhost:3000{claim_result['url']}")
                        
        except Exception as e:
            print(f"❌ GetReceipts export failed: {e}")
    
    # Return your existing results
    return transcription_result, summary_result, people_data, jargon_data, models_data
```

**Add this helper function:**
```python
def build_getreceipts_session_data(transcription, summary, people, jargon, models, file_path):
    """Convert Knowledge_Chipper data to GetReceipts format"""
    
    # Extract main claims from your summary data
    # ADAPT THIS to match your actual summary structure
    key_points = []
    
    if hasattr(summary, 'main_points') or 'main_points' in summary:
        # If your summary has main_points
        for point in summary.get('main_points', []):
            key_points.append({
                'summary': str(point.get('text', point.get('summary', str(point)))[:500],
                'details': str(point.get('details', point.get('explanation', '')))[:2000],
                'categories': point.get('topics', point.get('categories', [])),
                'evidence': point.get('evidence', point.get('supporting_points', [])),
                'confidence': point.get('confidence', 0.7)
            })
    
    elif hasattr(summary, 'key_insights') or 'key_insights' in summary:
        # If your summary has key_insights
        for insight in summary.get('key_insights', []):
            key_points.append({
                'summary': str(insight)[:500],
                'details': '',
                'categories': [],
                'evidence': [],
                'confidence': 0.7
            })
    
    else:
        # Fallback: create one claim from main summary
        main_summary = str(summary.get('summary', summary.get('main_summary', str(summary))))
        if main_summary and len(main_summary) > 10:
            key_points.append({
                'summary': main_summary[:500],
                'details': main_summary[:2000],
                'categories': transcription.get('topics', []),
                'evidence': [],
                'confidence': 0.6
            })
    
    # Build session data
    session_data = {
        'session_id': f"kc_session_{int(time.time())}",
        'source_url': getattr(file_path, 'url', None),
        'source_title': getattr(file_path, 'title', Path(file_path).stem),
        'processed_date': time.strftime('%Y-%m-%d'),
        'summary': {
            'key_points': key_points
        },
        'people': format_people_for_getreceipts(people),
        'jargon': format_jargon_for_getreceipts(jargon),
        'mental_models': format_models_for_getreceipts(models),
        'transcription': {
            'text': str(transcription.get('text', str(transcription))),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
    }
    
    return session_data

def format_people_for_getreceipts(people_data):
    """Convert your people data to GetReceipts format"""
    formatted = []
    
    if isinstance(people_data, list):
        for person in people_data:
            if isinstance(person, dict):
                formatted.append({
                    'name': person.get('name', ''),
                    'bio': person.get('bio', person.get('description', '')),
                    'expertise': person.get('expertise', person.get('areas', person.get('skills', []))),
                    'credibility': person.get('credibility', person.get('score', 0.5)),
                    'mentions': person.get('mentions', person.get('sources', []))
                })
            elif isinstance(person, str):
                formatted.append({
                    'name': person,
                    'bio': '',
                    'expertise': [],
                    'credibility': 0.5,
                    'mentions': []
                })
    
    return formatted

def format_jargon_for_getreceipts(jargon_data):
    """Convert your jargon data to GetReceipts format"""
    formatted = []
    
    if isinstance(jargon_data, list):
        for term in jargon_data:
            if isinstance(term, dict):
                formatted.append({
                    'term': term.get('term', term.get('name', '')),
                    'definition': term.get('definition', term.get('explanation', term.get('meaning', ''))),
                    'domain': term.get('domain', term.get('category', term.get('field', ''))),
                    'related': term.get('related', term.get('related_terms', [])),
                    'examples': term.get('examples', term.get('usage_examples', []))
                })
    
    return formatted

def format_models_for_getreceipts(models_data):
    """Convert your mental models data to GetReceipts format"""
    formatted = []
    
    if isinstance(models_data, list):
        for model in models_data:
            if isinstance(model, dict):
                formatted.append({
                    'name': model.get('name', model.get('title', '')),
                    'description': model.get('description', model.get('summary', model.get('explanation', ''))),
                    'domain': model.get('domain', model.get('category', model.get('field', ''))),
                    'concepts': model.get('concepts', model.get('key_terms', model.get('components', []))),
                    'relationships': model.get('relationships', [])
                })
    
    return formatted
```

#### B) CLI Integration (if you have a CLI)
**File to find**: Your CLI interface file
**Look for**: Click commands or argparse setup

**Add CLI option:**
```python
@click.command()
@click.argument('file_path')
@click.option('--export-to-getreceipts', is_flag=True, help='Export results to GetReceipts')
@click.option('--getreceipts-url', default='http://localhost:3000', help='GetReceipts instance URL')
def process_command(file_path, export_to_getreceipts, getreceipts_url):
    """Process audio/video file and optionally export to GetReceipts"""
    
    print(f"🎵 Processing: {file_path}")
    if export_to_getreceipts:
        print(f"🔗 Will export to GetReceipts: {getreceipts_url}")
    
    # Call your enhanced processing function
    results = process_file_with_export(file_path, export_to_getreceipts)
    
    print("✅ Processing complete!")
    return results

# Usage examples:
# python -m knowledge_system process video.mp4 --export-to-getreceipts
# python cli.py process audio.wav --export-to-getreceipts --getreceipts-url http://localhost:3000
```

#### C) GUI Integration (if you have a GUI)
**File to find**: Your GUI/Qt interface file
**Look for**: Process button handlers or result display functions

**Add GUI controls:**
```python
# In your GUI initialization
def setup_export_controls(self):
    """Add GetReceipts export controls to GUI"""
    
    # Add checkbox for auto-export
    self.export_checkbox = QCheckBox("Auto-export to GetReceipts")
    self.export_checkbox.setChecked(False)
    
    # Add URL input
    self.getreceipts_url_input = QLineEdit("http://localhost:3000")
    self.getreceipts_url_input.setPlaceholderText("GetReceipts URL")
    
    # Add manual export button  
    self.export_button = QPushButton("Export to GetReceipts")
    self.export_button.clicked.connect(self.manual_export_to_getreceipts)
    self.export_button.setEnabled(False)  # Enable after processing
    
    # Add to your layout
    layout.addWidget(QLabel("GetReceipts Integration:"))
    layout.addWidget(self.export_checkbox)
    layout.addWidget(self.getreceipts_url_input)
    layout.addWidget(self.export_button)

# In your processing completion handler
def on_processing_complete(self, results):
    """Called when processing finishes"""
    
    # Your existing result handling
    self.display_results(results)
    self.export_button.setEnabled(True)
    
    # Auto-export if enabled
    if self.export_checkbox.isChecked():
        self.export_to_getreceipts(results)

def export_to_getreceipts(self, results):
    """Export results to GetReceipts"""
    try:
        # Build session data from results
        session_data = build_getreceipts_session_data(
            results['transcription'], results['summary'], 
            results['people'], results['jargon'], results['models'], 
            self.current_file_path
        )
        
        exporter = GetReceiptsExporter(self.getreceipts_url_input.text())
        result = exporter.export_session_data(session_data)
        
        # Show success message
        QMessageBox.information(
            self, 
            "Export Successful", 
            f"Exported {result['claims_submitted']} claims to GetReceipts!"
        )
        
    except Exception as e:
        QMessageBox.warning(self, "Export Failed", f"Error: {e}")

def manual_export_to_getreceipts(self):
    """Manual export button handler"""
    if hasattr(self, 'last_results') and self.last_results:
        self.export_to_getreceipts(self.last_results)
    else:
        QMessageBox.warning(self, "No Data", "Process a file first!")
```

### Task 3: Configuration (Optional)
**Create**: `getreceipts_config.py` or add to existing config

```python
# GetReceipts integration settings
GETRECEIPTS_CONFIG = {
    'enabled': True,
    'url': 'http://localhost:3000',
    'auto_export': False,  # Set True for automatic export
    'min_confidence': 0.6,  # Only export claims above this confidence
    'max_claims_per_session': 10,  # Limit claims per export
    'timeout_seconds': 30,  # API timeout
}
```

### Task 4: Testing
1. **Start GetReceipts**:
   ```bash
   # In GetReceipts directory
   npm run dev
   ```

2. **Test the integration**:
   ```bash
   # In Knowledge_Chipper directory
   python your_cli.py process test_audio.wav --export-to-getreceipts
   ```

3. **Verify in GetReceipts**: Visit `http://localhost:3000/claim/[slug]` to see imported claims

## 🔧 CUSTOMIZATION NOTES

**Adapt these functions to match YOUR data structures:**

1. **`build_getreceipts_session_data()`** - Modify to match how your summary/transcription data is structured
2. **`format_people_for_getreceipts()`** - Adjust field names to match your people extraction format  
3. **`format_jargon_for_getreceipts()`** - Adjust to match your jargon/terminology format
4. **`format_models_for_getreceipts()`** - Adjust to match your mental models format

**Common field mappings you might need to change:**
- `summary.main_points` → your summary structure
- `person.expertise` → `person.skills` or `person.areas`
- `term.definition` → `term.explanation` or `term.meaning`
- `model.concepts` → `model.key_terms` or `model.components`

## 🎯 SUCCESS CRITERIA
- ✅ Knowledge_Chipper processes audio/video normally
- ✅ Claims automatically appear in GetReceipts with knowledge artifacts
- ✅ Can view rich claim pages with people, jargon, mental models
- ✅ Community can vote and discuss the imported claims
- ✅ Claims show up in the interactive network graph

## 🐛 TROUBLESHOOTING
- **Import errors**: Check `knowledge_chipper_integration.py` is in the right directory
- **API errors**: Ensure GetReceipts is running on the specified URL
- **Empty exports**: Check your data structure mapping in `build_getreceipts_session_data()`
- **Formatting issues**: Verify field names match between your data and the formatting functions

## 📞 NEED HELP?
If you encounter issues, check:
1. Data structure mismatches in the formatting functions
2. API connectivity between Knowledge_Chipper and GetReceipts  
3. Field name mappings between your artifacts and the expected format

The integration should be **minimal and non-invasive** - your existing Knowledge_Chipper workflow continues unchanged, with optional export to GetReceipts for enhanced knowledge management and community discussion.
