"""
Chat Memory Management Module
Implements Buffer Window Memory for conversation history.
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)


class ChatMessage:
    """Represents a single chat message."""
    
    def __init__(self, role: str, content: str, timestamp: Optional[datetime] = None):
        """
        Initialize a chat message.
        
        Args:
            role: Message role ('user' or 'assistant')
            content: Message content
            timestamp: Message timestamp (defaults to now)
        """
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.now()
    
    def to_dict(self) -> Dict:
        """Convert message to dictionary."""
        return {
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ChatMessage':
        """Create message from dictionary."""
        timestamp = datetime.fromisoformat(data['timestamp']) if 'timestamp' in data else datetime.now()
        return cls(
            role=data['role'],
            content=data['content'],
            timestamp=timestamp
        )


class BufferWindowMemory:
    """
    Buffer Window Memory for conversation history.
    Maintains the last N messages per session.
    """
    
    def __init__(self, max_messages: int = 20):
        """
        Initialize buffer window memory.
        
        Args:
            max_messages: Maximum number of messages to keep per session
        """
        self.max_messages = max_messages
        self.sessions: Dict[str, List[ChatMessage]] = defaultdict(list)
        logger.info(f"Initialized BufferWindowMemory with max_messages={max_messages}")
    
    def add_message(self, session_id: str, role: str, content: str) -> None:
        """
        Add a message to the conversation history.
        
        Args:
            session_id: Session identifier
            role: Message role ('user' or 'assistant')
            content: Message content
        """
        message = ChatMessage(role=role, content=content)
        self.sessions[session_id].append(message)
        
        # Enforce window size
        if len(self.sessions[session_id]) > self.max_messages:
            # Remove oldest messages
            removed = len(self.sessions[session_id]) - self.max_messages
            self.sessions[session_id] = self.sessions[session_id][-self.max_messages:]
            logger.debug(f"Session {session_id}: Removed {removed} old messages, kept {self.max_messages}")
        
        logger.debug(f"Session {session_id}: Added {role} message (total: {len(self.sessions[session_id])})")
    
    def get_history(self, session_id: str) -> List[ChatMessage]:
        """
        Get conversation history for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of ChatMessage objects
        """
        return self.sessions.get(session_id, [])
    
    def get_history_dict(self, session_id: str) -> List[Dict]:
        """
        Get conversation history as list of dictionaries.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of message dictionaries
        """
        return [msg.to_dict() for msg in self.get_history(session_id)]
    
    def get_history_text(self, session_id: str, format_for_prompt: bool = True, exclude_last: int = 0) -> str:
        """
        Get conversation history as formatted text.
        
        Args:
            session_id: Session identifier
            format_for_prompt: If True, format for LLM prompt
            exclude_last: Number of last messages to exclude (useful when adding current message)
            
        Returns:
            Formatted conversation history string
        """
        messages = self.get_history(session_id)
        if not messages:
            return ""
        
        # Exclude last N messages if requested
        if exclude_last > 0:
            messages = messages[:-exclude_last]
        
        if not messages:
            return ""
        
        if format_for_prompt:
            # Format for LLM prompt
            lines = []
            for msg in messages:
                if msg.role == 'user':
                    lines.append(f"المستخدم: {msg.content}")
                elif msg.role == 'assistant':
                    lines.append(f"المساعد: {msg.content}")
            return "\n\n".join(lines)
        else:
            # Simple format
            return "\n".join([f"{msg.role}: {msg.content}" for msg in messages])
    
    def clear_session(self, session_id: str) -> None:
        """
        Clear conversation history for a session.
        
        Args:
            session_id: Session identifier
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Cleared history for session {session_id}")
    
    def get_session_count(self) -> int:
        """Get number of active sessions."""
        return len(self.sessions)
    
    def get_message_count(self, session_id: str) -> int:
        """Get number of messages in a session."""
        return len(self.sessions.get(session_id, []))


# Global memory instance
_global_memory: Optional[BufferWindowMemory] = None


def get_memory(max_messages: int = 20) -> BufferWindowMemory:
    """
    Get or create the global memory instance.
    
    Args:
        max_messages: Maximum messages per session (only used on first call)
        
    Returns:
        BufferWindowMemory instance
    """
    global _global_memory
    if _global_memory is None:
        _global_memory = BufferWindowMemory(max_messages=max_messages)
    return _global_memory


def reset_memory() -> None:
    """Reset the global memory instance (useful for testing)."""
    global _global_memory
    _global_memory = None

