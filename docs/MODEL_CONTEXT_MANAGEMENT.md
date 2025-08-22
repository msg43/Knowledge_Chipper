# 🤖 Dynamic Model Context Window Management

The Knowledge Chipper now automatically detects and manages context windows for language models, keeping your setup current as you install new models.

## 🔄 **How It Works**

### **Automatic Detection**
1. **Static Database**: Pre-configured context windows for popular models (OpenAI, Anthropic, common local models)
2. **Dynamic Detection**: Queries Ollama to find installed models and intelligently estimates context windows based on:
   - Model family (llama, mistral, qwen, etc.)
   - Parameter count (1B, 3B, 7B, 70B, etc.)
   - Model version (3.1, 3.2, etc.)
3. **Smart Caching**: Results cached for 5 minutes to avoid repeated API calls
4. **Graceful Fallbacks**: Falls back to conservative defaults when detection fails

### **Intelligent Mapping Rules**
- **Llama 3.1/3.2**: 128K tokens (modern versions have large context)
- **Mistral**: 32K tokens (typical for 7B variants)  
- **Qwen 2.5**: 32K tokens (standard for this series)
- **Phi Models**: 128K tokens (typically have large contexts)
- **CodeLlama**: 16K tokens (optimized for code)
- **Large Models (70B+)**: 4K tokens (memory constraints)

## 🛠️ **Manual Management**

### **Scan for New Models**
When you install new models in Ollama:
```bash
python -m src.knowledge_system.utils.model_updater scan
```

### **List All Known Models**
```bash
python -m src.knowledge_system.utils.model_updater list
```

### **Add Custom Context Window**
For models with non-standard context windows:
```bash
python -m src.knowledge_system.utils.model_updater add "model_name:latest" 256000
```

### **Refresh Cache**
Force refresh of cached detections:
```bash
python -m src.knowledge_system.utils.model_updater refresh
```

## 📈 **Benefits**

### **For Users**
- ✅ **Automatic**: No manual configuration needed for most models
- ✅ **Current**: Stays up-to-date as you install new models  
- ✅ **Efficient**: Avoids unnecessary chunking for models with large contexts
- ✅ **Fast**: Cached results prevent repeated API calls

### **For Developers**
- ✅ **Extensible**: Easy to add new model families
- ✅ **Reliable**: Multiple fallback layers prevent failures
- ✅ **Observable**: Clear logging shows detection process
- ✅ **Testable**: Utilities for manual testing and validation

## 🔧 **Advanced Usage**

### **Programmatic Access**
```python
from src.knowledge_system.utils.text_utils import (
    get_model_context_window,
    add_custom_model_context,
    refresh_model_context_cache
)

# Get context window (auto-detected)
context = get_model_context_window("llama3.2:latest")

# Add custom model
add_custom_model_context("my_model:latest", 512000)

# Force refresh cache
refresh_model_context_cache()
```

### **Integration Points**
The dynamic detection integrates with:
- **Summarization**: Prevents unnecessary chunking
- **Transcription**: Optimizes prompt sizing  
- **Processing**: Adjusts batch sizes appropriately

## 🚨 **Troubleshooting**

### **Model Not Detected**
1. **Check Ollama**: `ollama list` to verify model is installed
2. **Restart Service**: `ollama serve` to restart Ollama
3. **Manual Override**: Use `add` command for custom context windows
4. **Check Logs**: Look for detection warnings in application logs

### **Unexpected Context Windows**
1. **Clear Cache**: Use `refresh` command
2. **Re-scan**: Use `scan` command to re-detect
3. **Manual Override**: Use `add` command to set correct value

### **Performance Issues**
- Cache TTL is 5 minutes by default
- Ollama queries are lightweight and fast
- Fallbacks ensure system never hangs on detection

## 📝 **Examples**

### **Common Workflows**

**New Model Setup:**
```bash
# Install model in Ollama
ollama pull qwen2.5:14b

# Scan to detect context window  
python -m src.knowledge_system.utils.model_updater scan

# Verify detection
python -m src.knowledge_system.utils.model_updater list | grep qwen2.5
```

**Custom Model Configuration:**
```bash
# Add custom context window for fine-tuned model
python -m src.knowledge_system.utils.model_updater add "my_tuned_llama:latest" 200000

# Verify it was added
python -m src.knowledge_system.utils.model_updater list | grep my_tuned
```

This system ensures your Knowledge Chipper always has optimal performance with any model you install! 🎉
