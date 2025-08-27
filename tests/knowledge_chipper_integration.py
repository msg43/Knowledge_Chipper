#!/usr/bin/env python3
"""
GetReceipts Integration for Knowledge_Chipper

This module provides a simple one-function integration to automatically
publish knowledge_chipper results to GetReceipts.org.

USAGE FOR LLM:
Simply call publish_to_getreceipts() with your extracted data.
"""

import os
import requests
import json
from typing import List, Dict, Any, Optional

# Configuration
GETRECEIPTS_API_KEY = os.getenv('GETRECEIPTS_API_KEY')
GETRECEIPTS_API_URL = os.getenv('GETRECEIPTS_API_URL', 'http://localhost:3000/api')

def publish_to_getreceipts(
    transcript: str,
    video_url: str,
    claims: List[str],
    people: List[Dict[str, Any]] = None,
    jargon: List[Dict[str, Any]] = None,
    mental_models: List[Dict[str, Any]] = None,
    topics: List[str] = None
) -> Dict[str, Any]:
    """
    ONE-FUNCTION INTEGRATION: Publish knowledge_chipper results to GetReceipts
    
    Args:
        transcript (str): Full transcript text from the video
        video_url (str): URL of the source video
        claims (List[str]): List of extracted factual claims
        people (List[Dict], optional): People mentioned in the content
        jargon (List[Dict], optional): Technical terms and definitions
        mental_models (List[Dict], optional): Conceptual frameworks identified
        topics (List[str], optional): Categories/tags for the content
        
    Returns:
        Dict with results: {
            'success': bool,
            'published_claims': int,
            'failed_claims': int,
            'claim_urls': List[str],
            'errors': List[str]
        }
    
    Example:
        result = publish_to_getreceipts(
            transcript="Dr. Smith explains that AI models require...",
            video_url="https://youtube.com/watch?v=abc123",
            claims=["AI models require large datasets", "Deep learning uses neural networks"],
            people=[{"name": "Dr. Smith", "bio": "AI researcher", "expertise": ["AI"]}],
            jargon=[{"term": "neural network", "definition": "Computing system inspired by biology"}],
            topics=["AI", "machine learning"]
        )
        print(f"Published {result['published_claims']} claims!")
    """
    
    if not GETRECEIPTS_API_KEY:
        return {
            'success': False,
            'published_claims': 0,
            'failed_claims': len(claims),
            'claim_urls': [],
            'errors': ['GETRECEIPTS_API_KEY environment variable not set']
        }
    
    # Set defaults for optional parameters
    people = people or []
    jargon = jargon or []
    mental_models = mental_models or []
    topics = topics or ["knowledge_chipper", "video_content"]
    
    print(f"🚀 Publishing {len(claims)} claims to GetReceipts...")
    
    # Results tracking
    published_claims = []
    failed_claims = []
    claim_urls = []
    errors = []
    
    # Submit each claim
    for i, claim_text in enumerate(claims):
        try:
            # Create RF-1 format for this claim
            rf1_claim = {
                "claim_text": claim_text,
                "claim_long": transcript[:1000] if len(transcript) > 1000 else transcript,
                "topics": topics,
                "sources": [
                    {
                        "type": "video",
                        "title": f"Video Content - Claim {i+1}",
                        "url": video_url
                    }
                ],
                "supporters": [],
                "opponents": [],
                "provenance": {
                    "producer_app": "knowledge_chipper",
                    "version": "1.0"
                },
                "knowledge_artifacts": {
                    "people": people,
                    "jargon": jargon,
                    "mental_models": mental_models
                }
            }
            
            # Submit to GetReceipts API
            headers = {
                'Authorization': f'Bearer {GETRECEIPTS_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                f'{GETRECEIPTS_API_URL}/receipts',
                headers=headers,
                json=rf1_claim,
                timeout=30
            )
            
            if response.status_code == 201:
                result = response.json()
                published_claims.append(result)
                claim_url = f"http://localhost:3000{result['url']}"
                claim_urls.append(claim_url)
                print(f"✅ Claim {i+1}: {claim_text[:50]}...")
                print(f"   🔗 {claim_url}")
            else:
                error_msg = f"Claim {i+1} failed: HTTP {response.status_code}"
                failed_claims.append(claim_text)
                errors.append(error_msg)
                print(f"❌ {error_msg}")
                
        except Exception as e:
            error_msg = f"Claim {i+1} error: {str(e)}"
            failed_claims.append(claim_text)
            errors.append(error_msg)
            print(f"❌ {error_msg}")
    
    # Summary
    success = len(published_claims) > 0
    print(f"\n📊 Results: {len(published_claims)} published, {len(failed_claims)} failed")
    
    return {
        'success': success,
        'published_claims': len(published_claims),
        'failed_claims': len(failed_claims),
        'claim_urls': claim_urls,
        'errors': errors,
        'detailed_results': published_claims
    }

# Example usage and testing
if __name__ == "__main__":
    print("🧪 Testing GetReceipts integration...")
    
    # Test data
    test_result = publish_to_getreceipts(
        transcript="Dr. Sarah Chen explains that machine learning models require vast amounts of training data to achieve good performance. The concept of overfitting occurs when a model memorizes training data rather than learning generalizable patterns.",
        video_url="https://example.com/ai-lecture.mp4",
        claims=[
            "Machine learning models require vast amounts of training data to achieve good performance",
            "Overfitting occurs when models memorize training data rather than learning patterns"
        ],
        people=[
            {
                "name": "Dr. Sarah Chen",
                "bio": "Machine Learning researcher at Stanford University",
                "expertise": ["machine learning", "deep learning", "AI safety"],
                "credibility_score": 0.85,
                "sources": ["Stanford profile", "100+ papers"]
            }
        ],
        jargon=[
            {
                "term": "overfitting",
                "definition": "A modeling error when ML models memorize training data rather than learning patterns",
                "domain": "machine learning",
                "related_terms": ["generalization", "training data", "validation"],
                "examples": ["high training accuracy but poor test accuracy"]
            }
        ],
        mental_models=[
            {
                "name": "Bias-Variance Tradeoff",
                "description": "The fundamental tradeoff between model complexity and generalization",
                "domain": "machine learning",
                "key_concepts": ["bias", "variance", "overfitting", "underfitting"],
                "relationships": [
                    {"from": "high complexity", "to": "overfitting", "type": "causes"},
                    {"from": "overfitting", "to": "poor generalization", "type": "causes"}
                ]
            }
        ],
        topics=["machine learning", "AI", "Stanford", "education"]
    )
    
    if test_result['success']:
        print(f"🎉 Test successful! Published {test_result['published_claims']} claims")
        for url in test_result['claim_urls']:
            print(f"   📄 {url}")
    else:
        print(f"❌ Test failed: {test_result['errors']}")
