# Performance Levels Reference

## Invisible Performance Profiles (Hardware-Based Auto-Assignment)

The system automatically assigns performance levels 1-6 based on detected hardware. These are invisible to users and allow easy expansion as hardware advances.

### Level Assignment Logic

| Level | RAM Requirement | CPU Requirement | Typical Hardware | Max Concurrent | Whisper Model |
|-------|----------------|-----------------|------------------|----------------|---------------|
| **Level 1** | ≤4GB | ≤2 cores | Old laptops, low-end systems | 1 | tiny |
| **Level 2** | 4-8GB | 2-4 cores | Entry laptops, budget systems | 2-4 | base |
| **Level 3** | 8-32GB | 4-12 cores | Mainstream laptops/desktops | 8-12 | base |
| **Level 4** | 16-32GB | 8-12 cores | Enthusiast systems | 12-16 | base |
| **Level 5** | 64GB+ | 16+ cores | Workstation-class | up to 20 | small |
| **Level 6** | 128GB+ | 20+ cores | Server-class | up to 32 | medium |

### Apple Silicon Adjustments

Apple Silicon systems get promoted to higher levels due to efficiency:
- **Level 4**: 16GB+ RAM, 8+ cores (vs 32GB+ for Intel/AMD)
- **Level 5**: 64GB+ RAM, 16+ cores 
- **Level 6**: 128GB+ RAM, 20+ cores (vs 24+ for Intel/AMD)

### Expansion Ready

When new hardware emerges (e.g., 512GB RAM, 64+ cores), simply add:
- **Level 7**, **Level 8**, etc.
- No user-facing changes needed
- Maintains backward compatibility

### Current Settings by Level

| Level | Sequential Mode | Max Concurrent | Batch Size | Model Upgrade | GPU Usage |
|-------|----------------|----------------|------------|---------------|-----------|
| 1 | Yes | 1 | 8 | No | Limited |
| 2 | No | 2-4 | 8-16 | No | Standard |
| 3 | No | 8-12 | 16-24 | No | Standard |
| 4 | No | 12-16 | 24-32 | No | Full |
| 5 | No | up to 20 | 32-64 | Yes (small) | Raw GPU |
| 6 | No | up to 32 | 64-128 | Yes (medium) | Raw GPU |

### Example Assignments

- **MacBook Air M2 8GB**: Level 2
- **MacBook Pro M2 Pro 32GB**: Level 4  
- **Mac Studio M2 Max 64GB**: Level 4
- **Mac Studio M2 Ultra 128GB**: Level 6 ⚡
- **Intel i9 32-core 256GB**: Level 6 ⚡
