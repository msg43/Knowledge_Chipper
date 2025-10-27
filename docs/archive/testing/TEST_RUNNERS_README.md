# Comprehensive Test Runners

This directory contains multiple test runner scripts for different scenarios:

## Option 1: Sequential with Per-Test Reporting
```bash
./run_comprehensive_tests.sh
```
- Runs each test suite individually
- Continues on failures (no early exit)
- Shows warnings instead of stopping
- Real-time reporting with timestamps

## Option 2: All Tests in One Command
```bash
./run_all_comprehensive_tests.sh
```
- Runs all three test files together
- Continues on failures (no `--maxfail=1`)
- Generates HTML and XML reports
- Single command execution

## Option 3: Find All Issues Mode
```bash
./run_find_all_issues.sh
```
- Explicitly designed to find all issues
- Clear messaging about parallel fixing
- Comprehensive reporting
- Proper exit codes for CI/CD

## Option 4: Auto-Fix Loop Mode
```bash
./run_auto_fix_loop.sh
```
- Runs tests, attempts to fix issues automatically
- Re-runs until all clear or max iterations reached
- Handles common issues (imports, database, permissions, etc.)
- Maximum 10 iterations

## Option 5: Smart Auto-Fix Loop Mode (Recommended)
```bash
./run_smart_auto_fix_loop.sh
```
- Advanced AI-powered failure analysis
- Generates analysis prompts for AI assistance
- Smart fix suggestions based on failure patterns
- Maximum 15 iterations
- Creates detailed analysis files

## Test Coverage

All scripts test:
1. **GUI Complete** - Real GUI + real data + real outputs + tab switching
2. **Integration Complete** - Real files + real processing + real database
3. **System2 Complete** - Real orchestration + real LLM + real checkpointing

## Output Files

- `test-results/comprehensive_results_*.xml` - JUnit XML results
- `test-results/comprehensive_report_*.html` - HTML test reports
- `test-results/test_output_*.log` - Detailed test logs
- `test-results/analysis_prompt_*.txt` - AI analysis prompts (Option 5)

## Recommended Usage

For development: Use **Option 5** (Smart Auto-Fix Loop)
For CI/CD: Use **Option 3** (Find All Issues)
For quick checks: Use **Option 2** (All Tests)
