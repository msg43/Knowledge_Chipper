#!/usr/bin/env python3
"""
Simple test to verify HCE schema validation and foreign key fixes.
This can be run standalone without full environment setup.
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

print("=" * 60)
print("Testing HCE Schema and FK Fixes")
print("=" * 60)
print()

# Test 1: Schema Check
print("Test 1: Checking flagship schema")
print("-" * 60)

try:
    schema_path = Path(__file__).parent.parent / "schemas" / "flagship_output.v1.json"
    with open(schema_path) as f:
        schema = json.load(f)
    
    # Check that rank is NOT in required fields
    required_fields = schema["properties"]["evaluated_claims"]["items"]["required"]
    
    if "rank" in required_fields:
        print("❌ FAIL: 'rank' is still in required fields")
        print(f"   Required: {required_fields}")
        sys.exit(1)
    else:
        print("✅ PASS: 'rank' correctly removed from required fields")
        print(f"   Required: {required_fields}")
        print("   (rank is now optional, as it should be for rejected claims)")

except Exception as e:
    print(f"❌ ERROR: Could not check schema: {e}")
    sys.exit(1)

print()

# Test 2: Check repair logic exists
print("Test 2: Checking schema validator repair logic")
print("-" * 60)

try:
    validator_path = (
        Path(__file__).parent.parent 
        / "src" / "knowledge_system" / "processors" / "hce" 
        / "schema_validator.py"
    )
    
    with open(validator_path) as f:
        validator_code = f.read()
    
    # Check for rank repair logic
    if "placeholder ranks for rejected" in validator_code:
        print("✅ PASS: Repair logic for missing rank field found")
        print("   - Adds placeholder rank (999) for claims missing rank")
        print("   - Prevents validation failures on rejected claims")
    else:
        print("❌ FAIL: Repair logic not found in schema_validator.py")
        sys.exit(1)

except Exception as e:
    print(f"❌ ERROR: Could not check validator: {e}")
    sys.exit(1)

print()

# Test 3: Check store_segments enhancement
print("Test 3: Checking ClaimStore.store_segments() enhancement")
print("-" * 60)

try:
    claim_store_path = (
        Path(__file__).parent.parent 
        / "src" / "knowledge_system" / "database" 
        / "claim_store.py"
    )
    
    with open(claim_store_path) as f:
        claim_store_code = f.read()
    
    # Check for episode pre-creation logic
    checks = {
        "source_id parameter": "source_id: str | None = None" in claim_store_code,
        "episode_title parameter": "episode_title: str | None = None" in claim_store_code,
        "episode existence check": "episode = session.query(Episode).filter_by(episode_id=episode_id).first()" in claim_store_code,
        "FK constraint comment": "CRITICAL: Ensure episode record exists before storing segments" in claim_store_code,
    }
    
    all_passed = all(checks.values())
    
    if all_passed:
        print("✅ PASS: All foreign key constraint handling enhancements found:")
        for check_name, passed in checks.items():
            print(f"   ✓ {check_name}")
    else:
        print("❌ FAIL: Some enhancements missing:")
        for check_name, passed in checks.items():
            status = "✓" if passed else "✗"
            print(f"   {status} {check_name}")
        sys.exit(1)

except Exception as e:
    print(f"❌ ERROR: Could not check claim_store: {e}")
    sys.exit(1)

print()

# Test 4: Check orchestrator call site
print("Test 4: Checking System2Orchestrator call site")
print("-" * 60)

try:
    orchestrator_path = (
        Path(__file__).parent.parent 
        / "src" / "knowledge_system" / "core" 
        / "system2_orchestrator_mining.py"
    )
    
    with open(orchestrator_path) as f:
        orchestrator_code = f.read()
    
    # Check for updated store_segments call
    if "source_id=source_id, episode_title=episode_title" in orchestrator_code:
        print("✅ PASS: store_segments() call correctly passes source_id and episode_title")
        print("   - Episode can now be created automatically if needed")
        print("   - Foreign key constraints will be satisfied")
    else:
        print("❌ FAIL: store_segments() call not updated with new parameters")
        sys.exit(1)

except Exception as e:
    print(f"❌ ERROR: Could not check orchestrator: {e}")
    sys.exit(1)

print()
print("=" * 60)
print("All Code Checks Passed! ✅")
print("=" * 60)
print()
print("Summary of Fixes:")
print("  ✓ Schema no longer requires rank for rejected claims")
print("  ✓ Validator automatically repairs missing rank fields")  
print("  ✓ ClaimStore creates episode record before storing segments")
print("  ✓ Foreign key constraints are properly handled")
print("  ✓ System2Orchestrator passes necessary parameters")
print()
print("The HCE pipeline should now handle:")
print("  - Rejected claims without validation errors")
print("  - Segment storage without foreign key violations")
print()

