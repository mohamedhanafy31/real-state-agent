"""
Selector Memory Management Module
Tracks last selected units per session for pronoun resolution.
"""

import logging
from typing import List, Dict, Any, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class SelectorMemory:
    """
    In-memory store for selector state per session.
    Tracks last selected units to enable pronoun resolution.
    """
    
    def __init__(self):
        """Initialize selector memory."""
        # session_id -> {
        #   'last_units': List[Dict[str, Any]],
        #   'focus_unit': Optional[Dict[str, Any]],
        #   'last_selection_reason': Optional[str]
        # }
        self.sessions: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'last_units': [],
            'focus_unit': None,
            'last_selection_reason': None
        })
        logger.info("Initialized SelectorMemory")
    
    def save_selection(
        self,
        session_id: str,
        units: List[Dict[str, Any]],
        selection_reason: Optional[str] = None,
        focus_unit: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Save the last selected units for a session.
        
        Args:
            session_id: Session identifier
            units: List of unit dictionaries (rows from selector)
            selection_reason: Optional reason/description of why these units were selected
            focus_unit: Optional single unit that is currently in focus
        """
        if not units:
            # Don't overwrite with empty results
            logger.debug(f"Session {session_id}: Not saving empty selection")
            return
        
        self.sessions[session_id]['last_units'] = units
        self.sessions[session_id]['last_selection_reason'] = selection_reason
        self.sessions[session_id]['focus_unit'] = focus_unit
        
        logger.info(
            f"Session {session_id}: Saved {len(units)} units to memory"
            + (f" (reason: {selection_reason})" if selection_reason else "")
        )
    
    def get_last_units(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get the last selected units for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of unit dictionaries, or empty list if none
        """
        return self.sessions.get(session_id, {}).get('last_units', [])
    
    def get_focus_unit(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the currently focused unit for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Unit dictionary or None
        """
        return self.sessions.get(session_id, {}).get('focus_unit')
    
    def get_selection_reason(self, session_id: str) -> Optional[str]:
        """
        Get the reason for the last selection.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Selection reason string or None
        """
        return self.sessions.get(session_id, {}).get('last_selection_reason')
    
    def clear_session(self, session_id: str) -> None:
        """
        Clear selector memory for a session.
        
        Args:
            session_id: Session identifier
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Cleared selector memory for session {session_id}")
    
    def get_all_sessions(self) -> List[str]:
        """Get list of all session IDs with stored memory."""
        return list(self.sessions.keys())


# Global selector memory instance
_global_selector_memory: Optional[SelectorMemory] = None


def get_selector_memory() -> SelectorMemory:
    """
    Get or create the global selector memory instance.
    
    Returns:
        SelectorMemory instance
    """
    global _global_selector_memory
    if _global_selector_memory is None:
        _global_selector_memory = SelectorMemory()
    return _global_selector_memory


def reset_selector_memory() -> None:
    """Reset the global selector memory instance (useful for testing)."""
    global _global_selector_memory
    _global_selector_memory = None

