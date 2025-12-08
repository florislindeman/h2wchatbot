from fastapi import APIRouter, HTTPException, Depends
from typing import List
import numpy as np
from models import ChatQuestion, ChatResponse, ChatHistory, ChatFeedback, SourceDocument
from auth import get_current_user, TokenData
from database import get_supabase
from openai_service import get_openai_service, OpenAIService
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["Chat"])

@router.post("/ask", response_model=ChatResponse)
async def ask_question(
    question: ChatQuestion,
    current_user: TokenData = Depends(get_current_user)
):
    """Ask a question and get AI answer based on documents"""
    supabase = get_supabase()
    openai_svc = get_openai_service()
    
    # Get user's accessible documents
    user_cats = supabase.table("user_categories").select("category_id").eq("user_id", current_user.user_id).execute()
    user_category_ids = [item["category_id"] for item in user_cats.data]
    
    if not user_category_ids:
        return ChatResponse(
            answer="Je hebt nog geen toegang tot documentcategorieën.",
            confidence=0.0,
            sources=[]
        )
    
    # Get accessible document IDs
    doc_cats = supabase.table("document_categories").select("document_id").in_("category_id", user_category_ids).execute()
    allowed_doc_ids = list(set([item["document_id"] for item in doc_cats.data]))
    
    if not allowed_doc_ids:
        return ChatResponse(
            answer="Er zijn nog geen documenten beschikbaar.",
            confidence=0.0,
            sources=[]
        )
    
    # Generate question embedding
    try:
        question_embedding = openai_svc.generate_embedding(question.question)
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        raise HTTPException(status_code=500, detail="Failed to process question")
    
    # Get embeddings for all accessible documents
    embeddings_result = supabase.table("document_embeddings").select("*").in_("document_id", allowed_doc_ids).execute()
    
    if not embeddings_result.data:
        return ChatResponse(
            answer="Er zijn nog geen documenten geïndexeerd.",
            confidence=0.0,
            sources=[]
        )
    
    # Calculate similarity per DOCUMENT (average of chunks)
    document_scores = {}
    for chunk_data in embeddings_result.data:
        try:
            embedding = chunk_data["embedding"]
            if isinstance(embedding, str):
                import ast
                embedding = ast.literal_eval(embedding)
            
            similarity = OpenAIService.cosine_similarity(question_embedding, embedding)
            doc_id = chunk_data["document_id"]
            
            if doc_id not in document_scores:
                document_scores[doc_id] = []
            document_scores[doc_id].append(similarity)
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            continue
    
    # Average similarity per document
    doc_avg_scores = {
        doc_id: sum(scores) / len(scores) 
        for doc_id, scores in document_scores.items()
    }
    
    # Get top 3 most relevant documents
    top_docs = sorted(doc_avg_scores.items(), key=lambda x: x[1], reverse=True)[:3]
    top_doc_ids = [doc_id for doc_id, score in top_docs if score > 0.5]
    
    if not top_doc_ids:
        return ChatResponse(
            answer="Ik kan geen relevant antwoord vinden in de beschikbare documenten.",
            confidence=0.0,
            sources=[]
        )
    
    # Get FULL CONTENT of top documents
    docs_result = supabase.table("documents").select("*").in_("id", top_doc_ids).execute()
    
    if not docs_result.data:
        return ChatResponse(
            answer="Documenten niet gevonden.",
            confidence=0.0,
            sources=[]
        )
    
    # Build context from FULL documents
    full_docs_context = []
    sources = []
    
    for doc in docs_result.data:
        # Use FULL content_text instead of chunks
        full_docs_context.append({
            "document_title": doc["title"],
            "document_id": doc["id"],
            "full_text": doc["content_text"][:15000],  # Max 15k chars per doc to fit in GPT context
            "file_url": doc["file_url"],
            "file_type": doc["file_type"]
        })
        
        sources.append(SourceDocument(
            document_id=doc["id"],
            document_title=doc["title"],
            document_url=doc["file_url"],
            file_type=doc["file_type"]
        ))
    
    # Generate answer with FULL documents
    try:
        context_for_ai = "\n\n---\n\n".join([
            f"[Document: {doc['document_title']}]\n{doc['full_text']}"
            for doc in full_docs_context
        ])
        
        # Call OpenAI with full context
        system_prompt = f"""Je bent een slimme AI-assistent voor Health2Work.
Je hebt toegang tot de VOLLEDIGE INHOUD van {len(full_docs_context)} documenten.

BELANGRIJKE INSTRUCTIES:
- Lees de documenten GRONDIG door
- Zoek naar bedragen (€ XX,-, EUR XX, XX euro)
- Zoek naar artikelcodes, prijzen, kosten
- Als de informatie er staat, geef het antwoord
- Citeer de bron: "Volgens [documentnaam]: ..."
- Wees specifiek en precies

VOLLEDIGE DOCUMENTEN:
{context_for_ai}"""

        response = openai_svc.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question.question}
            ],
            temperature=0.2,
            max_tokens=1000
        )
        
        answer = response.choices[0].message.content
        
        # Calculate confidence based on document relevance
        avg_similarity = sum(score for _, score in top_docs[:len(full_docs_context)]) / len(full_docs_context)
        confidence = round(avg_similarity * 100, 1)
        
        # Lower confidence if answer indicates uncertainty
        if any(phrase in answer.lower() for phrase in [
            'kan niet beantwoorden',
            'niet in de beschikbare',
            'weet ik niet',
            'geen informatie'
        ]):
            confidence = min(confidence, 30.0)
        
    except Exception as e:
        logger.error(f"Failed to generate answer: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate answer")
    
    # Save to chat history
    supabase.table("chat_history").insert({
        "user_id": current_user.user_id,
        "question": question.question,
        "answer": answer,
        "confidence_score": confidence,
        "source_documents": [s.model_dump() for s in sources]
    }).execute()
    
    logger.info(f"Question answered with {confidence}% confidence, {len(sources)} sources")
    
    return ChatResponse(
        answer=answer,
        confidence=confidence,
        sources=sources
    )
