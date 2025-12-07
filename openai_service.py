from openai import OpenAI
from config import settings
import logging
from typing import List
import numpy as np

logger = logging.getLogger(__name__)

class OpenAIService:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        logger.info("OpenAI client initialized")
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using OpenAI"""
        try:
            response = self.client.embeddings.create(
                input=text,
                model="text-embedding-ada-002"
            )
            embedding = response.data[0].embedding
            logger.info(f"Generated embedding for text of length {len(text)}")
            return embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    def generate_answer(self, question: str, context_chunks: List[dict]) -> tuple[str, float]:
        """
        Generate answer based on question and context chunks
        Returns: (answer, confidence_score)
        """
        if not context_chunks:
            return (
                "Ik kan helaas geen antwoord vinden op je vraag in de beschikbare documenten.",
                0.0
            )
        
        # Build context from chunks
        context = "\n\n---\n\n".join([
            f"[Document: {chunk['document_title']}]\n{chunk['chunk_text']}"
            for chunk in context_chunks
        ])
        
        system_prompt = f"""Je bent een behulpzame AI-assistent voor Health2Work. 
Gebruik ALLEEN de verstrekte context om vragen te beantwoorden.

BELANGRIJKE REGELS:
- Als het antwoord niet in de context staat, zeg dan: "Deze informatie staat niet in mijn kennisbank."
- Citeer indien mogelijk de bron
- Wees specifiek en concreet
- Gebruik een vriendelijke, professionele toon
- Antwoord in het Nederlands tenzij anders gevraagd
- Beantwoord de vraag ALLEEN op basis van de gegeven context
- Wees beknopt maar volledig

Context uit bedrijfsdocumenten:
{context}"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            answer = response.choices[0].message.content
            
            # Calculate confidence based on similarity scores
            avg_similarity = sum(chunk['similarity'] for chunk in context_chunks) / len(context_chunks)
            confidence = round(avg_similarity * 100, 1)
            
            # Lower confidence if answer indicates uncertainty
            if any(phrase in answer.lower() for phrase in [
                'kan niet beantwoorden',
                'niet in de beschikbare',
                'weet ik niet',
                'geen informatie'
            ]):
                confidence = min(confidence, 30.0)
            
            logger.info(f"Generated answer with confidence {confidence}%")
            return answer, confidence
            
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            raise
    
    def suggest_tags(self, filename: str, content_preview: str = None) -> List[str]:
        """Generate tag suggestions using GPT"""
        try:
            prompt = f"Genereer 5 relevante Nederlandse tags voor een document met de titel '{filename}'."
            if content_preview:
                prompt += f"\n\nInhoud preview:\n{content_preview[:500]}"
            
            prompt += "\n\nGeef alleen de tags terug als komma-gescheiden lijst, geen uitleg of nummering."
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Je bent een assistent die korte, relevante tags genereert voor documenten."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=50
            )
            
            tags_text = response.choices[0].message.content.strip()
            tags = [tag.strip() for tag in tags_text.split(',')]
            
            logger.info(f"Generated {len(tags)} tag suggestions")
            return tags[:5]  # Limit to 5 tags
            
        except Exception as e:
            logger.error(f"Error generating tags: {e}")
            return []
    
    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)
        
        dot_product = np.dot(vec1_np, vec2_np)
        norm1 = np.linalg.norm(vec1_np)
        norm2 = np.linalg.norm(vec2_np)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)

# Singleton instance
openai_service = OpenAIService()

def get_openai_service():
    return openai_service
