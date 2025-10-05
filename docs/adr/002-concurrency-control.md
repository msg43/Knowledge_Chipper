# ADR-002: Hardware-Aware Concurrency Control

## Status
Accepted

## Context
Knowledge Chipper runs on diverse hardware:
- Consumer laptops with 4GB RAM
- Professional workstations with 32GB+ RAM
- Server deployments with 128GB+ RAM

Fixed concurrency limits either waste resources on powerful hardware or overwhelm weaker systems.

## Decision
Implement hardware tier-based concurrency control:
1. **Detect hardware tier** based on RAM and CPU cores
2. **Apply tier-specific worker limits** for different job types
3. **Monitor memory usage** and throttle dynamically
4. **Use exponential backoff** for rate limit handling

## Hardware Tiers

| Tier | RAM | CPU Cores | Mining Workers | Eval Workers |
|------|-----|-----------|----------------|--------------|
| Consumer | <8GB | 2-4 | 2 | 1 |
| Prosumer | 16GB | 8 | 4 | 2 |
| Professional | 32GB | 12+ | 6 | 3 |
| Server | 64GB+ | 16+ | 10 | 5 |

## Consequences

### Positive
- **Optimal resource usage** across hardware tiers
- **Prevents OOM crashes** via memory monitoring
- **Better user experience** on all hardware
- **Automatic adaptation** without configuration

### Negative
- **Complexity** in resource management code
- **Testing burden** across hardware profiles
- **Potential for conservative limits** on edge cases

### Neutral
- Performance scales with hardware investment
- Users can override detected tiers if needed

## Implementation
```python
class LLMAdapter:
    def __init__(self):
        self.tier_config = self._determine_tier()
        self.memory_monitor = MemoryMonitor(
            threshold=self.tier_config.memory_threshold
        )
        self.mining_executor = ThreadPoolExecutor(
            max_workers=self.tier_config.mining_workers
        )
```

## Monitoring
- Track `memory_throttle_events` metric
- Log hardware tier on startup
- Alert on sustained throttling
