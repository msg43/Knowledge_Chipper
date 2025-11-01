# Whisper Hallucination Fix - October 2025

## Problem

Heavy hallucinations were occurring during transcription, particularly with the `large-v3` Whisper model. Example from logs:

```
⚠️ Heavy hallucination detected: 42 repetitions across 1 pattern(s) - cleaned automatically
🧹 Removed 42 consecutive repetitions of: 'and that process was much more intense in canada t...' (from 172.0s to 258.0s)
```

This resulted in **86 seconds of content loss** (from 172s to 258s in a 258s video) - essentially losing the last third of the video.

## Root Causes

### 1. Large Model Susceptibility
The `large-v3` model is significantly more prone to hallucinations than smaller models. From the existing documentation (`HALLUCINATION_PREVENTION_IMPROVEMENTS.md`):

> "While large models are more accurate on challenging audio, they are **significantly more prone to hallucinations**."

### 2. Missing Whisper.cpp Hallucination Control Parameters

Whisper.cpp provides several command-line parameters specifically designed to prevent hallucinations, but we weren't using them:

- `--entropy-thold N` - Entropy threshold for decoder fail (default: 2.40)
- `--logprob-thold N` - Log probability threshold for decoder fail (default: -1.00)  
- `--max-len N` - Maximum segment length in characters (default: 0 = unlimited)
- `--temperature N` - Sampling temperature (default: 0.00)

### 3. Silence/Background Noise Drift

While we have silence removal enabled, long periods of silence or background noise at the end of videos can still cause the model to "drift" and start hallucinating repetitive content.

## Solution Implemented

### Added Hallucination Prevention Parameters

Modified `src/knowledge_system/processors/whisper_cpp_transcribe.py` to add four key parameters to the whisper.cpp command:

#### 1. Entropy Threshold (`--entropy-thold`)
```python
# Model-specific thresholds
if self.model_name == "large":
    entropy_thold = 2.8  # More aggressive for large models
else:
    entropy_thold = 2.6  # Slightly higher than default for medium/small
```

**What it does**: Entropy measures the "randomness" or uncertainty in the model's predictions. Higher entropy = model is less confident. Setting a higher threshold (2.8 vs default 2.4) means the decoder will **fail faster** when it detects low-confidence predictions, stopping hallucinations before they start.

#### 2. Log Probability Threshold (`--logprob-thold`)
```python
logprob_thold = -0.8  # Default is -1.00 (more lenient)
```

**What it does**: This measures the log probability of predicted tokens. A higher (less negative) threshold means we're **more aggressive about rejecting low-confidence segments**. Changed from -1.0 to -0.8 to catch more potential hallucinations.

#### 3. Maximum Segment Length (`--max-len`)
```python
max_len = 200  # 200 characters max per segment (default: 0 = unlimited)
```

**What it does**: Prevents **runaway hallucinations** by limiting segment length. If Whisper starts repeating, it can't generate 42+ consecutive identical segments because each segment is capped at 200 characters.

#### 4. Temperature (`--temperature`)
```python
temperature = 0.0  # Deterministic (default)
```

**What it does**: Temperature of 0 means **completely deterministic** output (no randomness). This is already the default, but we explicitly set it to ensure consistency.

### Implementation Details

The parameters are:
- ✅ **Automatically configured** based on model size
- ✅ **Override-able** via kwargs if needed for fine-tuning
- ✅ **Logged** so you can see what values are being used
- ✅ **Model-aware** - more aggressive for large models

### Code Location

File: `src/knowledge_system/processors/whisper_cpp_transcribe.py`  
Lines: ~927-959

```python
# Add hallucination prevention parameters
entropy_thold = kwargs.get("entropy_thold")
if entropy_thold is None:
    if self.model_name == "large":
        entropy_thold = 2.8  # More aggressive for large models
        logger.info("🎯 Using aggressive hallucination prevention for large model")
    else:
        entropy_thold = 2.6  # Slightly higher than default
cmd.extend(["--entropy-thold", str(entropy_thold)])

logprob_thold = kwargs.get("logprob_thold", -0.8)
cmd.extend(["--logprob-thold", str(logprob_thold)])

max_len = kwargs.get("max_len", 200)
cmd.extend(["--max-len", str(max_len)])

temperature = kwargs.get("temperature", 0.0)
cmd.extend(["--temperature", str(temperature)])

logger.info(
    f"🛡️ Hallucination prevention: entropy={entropy_thold}, "
    f"logprob={logprob_thold}, max_len={max_len}, temp={temperature}"
)
```

## Expected Results

With these parameters enabled:

1. **Prevention over cleanup**: Hallucinations should be **prevented** at generation time rather than cleaned up afterward
2. **Less content loss**: No more removing 86 seconds of repetitions - the model will stop generating them
3. **Faster processing**: Less wasted compute on generating hallucinated content
4. **Better for large model**: The large model should now be more usable without massive hallucination issues

## Verification

Next time you transcribe, look for this log line:

```
🛡️ Hallucination prevention: entropy=2.8, logprob=-0.8, max_len=200, temp=0.0
```

And for large models, you should also see:
```
🎯 Using aggressive hallucination prevention for large model
```

## Additional Recommendations

### 1. Consider Using Medium Model
Despite this fix, the **medium model** is still recommended as the default for most use cases:
- 70-80% less hallucination risk than large
- 5-10x real-time processing (vs ~2-3x for large)
- Better balance of accuracy and reliability

Use large model only when:
- Audio quality is very poor
- Heavy accents or technical jargon
- You absolutely need the highest possible accuracy

### 2. Existing Safeguards Still Active
The following existing protections remain in place:
- ✅ Silence removal preprocessing
- ✅ Automatic repetition cleanup (as fallback)
- ✅ Contextual prompts with YouTube metadata
- ✅ Timestamp anchoring

## Testing

Test with the same video that caused the issue:
- Video ID: `kxKk7sBpcYA` 
- Title: "Why Trump's Stance on Canada Makes Sense || Peter Zeihan"
- Duration: 258 seconds
- Previously: Lost 86 seconds to hallucinations (172s-258s)

Expected: Clean transcription with no or minimal repetition cleanup needed.

## Parameters Can Be Tuned

If you still experience hallucinations or find legitimate content is being cut off:

```python
# Override in your code:
processor.process(
    audio_file,
    entropy_thold=3.0,     # Even more aggressive (may cut real content)
    logprob_thold=-0.6,    # More aggressive
    max_len=300,           # Allow longer segments
    temperature=0.2,       # Add slight randomness (not recommended)
)
```

## References

- [Whisper.cpp source](https://github.com/ggerganov/whisper.cpp)
- `docs/archive/implementations/HALLUCINATION_PREVENTION_IMPROVEMENTS.md` - Original hallucination prevention docs
- [OpenAI Whisper paper](https://arxiv.org/abs/2212.04356) - Original Whisper model documentation

