"""
LangGraph RAG Pipeline Graph Builder
"""

import logging
from typing import Literal, Annotated
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .schemas import RAGState
from .nodes import (
    load_documents,
    clean_text,
    chunk_documents,
    embed_chunks,
    store_embeddings,
    embed_query,
    retrieve_chunks,
    select_units,
    generate_answer
)

logger = logging.getLogger(__name__)


def reducer(left: dict, right: dict) -> dict:
    """Reducer function for merging state updates."""
    result = left.copy()
    for key, value in right.items():
        if value is None:
            # Skip None values
            continue
        elif key in result and isinstance(result[key], list) and isinstance(value, list):
            # For lists, replace (nodes return complete lists)
            result[key] = value
        elif key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # For dicts, merge
            result[key] = {**result[key], **value}
        else:
            # Otherwise, replace
            result[key] = value
    return result


def build_rag_graph() -> StateGraph:
    """
    Build the LangGraph RAG pipeline.
    
    Returns:
        Compiled LangGraph StateGraph
    """
    logger.info("Building RAG LangGraph")
    
    # Create the graph with RAGState as TypedDict
    workflow = StateGraph(RAGState, reducer=reducer)
    
    # Add ingestion nodes
    workflow.add_node("load_documents", load_documents)
    workflow.add_node("clean_text", clean_text)
    workflow.add_node("chunk_documents", chunk_documents)
    workflow.add_node("embed_chunks", embed_chunks)
    workflow.add_node("store_embeddings", store_embeddings)
    
    # Add query nodes
    workflow.add_node("embed_query", embed_query)
    workflow.add_node("retrieve_chunks", retrieve_chunks)
    workflow.add_node("select_units", select_units)  # Runs in parallel with retrieve_chunks
    workflow.add_node("generate_answer", generate_answer)
    
    # Set entry points
    workflow.set_entry_point("load_documents")
    
    # Define ingestion flow
    workflow.add_edge("load_documents", "clean_text")
    workflow.add_edge("clean_text", "chunk_documents")
    workflow.add_edge("chunk_documents", "embed_chunks")
    workflow.add_edge("embed_chunks", "store_embeddings")
    workflow.add_edge("store_embeddings", END)
    
    # Define query flow (can be called separately)
    # After embedding query, run retrieval and unit selection in parallel
    workflow.add_edge("embed_query", "retrieve_chunks")
    workflow.add_edge("embed_query", "select_units")
    # Both feed into answer generation
    workflow.add_edge("retrieve_chunks", "generate_answer")
    workflow.add_edge("select_units", "generate_answer")
    workflow.add_edge("generate_answer", END)
    
    # Compile the graph with memory checkpoint
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    
    logger.info("RAG LangGraph built successfully")
    
    return app


def build_ingestion_graph() -> StateGraph:
    """
    Build a graph for ingestion only.
    
    Returns:
        Compiled LangGraph for ingestion
    """
    workflow = StateGraph(RAGState, reducer=reducer)
    
    workflow.add_node("load_documents", load_documents)
    workflow.add_node("clean_text", clean_text)
    workflow.add_node("chunk_documents", chunk_documents)
    workflow.add_node("embed_chunks", embed_chunks)
    workflow.add_node("store_embeddings", store_embeddings)
    
    workflow.set_entry_point("load_documents")
    workflow.add_edge("load_documents", "clean_text")
    workflow.add_edge("clean_text", "chunk_documents")
    workflow.add_edge("chunk_documents", "embed_chunks")
    workflow.add_edge("embed_chunks", "store_embeddings")
    workflow.add_edge("store_embeddings", END)
    
    return workflow.compile()


def build_query_graph() -> StateGraph:
    """
    Build a graph for query answering only.
    
    Returns:
        Compiled LangGraph for query answering
    """
    workflow = StateGraph(RAGState, reducer=reducer)
    
    workflow.add_node("embed_query", embed_query)
    workflow.add_node("retrieve_chunks", retrieve_chunks)
    workflow.add_node("select_units", select_units)
    workflow.add_node("generate_answer", generate_answer)
    
    workflow.set_entry_point("embed_query")
    # Run retrieval and unit selection in parallel
    workflow.add_edge("embed_query", "retrieve_chunks")
    workflow.add_edge("embed_query", "select_units")
    # Both feed into answer generation
    workflow.add_edge("retrieve_chunks", "generate_answer")
    workflow.add_edge("select_units", "generate_answer")
    workflow.add_edge("generate_answer", END)
    
    return workflow.compile()

