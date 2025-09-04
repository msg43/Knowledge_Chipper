# Process Isolation System - User Guide

## Overview

The Process Isolation System is a comprehensive crash prevention and recovery solution for Knowledge Chipper that ensures your GUI never freezes or crashes during batch processing operations. It moves resource-intensive processing to separate processes while maintaining full functionality and user experience.

## Key Benefits

### 🛡️ **Complete Crash Protection**
- **Zero GUI crashes** during batch processing
- **Instant recovery** from worker process failures
- **Automatic restart** with exponential backoff
- **Process isolation** prevents crashes from affecting the main application

### 📊 **Smart Progress Tracking**
- **Real-time progress updates** during processing
- **Checkpoint-based recovery** allows resuming interrupted jobs
- **Detailed analytics** on processing performance and reliability
- **Memory usage monitoring** prevents system overload

### 🔄 **Seamless Recovery**
- **Automatic detection** of interrupted jobs on startup
- **User-friendly recovery dialog** with resume/restart/delete options
- **Complete job state preservation** in checkpoints
- **No data loss** from unexpected shutdowns

## How It Works

### Process Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Main GUI      │    │  Worker Process │    │   Checkpoint    │
│   Application   │◄──►│  (Isolated)     │◄──►│   System        │
│                 │    │                 │    │                 │
│ • User Interface│    │ • Audio Proc.   │    │ • Progress Save │
│ • Progress UI   │    │ • Summarization │    │ • Resume State  │
│ • Controls      │    │ • MOC Generation│    │ • Error Recovery│
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                │
                    ┌─────────────────┐
                    │   Analytics &   │
                    │   Monitoring    │
                    │                 │
                    │ • Health Status │
                    │ • Performance   │
                    │ • Error Tracking│
                    └─────────────────┘
```

### Communication Flow

1. **Job Submission**: GUI creates configuration and file list
2. **Process Spawn**: Isolated worker process starts with job parameters
3. **Real-time Updates**: Worker sends progress via JSON messages
4. **Checkpoint Saves**: Progress automatically saved for recovery
5. **Completion/Error**: Final results or error handling with recovery options

## User Interface

### Process Tab Interface

The updated Process Tab provides the same functionality with enhanced reliability:

- **File Selection**: Add files and directories as before
- **Configuration**: Same transcription, summarization, and MOC options
- **Processing Control**: Start/stop with visual progress tracking
- **Results Display**: Real-time updates with success/failure indicators

### Recovery Dialog

When the application detects interrupted jobs, it shows a recovery dialog:

#### Dialog Features
- **Job List**: Shows all recoverable processing jobs
- **Progress Details**: Displays completion percentage and file counts
- **Job Information**: Configuration, file list, and timestamps
- **Action Options**: Resume, Restart, or Delete interrupted jobs

#### Recovery Actions
- **Resume**: Continue from last completed file (recommended)
- **Restart**: Begin processing from the first file again
- **Delete**: Remove the checkpoint and start fresh

## Configuration

### Automatic Settings

The system automatically configures itself based on your hardware:

| System Memory | Configuration |
|---------------|---------------|
| < 4 GB | Conservative memory limits, single model loading |
| 4-16 GB | Balanced settings, moderate concurrency |
| > 16 GB | High performance, multiple concurrent models |

### Manual Configuration

Advanced users can customize settings in `config/process_isolation.yaml`:

```yaml
process_isolation:
  enabled: true
  max_restart_attempts: 3
  heartbeat_timeout_seconds: 60

memory_management:
  memory_pressure_threshold: 85.0  # Percentage
  adaptive_batch_sizing: true
  model_cache_limit_gb: 4.0

checkpoint_system:
  enabled: true
  frequency: "per_file"  # per_file, time_based, adaptive
  auto_cleanup_enabled: true

safety_features:
  crash_detection_enabled: true
  auto_recovery_enabled: true
  memory_monitoring_enabled: true
