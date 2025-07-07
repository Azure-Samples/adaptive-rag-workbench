from typing import List, Dict
import re
from ..core.config import settings
from ..services.azure_services import azure_service_manager

class VerifierAgent:
    def __init__(self, kernel):
        self.kernel = kernel
        self.client = None
    
    async def _ensure_client(self):
        if self.client is None:
            self.client = azure_service_manager.async_openai_client
    
    async def get_response(self, retrieved_docs: List[Dict], query: str) -> str:
        await self._ensure_client()
        verified_docs = await self.invoke(retrieved_docs, query)
        avg_confidence = sum(doc['confidence'] for doc in verified_docs) / len(verified_docs) if verified_docs else 0
        return f"Verified {len(verified_docs)} documents with average confidence: {avg_confidence:.2f}"
    
    async def invoke_stream(self, retrieved_docs: List[Dict], query: str):
        verified_docs = await self.invoke(retrieved_docs, query)
        for doc in verified_docs:
            yield f"Verified: {doc['company']} {doc['year']} (confidence: {doc['confidence']:.2f})\n"
    
    async def invoke(self, retrieved_docs: List[Dict], query: str) -> List[Dict]:
        await self._ensure_client()
        verified_docs = []
        
        for doc in retrieved_docs:
            try:
                confidence = await self._assess_credibility_with_ai(doc, query)
            except Exception:
                confidence = self._assess_credibility(doc, query)
            
            doc["confidence"] = confidence
            doc["verified"] = confidence > 0.7
            verified_docs.append(doc)
        
        return sorted(verified_docs, key=lambda x: x["confidence"], reverse=True)
    
    async def _assess_credibility_with_ai(self, doc: Dict, query: str) -> float:
        try:
            prompt = f"""Assess the credibility and relevance of this document for the query.

Query: {query}
Document: {doc.get('content', '')[:500]}...
Company: {doc.get('company', 'Unknown')}
Year: {doc.get('year', 'Unknown')}
Source: {doc.get('source', 'Unknown')}

Rate the credibility and relevance on a scale of 0.0 to 1.0 considering:
1. Relevance to the query
2. Recency of information
3. Authority of the source
4. Content quality

Respond with only a number between 0.0 and 1.0."""

            response = await self.client.chat.completions.create(
                model=settings.openai_chat_deployment,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10
            )
            
            score_text = response.choices[0].message.content.strip()
            return min(max(float(score_text), 0.0), 1.0)
        except Exception:
            return self._assess_credibility(doc, query)
    
    def _assess_credibility(self, doc: Dict, query: str) -> float:
        content = doc.get('content', '').lower()
        query_lower = query.lower()
        company = doc.get('company', '')
        year = doc.get('year', 0)
        
        base_score = 0.8
        
        query_terms = re.findall(r'\b\w+\b', query_lower)
        content_terms = re.findall(r'\b\w+\b', content)
        
        matching_terms = sum(1 for term in query_terms if term in content_terms)
        relevance_score = min(matching_terms / max(len(query_terms), 1), 1.0)
        
        if year >= 2022:
            recency_bonus = 0.1
        elif year >= 2020:
            recency_bonus = 0.05
        else:
            recency_bonus = 0.0
        
        if company in ["Apple", "Microsoft", "Google", "Meta"]:
            authority_bonus = 0.1
        else:
            authority_bonus = 0.05
        
        final_score = base_score + (relevance_score * 0.2) + recency_bonus + authority_bonus
        return min(final_score, 1.0)
