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
    
    user_cats = supabase.table("user_categories").select("category_id").eq("user_id", current_user.user_id).execute()
    user_category_ids = [item["category_id"] for item in user_cats.data]
    
    if not user_category_ids:
        return ChatResponse(
            answer="Je hebt nog geen toegang tot documentcategorieën. Neem contact op met de administrator.",
            confidence=0.0,
            sources=[]
        )
    
    if question.category_filters:
        allowed_categories = [cat for cat in question.category_filters if cat in user_category_ids]
        if not allowed_categories:
            allowed_categories = user_category_ids
    else:
        allowed_categories = user_category_ids
    
    try:
        question_embedding = openai_svc.generate_embedding(question.question)
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        raise HTTPException(status_code=500, detail="Failed to process question")
    
    doc_cats = supabase.table("document_categories").select("document_id").in_("category_id", allowed_categories).execute()
    allowed_doc_ids = list(set([item["document_id"] for item in doc_cats.data]))
    
    if not allowed_doc_ids:
        return ChatResponse(
            answer="Er zijn nog geen documenten beschikbaar in je categorieën.",
            confidence=0.0,
            sources=[]
        )
    
    embeddings_result = supabase.table("document_embeddings").select("*").in_("document_id", allowed_doc_ids).execute()
    
    if not embeddings_result.data:
        return ChatResponse(
            answer="Er zijn nog geen documenten geïndexeerd. Probeer het later opnieuw.",
            confidence=0.0,
            sources=[]
        )
    
    chunk_similarities = [:10]
    for chunk_data in embeddings_result.data:
        try:
            embedding = chunk_data["embedding"]
            if isinstance(embedding, str):
                import ast
                embedding = ast.literal_eval(embedding)
            if not isinstance(embedding, np.ndarray):
                embedding = np.array(embedding)
            
            similarity = OpenAIService.cosine_similarity(question_embedding, embedding)
            
            if similarity > 0.7:
                chunk_similarities.append({
                    "document_id": chunk_data["document_id"],
                    "chunk_text": chunk_data["chunk_text"],
                    "similarity": similarity
                })
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            continue
    
    chunk_similarities.sort(key=lambda x: x["similarity"], reverse=True)
    top_chunks = chunk_similarities[:5]
    
    if not top_chunks:
        supabase.table("chat_history").insert({
            "user_id": current_user.user_id,
            "question": question.question,
            "answer": "Ik kan deze vraag niet beantwoorden op basis van de beschikbare documenten.",
            "confidence_score": 0.0,
            "source_documents": []
        }).execute()
        
        return ChatResponse(
            answer="Ik kan helaas geen relevant antwoord vinden in de beschikbare documenten.",
            confidence=0.0,
            sources=[]
        )
    
    doc_ids = list(set([chunk["document_id"] for chunk in top_chunks]))
    docs_result = supabase.table("documents").select("*").in_("id", doc_ids).execute()
    docs_map = {doc["id"]: doc for doc in docs_result.data}
    
    filtered_chunks = []
    for chunk in top_chunks:
        doc = docs_map.get(chunk["document_id"])
        if not doc:
            continue
        
        if question.date_filter_start and datetime.fromisoformat(doc["upload_date"]) < question.date_filter_start:
            continue
        if question.date_filter_end and datetime.fromisoformat(doc["upload_date"]) > question.date_filter_end:
            continue
        if question.file_type_filters and doc["file_type"] not in question.file_type_filters:
            continue
        if doc.get("expiry_date") and datetime.fromisoformat(doc["expiry_date"]) < datetime.now():
            continue
        
        chunk["document_title"] = doc["title"]
        chunk["document_url"] = doc["file_url"]
        chunk["file_type"] = doc["file_type"]
        filtered_chunks.append(chunk)
    
    if not filtered_chunks:
        return ChatResponse(
            answer="Geen documenten gevonden die voldoen aan je filters.",
            confidence=0.0,
            sources=[]
        )
    
    try:
        answer, confidence = openai_svc.generate_answer(question.question, filtered_chunks)
    except Exception as e:
        logger.error(f"Failed to generate answer: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate answer")
    
    sources = []
    seen_doc_ids = set()
    for chunk in filtered_chunks:
        if chunk["document_id"] not in seen_doc_ids:
            sources.append(SourceDocument(
                document_id=chunk["document_id"],
                document_title=chunk["document_title"],
                document_url=chunk["document_url"],
                file_type=chunk["file_type"]
            ))
            seen_doc_ids.add(chunk["document_id"])
    
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

@router.get("/history", response_model=List[ChatHistory])
async def get_chat_history(
    limit: int = 50,
    current_user: TokenData = Depends(get_current_user)
):
    """Get chat history for current user (last 1 month)"""
    supabase = get_supabase()
    
    one_month_ago = datetime.now() - timedelta(days=30)
    
    result = supabase.table("chat_history").select("*").eq("user_id", current_user.user_id).gte("created_at", one_month_ago.isoformat()).order("created_at", desc=True).limit(limit).execute()
    
    chats = []
    for chat in result.data:
        sources = [SourceDocument(**s) for s in chat.get("source_documents", [])]
        chats.append(ChatHistory(**{**chat, "source_documents": sources}))
    
    return chats

@router.post("/history/{chat_id}/feedback")
async def submit_feedback(
    chat_id: str,
    feedback: ChatFeedback,
    current_user: TokenData = Depends(get_current_user)
):
    """Submit thumbs up/down feedback for a chat response"""
    supabase = get_supabase()
    
    chat_result = supabase.table("chat_history").select("user_id").eq("id", chat_id).execute()
    
    if not chat_result.data:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    if chat_result.data[0]["user_id"] != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not your chat")
    
    supabase.table("chat_history").update({"feedback": feedback.feedback}).eq("id", chat_id).execute()
    
    logger.info(f"Feedback submitted for chat {chat_id}: {feedback.feedback}")
    return {"message": "Feedback submitted"}

@router.delete("/history")
async def clear_chat_history(current_user: TokenData = Depends(get_current_user)):
    """Clear chat history for current user"""
    supabase = get_supabase()
    
    supabase.table("chat_history").delete().eq("user_id", current_user.user_id).execute()
    
    logger.info(f"Chat history cleared for user {current_user.user_id}")
    return {"message": "Chat history cleared"}