```

### Environment Variables

Quick configuration via environment variables:

```bash
export KC_PROCESS_ISOLATION_ENABLED=true
export KC_MEMORY_THRESHOLD=75.0
export KC_MAX_RESTART_ATTEMPTS=5
export KC_AUTO_RECOVERY=true
```

## Monitoring and Analytics

### Health Dashboard

Access system health information through the analytics system:

- **Crash Rate**: Crashes per hour of processing
- **Recovery Success Rate**: Percentage of successful recoveries
- **Processing Speed**: Files processed per hour
- **Memory Efficiency**: Output per GB-hour of memory used
- **Uptime Percentage**: System availability

### Performance Metrics

The system tracks comprehensive performance data:

- **Resource Usage**: Memory, CPU, and disk utilization
- **Processing Times**: Per-file and overall batch timing
- **Error Patterns**: Common failure modes and frequencies
- **User Satisfaction**: Based on completion rates and feedback

## Troubleshooting

### Common Issues

#### 1. Process Won't Start
**Symptoms**: Processing doesn't begin, immediate error messages
**Solutions**:
- Check system requirements (minimum 2GB RAM, Python 3.8+)
- Verify output directory permissions
- Review logs for specific error messages

#### 2. High Memory Usage
**Symptoms**: System becomes slow, memory warnings
**Solutions**:
- Reduce batch size in configuration
- Enable aggressive cleanup mode
- Process files in smaller groups

#### 3. Checkpoint Recovery Fails
**Symptoms**: Recovery dialog shows corrupted jobs
**Solutions**:
- Delete corrupted checkpoint files
- Restart processing from beginning
- Check disk space and permissions

#### 4. Frequent Process Crashes
**Symptoms**: Multiple restart attempts, poor success rates
**Solutions**:
- Lower memory pressure thresholds
- Reduce concurrent model loading
- Check for system instability issues

### Diagnostic Commands

Generate diagnostic reports for troubleshooting:

```python
from knowledge_system.gui.startup_integration import get_startup_integration

startup = get_startup_integration()
report = startup.generate_diagnostics_report()
print(report)
```

### Log Analysis

Check system logs for detailed error information:

```bash
# Main application logs
tail -f logs/knowledge_system.log

# Process isolation specific logs
grep "process_isolation" logs/knowledge_system.log

# Analytics and health monitoring
grep "analytics\|health" logs/knowledge_system.log
```

## Advanced Features

### Custom Recovery Workflows

Implement custom recovery logic for specific use cases:

```python
from knowledge_system.gui.dialogs.crash_recovery_dialog import CrashRecoveryManager

recovery_manager = CrashRecoveryManager()
recovery_manager.recovery_action_selected.connect(custom_recovery_handler)
```

### Performance Optimization

Fine-tune performance for your specific hardware:

```python
from knowledge_system.config.process_isolation import ProcessIsolationConfig

config = ProcessIsolationConfig()
config.set("memory_management", "model_cache_limit_gb", 8.0)
config.set("resource_limits", "max_cpu_cores", 6)
config.save_config()
```

### Analytics Integration

Access detailed analytics programmatically:

```python
from knowledge_system.utils.process_analytics import get_process_analytics

analytics = get_process_analytics()
health = analytics.get_health_status()
trends = analytics.get_trend_data(hours=24)
report = analytics.generate_report("json")
```

## Best Practices

### For Regular Users

1. **Let Recovery Work**: Trust the automatic recovery system
2. **Monitor Progress**: Watch for unusual patterns in processing times
3. **Regular Cleanup**: Allow automatic checkpoint cleanup to run
4. **Report Issues**: Use the feedback system to report problems

### For Power Users

1. **Customize Thresholds**: Adjust memory and performance limits for your hardware
2. **Monitor Analytics**: Review health reports regularly
3. **Optimize Batches**: Group similar files for better performance
4. **Backup Checkpoints**: Important long-running jobs can have checkpoints backed up

### For Developers

1. **Error Handling**: Always check return codes and handle exceptions
2. **Resource Cleanup**: Ensure proper cleanup in custom processors
3. **Progress Reporting**: Implement progress callbacks for better UX
4. **Testing**: Use the beta test framework for validation

## Migration from Thread-Based System

The process isolation system is designed as a drop-in replacement:

### Automatic Migration
- Existing configurations work without changes
- Old checkpoint files are automatically migrated
- Fallback to thread mode if process isolation fails

### Manual Migration Steps
1. **Backup Data**: Export any important configurations
2. **Update Configuration**: Review and adjust memory limits
3. **Test Processing**: Run small batches to verify functionality
4. **Monitor Health**: Check analytics for any issues

### Rollback Procedure
If needed, disable process isolation:

```yaml
# config/process_isolation.yaml
process_isolation:
  enabled: false

compatibility:
  fallback_to_thread_mode: true
```

## Support and Feedback

### Getting Help
- **Documentation**: This guide and inline help text
- **Logs**: Check application logs for detailed error information
- **Diagnostics**: Generate diagnostic reports for support requests
- **Community**: Share experiences and solutions with other users

### Providing Feedback
The system includes built-in feedback collection:
- **Satisfaction Ratings**: Rate your experience after processing
- **Error Reports**: Automatic crash and error reporting
- **Performance Data**: Anonymous usage statistics for improvements
- **Feature Requests**: Suggest improvements through the feedback system

### Contributing
Help improve the system:
- **Beta Testing**: Participate in testing new features
- **Bug Reports**: Report issues with detailed reproduction steps
- **Documentation**: Improve user guides and technical documentation
- **Code Contributions**: Submit improvements and fixes

---

*This guide covers the essentials of the Process Isolation System. For technical details, see the developer documentation in `docs/internal/`.*
