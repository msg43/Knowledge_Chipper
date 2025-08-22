"""
Knowledge_Chipper to GetReceipts Integration
Add this to your Knowledge_Chipper project to export artifacts to GetReceipts
"""

import requests
import json
from typing import Dict, List, Any, Optional


class GetReceiptsExporter:
    """Exports Knowledge_Chipper artifacts to GetReceipts in RF-1 format"""
    
    def __init__(self, getreceipts_url: str = "http://localhost:3000"):
        self.base_url = getreceipts_url.rstrip('/')
        self.session = requests.Session()
        
    def export_session_data(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Export a complete Knowledge_Chipper session to GetReceipts
        
        Args:
            session_data: Dictionary containing all processed data from Knowledge_Chipper
                Expected structure:
                {
                    'transcription': {...},
                    'summary': {...},
                    'people': [...],
                    'jargon': [...],
                    'mental_models': [...],
                    'source_url': 'optional',
                    'source_title': 'optional'
                }
        """
        
        # Extract main claims from summary
        claims = self._extract_claims_from_summary(session_data.get('summary', {}))
        
        results = []
        for claim in claims:
            receipt = self._build_rf1_receipt(claim, session_data)
            result = self._submit_receipt(receipt)
            results.append(result)
            
        return {
            'success': True,
            'claims_submitted': len(results),
            'results': results
        }
    
    def _extract_claims_from_summary(self, summary_data: Dict) -> List[Dict]:
        """Extract factual claims from Knowledge_Chipper summary data"""
        claims = []
        
        # Adapt this to your actual Knowledge_Chipper summary structure
        if 'key_points' in summary_data:
            for point in summary_data['key_points']:
                claims.append({
                    'main_claim': point.get('summary', point.get('text', '')),
                    'detailed_explanation': point.get('details', ''),
                    'topics': point.get('categories', []),
                    'supporting_evidence': point.get('evidence', []),
                    'confidence': point.get('confidence', 0.5)
                })
        
        # If no structured key_points, try to extract from main summary
        elif 'main_summary' in summary_data:
            claims.append({
                'main_claim': summary_data['main_summary'][:500],
                'detailed_explanation': summary_data.get('detailed_summary', ''),
                'topics': summary_data.get('topics', []),
                'supporting_evidence': [],
                'confidence': 0.7
            })
            
        return claims
    
    def _build_rf1_receipt(self, claim: Dict, session_data: Dict) -> Dict:
        """Build RF-1 formatted receipt from claim and session data"""
        
        return {
            "claim_text": claim['main_claim'],
            "claim_long": claim.get('detailed_explanation', ''),
            "topics": claim.get('topics', []),
            "sources": self._format_sources(session_data),
            "supporters": claim.get('supporting_evidence', []),
            "opponents": [],  # Knowledge_Chipper might not extract counterarguments
            "provenance": {
                "producer_app": "Knowledge_Chipper",
                "version": "2.0",
                "session_id": session_data.get('session_id', 'unknown'),
                "confidence": claim.get('confidence', 0.5)
            },
            "knowledge_artifacts": {
                "people": self._format_people(session_data.get('people', [])),
                "jargon": self._format_jargon(session_data.get('jargon', [])),
                "mental_models": self._format_mental_models(session_data.get('mental_models', [])),
                "claim_relationships": []  # Filled in later by relationship analysis
            }
        }
    
    def _format_sources(self, session_data: Dict) -> List[Dict]:
        """Format source information for RF-1"""
        sources = []
        
        # Add the original source (video/audio file)
        if session_data.get('source_url'):
            sources.append({
                "type": "video" if "youtube" in session_data['source_url'] else "article",
                "title": session_data.get('source_title', 'Audio/Video Content'),
                "url": session_data['source_url'],
                "date": session_data.get('processed_date')
            })
            
        # Add any additional sources found in the content
        if 'sources' in session_data:
            for source in session_data['sources']:
                sources.append({
                    "type": source.get('type', 'article'),
                    "title": source.get('title', ''),
                    "url": source.get('url', ''),
                    "doi": source.get('doi', ''),
                    "venue": source.get('venue', '')
                })
                
        return sources
    
    def _format_people(self, people_data: List[Dict]) -> List[Dict]:
        """Format people data for Knowledge_Chipper artifacts"""
        formatted_people = []
        
        for person in people_data:
            formatted_people.append({
                "name": person.get('name', ''),
                "bio": person.get('bio', person.get('description', '')),
                "expertise": person.get('expertise', person.get('areas', [])),
                "credibility_score": person.get('credibility', 0.5),
                "sources": person.get('mentions', person.get('sources', []))
            })
            
        return formatted_people
    
    def _format_jargon(self, jargon_data: List[Dict]) -> List[Dict]:
        """Format jargon/terminology data"""
        formatted_jargon = []
        
        for term in jargon_data:
            formatted_jargon.append({
                "term": term.get('term', term.get('name', '')),
                "definition": term.get('definition', term.get('explanation', '')),
                "domain": term.get('domain', term.get('category', '')),
                "related_terms": term.get('related', []),
                "examples": term.get('examples', [])
            })
            
        return formatted_jargon
    
    def _format_mental_models(self, models_data: List[Dict]) -> List[Dict]:
        """Format mental models data"""
        formatted_models = []
        
        for model in models_data:
            formatted_models.append({
                "name": model.get('name', model.get('title', '')),
                "description": model.get('description', model.get('summary', '')),
                "domain": model.get('domain', model.get('category', '')),
                "key_concepts": model.get('concepts', model.get('key_terms', [])),
                "relationships": model.get('relationships', [])
            })
            
        return formatted_models
    
    def _submit_receipt(self, receipt: Dict) -> Dict:
        """Submit RF-1 receipt to GetReceipts API"""
        try:
            response = self.session.post(
                f"{self.base_url}/api/receipts",
                json=receipt,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            return {
                "error": str(e),
                "receipt": receipt  # Include for debugging
            }


def example_usage():
    """Example of how to use the exporter in your Knowledge_Chipper workflow"""
    
    # Example session data structure - adapt to your actual data
    session_data = {
        'session_id': 'session_123',
        'source_url': 'https://youtube.com/watch?v=example',
        'source_title': 'AI Research Discussion',
        'transcription': {
            'text': 'Full transcription text...',
            'timestamp': '2024-01-15'
        },
        'summary': {
            'key_points': [
                {
                    'summary': 'Large language models show emergent capabilities at scale',
                    'details': 'Research indicates that capabilities like few-shot learning emerge...',
                    'categories': ['AI', 'Machine Learning', 'Research'],
                    'evidence': ['GPT-3 paper results', 'Empirical observations'],
                    'confidence': 0.8
                }
            ]
        },
        'people': [
            {
                'name': 'Dr. Jane Smith',
                'bio': 'AI researcher at Stanford',
                'expertise': ['Machine Learning', 'NLP'],
                'credibility': 0.9,
                'mentions': ['Mentioned as lead author', 'Cited multiple times']
            }
        ],
        'jargon': [
            {
                'term': 'Emergent Capabilities',
                'definition': 'Abilities that appear suddenly as model scale increases',
                'domain': 'AI Research',
                'related': ['Scaling Laws', 'Phase Transitions'],
                'examples': ['Few-shot learning', 'Chain-of-thought reasoning']
            }
        ],
        'mental_models': [
            {
                'name': 'Scaling Hypothesis',
                'description': 'The idea that AI capabilities improve predictably with scale',
                'domain': 'AI Research',
                'concepts': ['Compute', 'Data', 'Parameters'],
                'relationships': [
                    {'from': 'Compute', 'to': 'Performance', 'type': 'enables'},
                    {'from': 'Data', 'to': 'Capabilities', 'type': 'enables'}
                ]
            }
        ]
    }
    
    # Export to GetReceipts
    exporter = GetReceiptsExporter("http://localhost:3000")
    result = exporter.export_session_data(session_data)
    
    print(f"Export result: {json.dumps(result, indent=2)}")
    
    return result


if __name__ == "__main__":
    # Run example
    example_usage()
