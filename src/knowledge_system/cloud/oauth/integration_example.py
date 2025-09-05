"""
Complete Knowledge_Chipper to GetReceipts.org Integration Example

This script demonstrates the complete OAuth authentication and data upload flow.
Use this as a reference for integrating with your main Knowledge_Chipper code.

Usage:
    python integration_example.py

Author: GetReceipts.org Team
License: MIT
"""

import json
import time
from typing import Dict, Any
from .getreceipts_uploader import GetReceiptsUploader
from .getreceipts_config import get_config, set_production, print_config, validate_config

def create_sample_session_data() -> Dict[str, Any]:
    """
    Create sample HCE session data for testing
    
    This simulates the data structure that Knowledge_Chipper produces
    after processing a video/audio file.
    """
    
    episode_id = f"test_episode_{int(time.time())}"
    claim_id = f"test_claim_{int(time.time())}"
    
    return {
        'episodes': [{
            'episode_id': episode_id,
            'title': 'Test Episode: Climate Science Discussion',
            'url': 'https://youtube.com/watch?v=climate_test_123',
            'duration_seconds': 3600,
            'recorded_at': '2024-01-15T10:00:00Z'
        }],
        
        'claims': [{
            'claim_id': claim_id,
            'canonical': 'Climate change is significantly influenced by human activities, particularly greenhouse gas emissions from fossil fuel combustion.',
            'episode_id': episode_id,
            'claim_type': 'factual',
            'tier': 'A',
            'temporality_score': 5,
            'scores_json': json.dumps({
                'confidence': 0.9,
                'importance': 0.8,
                'novelty': 0.3,
                'controversy': 0.2,
                'fragility': 0.1
            }),
            'structured_categories_json': json.dumps([
                'climate science',
                'environmental policy',
                'greenhouse gases'
            ])
        }],
        
        'evidence_spans': [{
            'claim_id': claim_id,
            'episode_id': episode_id,
            'quote': 'According to the IPCC report, human activities are responsible for approximately 1.1°C of warming since 1850-1900.',
            'evidence_type': 'supporting',
            't0': '00:15:30',
            't1': '00:15:45',
            'confidence': 0.95,
            'youtube_link': 'https://youtube.com/watch?v=climate_test_123&t=930s'
        }],
        
        'people': [{
            'claim_id': claim_id,
            'episode_id': episode_id,
            'surface_form': 'IPCC',
            'name': 'Intergovernmental Panel on Climate Change',
            'entity_type': 'organization',
            'confidence': 0.99,
            'timestamps': '00:15:35',
            'external_ids_json': json.dumps({
                'wikipedia': 'Intergovernmental_Panel_on_Climate_Change',
                'official_website': 'https://www.ipcc.ch/'
            })
        }],
        
        'jargon': [{
            'claim_id': claim_id,
            'episode_id': episode_id,
            'term': 'greenhouse gas emissions',
            'definition': 'Gases in the atmosphere that trap heat from the sun, including carbon dioxide, methane, and nitrous oxide.',
            'category': 'climate science',
            'domain': 'environmental science',
            'related_terms': ['carbon dioxide', 'methane', 'global warming potential'],
            'examples': ['CO2 from fossil fuels', 'methane from agriculture']
        }],
        
        'concepts': [{
            'claim_id': claim_id,
            'episode_id': episode_id,
            'name': 'anthropogenic climate change',
            'description': 'Climate change caused by human activities, primarily through greenhouse gas emissions.',
            'domain': 'climate science',
            'key_concepts': ['greenhouse effect', 'carbon cycle', 'radiative forcing'],
            'aliases': ['human-caused climate change', 'man-made global warming'],
            'relationships_json': json.dumps({
                'causes': ['fossil fuel combustion', 'deforestation'],
                'effects': ['global temperature rise', 'sea level rise', 'extreme weather']
            })
        }],
        
        'relations': [{
            'source_claim_id': claim_id,
            'target_claim_id': f"related_claim_{int(time.time())}",
            'relation_type': 'supports',
            'strength': 0.8,
            'rationale': 'Both claims discuss human impact on climate systems',
            'evidence': 'Scientific consensus from multiple studies'
        }]
    }

def test_authentication():
    """Test the OAuth authentication flow"""
    print("🔐 Testing Authentication Flow")
    print("=" * 50)
    
    try:
        uploader = GetReceiptsUploader()
        auth_result = uploader.authenticate()
        
        print(f"✅ Authentication successful!")
        print(f"   User: {auth_result['user_info']['name']}")
        print(f"   Email: {auth_result['user_info']['email']}")
        print(f"   ID: {auth_result['user_info']['id']}")
        
        return uploader
        
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return None

