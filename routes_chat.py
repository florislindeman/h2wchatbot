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

@router.post("@router.post("", response_model=ChatResponse)/ask", response_model=ChatResponse)
async def ask_question(
    question: ChatQuestion,
    current_user: TokenData = Depends(get_current_user)
):
    """Ask a question and get AI answer based on ALL documents"""
    supabase = get_supabase()
    openai_svc = get_openai_service()
    
    # Admins get ALL documents, regular users get filtered by category
    if current_user.role == "admin":
        # Admin: Get ALL documents
        docs_result = supabase.table("documents").select("*").execute()
    else:
        # Regular user: Filter by accessible categories
        user_cats = supabase.table("user_categories").select("category_id").eq("user_id", current_user.user_id).execute()
        user_category_ids = [item["category_id"] for item in user_cats.data]
        
        if not user_category_ids:
            return ChatResponse(
                answer="Je hebt nog geen toegang tot documentcategorieën.",
                confidence=0.0,
                sources=[]
            )
        
        doc_cats = supabase.table("document_categories").select("document_id").in_("category_id", user_category_ids).execute()
        allowed_doc_ids = list(set([item["document_id"] for item in doc_cats.data]))
        
        if not allowed_doc_ids:
            return ChatResponse(
                answer="Er zijn nog geen documenten beschikbaar.",
                confidence=0.0,
                sources=[]
            )
        
        docs_result = supabase.table("documents").select("*").in_("id", allowed_doc_ids).execute()
    
    if not docs_result.data:
        return ChatResponse(
            answer="Er zijn nog geen documenten beschikbaar.",
            confidence=0.0,
            sources=[]
        )
    
    # Build context from ALL documents
    full_docs_context = []
    sources = []
    
    for doc in docs_result.data:
        # Use FULL content_text (limit per doc to fit in GPT context)
        max_chars_per_doc = 8000  # Adjust based on number of docs
        
        full_docs_context.append({
            "document_title": doc["title"],
            "document_id": doc["id"],
            "full_text": doc["content_text"][:max_chars_per_doc],
            "file_url": doc["file_url"],
            "file_type": doc["file_type"]
        })
        
        sources.append(SourceDocument(
            document_id=doc["id"],
            document_title=doc["title"],
            document_url=doc["file_url"],
            file_type=doc["file_type"]
        ))
    
    # Generate answer with ALL documents
    try:
        context_for_ai = "\n\n=== NIEUW DOCUMENT ===\n\n".join([
            f"📄 Document: {doc['document_title']}\n\n{doc['full_text']}"
            for doc in full_docs_context
        ])
        
        # Call OpenAI with full context
        system_prompt = f"""Je bent een slimme AI-assistent voor Health2Work.
Je hebt toegang tot ALLE {len(full_docs_context)} beschikbare documenten in hun volledige inhoud.

BELANGRIJKE INSTRUCTIES:
1. Doorzoek ALLE documenten grondig
2. Zoek naar exacte bedragen (€ XX,-, EUR XX, XX euro)
3. Zoek naar artikelcodes, prijzen, kosten, SLA's
4. Als informatie in ELK document staat, vind het
5. Combineer informatie uit meerdere documenten indien nodig
6. Citeer ALTIJD de bron: "Volgens [documentnaam]: ..."
7. Wees specifiek en precies met bedragen en data
8. Als het echt nergens staat, zeg dan: "Deze informatie staat niet in de beschikbare documenten."

Je hebt deze {len(full_docs_context)} documenten tot je beschikking:
{chr(10).join([f"- {doc['document_title']}" for doc in full_docs_context])}

VOLLEDIGE DOCUMENTEN:

{context_for_ai}"""

        response = openai_svc.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question.question}
            ],
            temperature=0.2,
            max_tokens=1500
        )
        
        answer = response.choices[0].message.content
        
        # Calculate confidence based on answer content
        confidence = 85.0  # Default high confidence since we search all docs
        
        # Lower confidence if answer indicates uncertainty
        uncertainty_phrases = [
            'kan niet vinden',
            'niet in de beschikbare',
            'weet ik niet',
            'geen informatie',
            'staat niet in'
        ]
        
        if any(phrase in answer.lower() for phrase in uncertainty_phrases):
            confidence = 25.0
        elif 'volgens' in answer.lower() and '€' in answer:
            # High confidence when citing source with price
            confidence = 95.0
        
    except Exception as e:
        logger.error(f"Failed to generate answer: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate answer")
    
    # Save to chat history
    try:
        supabase.table("chat_history").insert({
            "user_id": current_user.user_id,
            "question": question.question,
            "answer": answer,
            "confidence_score": confidence,
            "source_documents": [s.model_dump() for s in sources]
        }).execute()
    except Exception as e:
        logger.error(f"Failed to save chat history: {e}")
    
    logger.info(f"Question answered with {confidence}% confidence, searched {len(sources)} documents")
    
    return ChatResponse(
        answer=answer,
        confidence=confidence,
        sources=sources
    )
