import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json
import re
from urllib.parse import urlparse

from app.services.azure_services import AzureServiceManager
from app.core.config import settings

logger = logging.getLogger(__name__)

class CredibilityAssessor:
    """
    Service for assessing the credibility of information sources
    Key component for Exercise 3: Adaptive Knowledge Base Management
    """
    
    def __init__(self, azure_manager: AzureServiceManager):
        self.azure_manager = azure_manager
        self.trusted_domains = {
            "sec.gov": 1.0,
            "edgar.sec.gov": 1.0,
            "investor.gov": 0.95,
            "fasb.org": 0.9,
            "pcaobus.org": 0.9,
            "federalreserve.gov": 0.95,
            "treasury.gov": 0.9,
            "bloomberg.com": 0.8,
            "reuters.com": 0.8,
            "wsj.com": 0.8,
            "ft.com": 0.8,
            "marketwatch.com": 0.7,
            "yahoo.com": 0.6,
            "google.com": 0.5
        }
        
    async def assess_credibility(self, processed_doc: Dict, source: str) -> float:
        """
        Assess the credibility of a document and its source
        
        Args:
            processed_doc: Processed document information
            source: Source URL or identifier
            
        Returns:
            Credibility score between 0.0 and 1.0
        """
        try:
            logger.info(f"Assessing credibility for source: {source}")
            
            source_score = self._assess_source_credibility(source)
            content_score = await self._assess_content_credibility(processed_doc)
            metadata_score = self._assess_metadata_credibility(processed_doc.get("metadata", {}))
            consistency_score = await self._assess_internal_consistency(processed_doc)
            
            weights = {
                "source": 0.3,
                "content": 0.3,
                "metadata": 0.2,
                "consistency": 0.2
            }
            
            final_score = (
                source_score * weights["source"] +
                content_score * weights["content"] +
                metadata_score * weights["metadata"] +
                consistency_score * weights["consistency"]
            )
            
            penalties = await self._check_credibility_red_flags(processed_doc, source)
            final_score = max(0.0, final_score - penalties)
            
            logger.info(f"Credibility assessment complete: {final_score:.3f} for {source}")
            
            return min(1.0, max(0.0, final_score))
            
        except Exception as e:
            logger.error(f"Error assessing credibility for {source}: {e}")
            return 0.5  # Default neutral score on error
    
    def _assess_source_credibility(self, source: str) -> float:
        """Assess credibility based on source domain and characteristics"""
        try:
            if source.startswith(('http://', 'https://')):
                parsed_url = urlparse(source)
                domain = parsed_url.netloc.lower()
                
                if domain.startswith('www.'):
                    domain = domain[4:]
                
                for trusted_domain, score in self.trusted_domains.items():
                    if domain == trusted_domain or domain.endswith('.' + trusted_domain):
                        return score
                
                if domain.endswith('.gov'):
                    return 0.9
                
                if domain.endswith('.edu'):
                    return 0.8
                
                if domain.endswith('.org'):
                    return 0.7
                
                if domain.endswith('.com'):
                    return 0.6
                
                return 0.5  # Unknown domain
            
            else:
                if 'sec' in source.lower() or 'edgar' in source.lower():
                    return 0.95
                if 'official' in source.lower() or 'government' in source.lower():
                    return 0.9
                return 0.7  # Local file or unknown source
                
        except Exception as e:
            logger.error(f"Error assessing source credibility: {e}")
            return 0.5
    
    async def _assess_content_credibility(self, processed_doc: Dict) -> float:
        """Assess credibility based on content characteristics"""
        try:
            content = processed_doc.get("extracted_content", {}).get("content", "")
            if not content:
                return 0.3
            
            score = 0.5  # Base score
            
            financial_indicators = [
                "SEC", "EDGAR", "10-K", "10-Q", "GAAP", "FASB", 
                "audited", "certified", "financial statements",
                "balance sheet", "income statement", "cash flow"
            ]
            
            indicator_count = sum(1 for indicator in financial_indicators 
                                if indicator.lower() in content.lower())
            score += min(0.3, indicator_count * 0.05)
            
            if await self._has_professional_language(content):
                score += 0.1
            
            if self._has_proper_citations(content):
                score += 0.1
            
            if len(content) > 1000:
                score += 0.05
            elif len(content) < 100:
                score -= 0.2
            
            return min(1.0, score)
            
        except Exception as e:
            logger.error(f"Error assessing content credibility: {e}")
            return 0.5
    
    async def _has_professional_language(self, content: str) -> bool:
        """Check if content uses professional financial language"""
        try:
            prompt = f"""
            Analyze the following financial document excerpt for professional language quality:
            
            {content[:1000]}
            
            Rate the professionalism on a scale of 1-10 considering:
            - Technical accuracy
            - Formal tone
            - Proper financial terminology
            - Clear structure
            
            Respond with only a number from 1-10.
            """
            
            response = await self.azure_manager.async_openai_client.chat.completions.create(
                model=settings.openai_chat_deployment,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10
            )
            
            score = int(response.choices[0].message.content.strip())
            return score >= 7
            
        except Exception as e:
            logger.error(f"Error checking professional language: {e}")
            return False
    
    def _has_proper_citations(self, content: str) -> bool:
        """Check for proper citations and references"""
        citation_patterns = [
            r'\[\d+\]',  # [1], [2], etc.
            r'\(\d{4}\)',  # (2023), (2024), etc.
            r'See\s+\w+',  # "See Note 1", etc.
            r'Reference\s+\w+',  # "Reference A", etc.
            r'Note\s+\d+',  # "Note 1", etc.
        ]
        
        citation_count = 0
        for pattern in citation_patterns:
            citation_count += len(re.findall(pattern, content, re.IGNORECASE))
        
        return citation_count > 0
    
    def _assess_metadata_credibility(self, metadata: Dict) -> float:
        """Assess credibility based on document metadata"""
        score = 0.5  # Base score
        
        try:
            important_fields = ["document_type", "company_name", "filing_date"]
            complete_fields = sum(1 for field in important_fields 
                                if metadata.get(field))
            score += (complete_fields / len(important_fields)) * 0.3
            
            doc_type = metadata.get("document_type", "").lower()
            if doc_type in ["10-k", "10-q", "annual-report"]:
                score += 0.2
            elif doc_type in ["earnings-report"]:
                score += 0.1
            
            filing_date = metadata.get("filing_date")
            if filing_date:
                try:
                    filing_dt = datetime.fromisoformat(filing_date.replace('Z', '+00:00'))
                    days_old = (datetime.utcnow() - filing_dt.replace(tzinfo=None)).days
                    if days_old < 365:  # Less than a year old
                        score += 0.1
                except:
                    pass
            
            return min(1.0, score)
            
        except Exception as e:
            logger.error(f"Error assessing metadata credibility: {e}")
            return 0.5
    
    async def _assess_internal_consistency(self, processed_doc: Dict) -> float:
        """Assess internal consistency of the document"""
        try:
            chunks = processed_doc.get("chunks", [])
            if len(chunks) < 2:
                return 0.7  # Can't assess consistency with too few chunks
            
            sample_size = min(5, len(chunks))
            sample_chunks = chunks[:sample_size]
            
            consistency_scores = []
            
            for i in range(len(sample_chunks) - 1):
                chunk1 = sample_chunks[i]["content"]
                chunk2 = sample_chunks[i + 1]["content"]
                
                consistency = await self._check_chunk_consistency(chunk1, chunk2)
                consistency_scores.append(consistency)
            
            if consistency_scores:
                return sum(consistency_scores) / len(consistency_scores)
            else:
                return 0.7
                
        except Exception as e:
            logger.error(f"Error assessing internal consistency: {e}")
            return 0.7
    
    async def _check_chunk_consistency(self, chunk1: str, chunk2: str) -> float:
        """Check consistency between two content chunks"""
        try:
            prompt = f"""
            Analyze these two excerpts from the same financial document for consistency:
            
            EXCERPT 1:
            {chunk1[:500]}
            
            EXCERPT 2:
            {chunk2[:500]}
            
            Rate consistency from 0.0 to 1.0 considering:
            - Factual consistency
            - Tone consistency
            - Terminology consistency
            - No contradictions
            
            Respond with only a decimal number from 0.0 to 1.0.
            """
            
            response = await self.azure_manager.async_openai_client.chat.completions.create(
                model=settings.openai_chat_deployment,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10
            )
            
            score = float(response.choices[0].message.content.strip())
            return max(0.0, min(1.0, score))
            
        except Exception as e:
            logger.error(f"Error checking chunk consistency: {e}")
            return 0.7
    
    async def _check_credibility_red_flags(self, processed_doc: Dict, source: str) -> float:
        """Check for red flags that reduce credibility"""
        penalties = 0.0
        
        try:
            content = processed_doc.get("extracted_content", {}).get("content", "")
            
            red_flags = [
                r"not\s+audited",
                r"unverified",
                r"preliminary",
                r"subject\s+to\s+change",
                r"draft",
                r"confidential",
                r"insider\s+information"
            ]
            
            for pattern in red_flags:
                if re.search(pattern, content, re.IGNORECASE):
                    penalties += 0.1
            
            if source.startswith('http://'):  # Non-HTTPS
                penalties += 0.05
            
            metadata = processed_doc.get("metadata", {})
            filing_date = metadata.get("filing_date")
            if filing_date:
                try:
                    filing_dt = datetime.fromisoformat(filing_date.replace('Z', '+00:00'))
                    hours_old = (datetime.utcnow() - filing_dt.replace(tzinfo=None)).total_seconds() / 3600
                    if hours_old < 1:  # Created less than an hour ago
                        penalties += 0.2
                except:
                    pass
            
            return min(0.5, penalties)  # Cap penalties at 0.5
            
        except Exception as e:
            logger.error(f"Error checking red flags: {e}")
            return 0.0
    
    async def compare_source_credibility(self, sources: List[str]) -> Dict[str, float]:
        """Compare credibility scores across multiple sources"""
        credibility_scores = {}
        
        for source in sources:
            try:
                score = self._assess_source_credibility(source)
                credibility_scores[source] = score
            except Exception as e:
                logger.error(f"Error comparing source {source}: {e}")
                credibility_scores[source] = 0.5
        
        return credibility_scores
    
    async def get_credibility_explanation(self, processed_doc: Dict, source: str, 
                                        final_score: float) -> str:
        """Generate human-readable explanation of credibility assessment"""
        try:
            factors = []
            
            source_score = self._assess_source_credibility(source)
            if source_score > 0.8:
                factors.append("highly trusted source domain")
            elif source_score > 0.6:
                factors.append("moderately trusted source")
            else:
                factors.append("unknown or less trusted source")
            
            content = processed_doc.get("extracted_content", {}).get("content", "")
            if "SEC" in content or "10-K" in content or "10-Q" in content:
                factors.append("official SEC filing indicators")
            
            metadata = processed_doc.get("metadata", {})
            if metadata.get("document_type") in ["10-k", "10-q"]:
                factors.append("formal regulatory document type")
            
            explanation = f"Credibility score: {final_score:.2f}. "
            explanation += f"Based on: {', '.join(factors)}."
            
            if final_score < 0.5:
                explanation += " Consider verifying information from additional sources."
            
            return explanation
            
        except Exception as e:
            logger.error(f"Error generating credibility explanation: {e}")
            return f"Credibility score: {final_score:.2f}. Assessment completed with limited analysis."