def test_data_upload(uploader: GetReceiptsUploader):
    """Test uploading sample data"""
    print("\n📤 Testing Data Upload")
    print("=" * 50)
    
    try:
        # Create sample data
        session_data = create_sample_session_data()
        
        print("📋 Sample data created:")
        for table, data in session_data.items():
            print(f"   {table}: {len(data)} records")
        
        print("\n🚀 Starting upload...")
        
        # Upload data
        results = uploader.upload_session_data(session_data)
        
        print(f"\n✅ Upload completed successfully!")
        print("📊 Upload results:")
        for table, data in results.items():
            count = len(data) if data else 0
            print(f"   {table}: {count} records uploaded")
        
        return True
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return False

def demonstrate_production_switch():
    """Demonstrate switching between development and production"""
    print("\n🔄 Configuration Management Demo")
    print("=" * 50)
    
    print("Current configuration:")
    print_config()
    
    print("\n🔄 Switching to production...")
    set_production()
    print_config()
    
    print("\n⚠️  Note: This is just a demo. For actual production use,")
    print("   ensure you have production credentials configured.")

def main():
    """
    Main integration example function
    
    This demonstrates the complete flow:
    1. Configuration validation
    2. Authentication
    3. Data upload
    4. Production configuration switching
    """
    
    print("🎯 Knowledge_Chipper → GetReceipts.org Integration Example")
    print("=" * 60)
    
    # 1. Check configuration
    print("📋 Checking configuration...")
    config = get_config()
    
    if not validate_config(config):
        print("❌ Configuration incomplete!")
        print("\nPlease update getreceipts_config.py with your actual credentials.")
        print("Run: python getreceipts_config.py for setup instructions.")
        return
    
    print("✅ Configuration valid")
    print_config()
    
    # 2. Test authentication
    uploader = test_authentication()
    if not uploader:
        print("\n❌ Cannot proceed without authentication")
        return
    
    # 3. Test data upload
    upload_success = test_data_upload(uploader)
    if not upload_success:
        print("\n❌ Upload test failed")
        return
    
    # 4. Demonstrate configuration switching
    demonstrate_production_switch()
    
    print("\n🎉 Integration example completed successfully!")
    print("\nNext steps:")
    print("1. Copy these files to your Knowledge_Chipper project")
    print("2. Update getreceipts_config.py with your credentials")
    print("3. Add upload_to_getreceipts() to your processing pipeline")
    print("4. Test with your actual HCE data")

def upload_to_getreceipts(session_data: Dict[str, Any], use_production: bool = False) -> Dict[str, Any]:
    """
    Main integration function for Knowledge_Chipper
    
    Add this function to your Knowledge_Chipper codebase and call it
    after processing a session to upload data to GetReceipts.org
    
    Args:
        session_data: Dictionary containing HCE results
        use_production: Whether to use production configuration
        
    Returns:
        Upload results dictionary
        
    Raises:
        Exception: If authentication or upload fails
    """
    
    # Switch to production if requested
    if use_production:
        set_production()
    
    # Validate configuration
    config = get_config()
    if not validate_config(config):
        raise Exception("GetReceipts configuration incomplete - check getreceipts_config.py")
    
    # Initialize uploader
    uploader = GetReceiptsUploader(
        supabase_url=config['supabase_url'],
        supabase_anon_key=config['supabase_anon_key'],
        base_url=config['base_url']
    )
    
    # Authenticate user
    auth_result = uploader.authenticate()
    print(f"🔐 Authenticated as: {auth_result['user_info']['name']}")
    
    # Upload data
    upload_results = uploader.upload_session_data(session_data)
    
    print("✅ Upload to GetReceipts.org completed!")
    return upload_results

if __name__ == "__main__":
    # Run the complete example
    main()
    
    print("\n" + "=" * 60)
    print("📚 Usage in your Knowledge_Chipper code:")
    print("=" * 60)
    print("""
from integration_example import upload_to_getreceipts

# After processing a video/audio file:
session_data = your_hce_processing_results

try:
    results = upload_to_getreceipts(session_data)
    print(f"✅ Uploaded to GetReceipts.org: {results}")
except Exception as e:
    print(f"❌ Upload failed: {e}")
""")
