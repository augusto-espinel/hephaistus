"""
HistoryStore — SQLite-backed searchable conversation history.

Phase 3.3: Persistent storage for Layer 2 context (Deep History).
"""

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from contextlib import contextmanager


@dataclass
class HistoryEntryRecord:
    """Database record for a history entry."""
    
    id: str
    session_id: str
    timestamp: datetime
    user_request: str
    user_context: Optional[str]
    llm_response: str
    reasoning_summary: str
    patch_plan_json: Optional[str]
    validation_result: Optional[str]
    validation_json: Optional[str]
    user_action: Optional[str]
    user_feedback: Optional[str]
    context_tokens: int
    response_tokens: int
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "user_request": self.user_request,
            "reasoning_summary": self.reasoning_summary,
            "user_action": self.user_action,
        }


@dataclass 
class SearchResult:
    """Result from history search."""
    
    entry: HistoryEntryRecord
    relevance_score: float
    match_type: str  # "request", "response", "reasoning"
    matched_text: str


class HistoryStore:
    """
    SQLite-backed storage for conversation history.
    
    Provides:
    - Persistent storage across sessions
    - Full-text search (FTS5)
    - Time-range queries
    - Statistics and analytics
    """
    
    SCHEMA_VERSION = 1
    
    def __init__(self, db_path: str = ".hephaistus/history.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    @contextmanager
    def _connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._connection() as conn:
            cursor = conn.cursor()
            
            # Metadata table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            
            # Check schema version
            cursor.execute("SELECT value FROM metadata WHERE key = 'schema_version'")
            row = cursor.fetchone()
            if row and int(row[0]) >= self.SCHEMA_VERSION:
                return
            
            # Main entries table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history_entries (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    user_request TEXT NOT NULL,
                    user_context TEXT,
                    llm_response TEXT NOT NULL,
                    reasoning_summary TEXT,
                    patch_plan_json TEXT,
                    validation_result TEXT,
                    validation_json TEXT,
                    user_action TEXT,
                    user_feedback TEXT,
                    context_tokens INTEGER DEFAULT 0,
                    response_tokens INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_id 
                ON history_entries(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON history_entries(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_action 
                ON history_entries(user_action)
            """)
            
            # Full-text search
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS history_fts 
                USING fts5(
                    id,
                    user_request,
                    llm_response,
                    reasoning_summary,
                    content='history_entries',
                    content_rowid='rowid'
                )
            """)
            
            # Triggers to keep FTS in sync
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS history_ai 
                AFTER INSERT ON history_entries BEGIN
                    INSERT INTO history_fts (
                        id, user_request, llm_response, reasoning_summary
                    ) VALUES (
                        NEW.id, NEW.user_request, NEW.llm_response, NEW.reasoning_summary
                    );
                END
            """)
            
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS history_ad 
                AFTER DELETE ON history_entries BEGIN
                    INSERT INTO history_fts (
                        history_fts, id, user_request, llm_response, reasoning_summary
                    ) VALUES (
                        'delete', OLD.id, OLD.user_request, OLD.llm_response, OLD.reasoning_summary
                    );
                END
            """)
            
            # Update schema version
            cursor.execute("""
                INSERT OR REPLACE INTO metadata (key, value) 
                VALUES ('schema_version', ?)
            """, (str(self.SCHEMA_VERSION),))
    
    def add_entry(self, record: HistoryEntryRecord) -> None:
        """Add a history entry to the database."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO history_entries (
                    id, session_id, timestamp,
                    user_request, user_context,
                    llm_response, reasoning_summary,
                    patch_plan_json, validation_result, validation_json,
                    user_action, user_feedback,
                    context_tokens, response_tokens
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.id,
                record.session_id,
                record.timestamp.isoformat(),
                record.user_request,
                record.user_context,
                record.llm_response,
                record.reasoning_summary,
                record.patch_plan_json,
                record.validation_result,
                record.validation_json,
                record.user_action,
                record.user_feedback,
                record.context_tokens,
                record.response_tokens,
            ))
    
    def get_entry(self, entry_id: str) -> Optional[HistoryEntryRecord]:
        """Retrieve a specific entry by ID."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM history_entries WHERE id = ?", (entry_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_record(row)
            return None
    
    def search(
        self, 
        query: str, 
        limit: int = 10,
        session_id: Optional[str] = None,
    ) -> List[SearchResult]:
        """
        Full-text search across history.
        
        Args:
            query: Search query (FTS5 syntax supported)
            limit: Maximum results
            session_id: Filter to specific session
            
        Returns:
            List of SearchResult objects with relevance scores
        """
        with self._connection() as conn:
            cursor = conn.cursor()
            
            # Escape query for FTS5
            fts_query = query.replace("'", "''")
            
            if session_id:
                cursor.execute("""
                    SELECT 
                        e.*,
                        bm25(history_fts) as score
                    FROM history_fts f
                    JOIN history_entries e ON f.id = e.id
                    WHERE history_fts MATCH ?
                    AND e.session_id = ?
                    ORDER BY score ASC
                    LIMIT ?
                """, (fts_query, session_id, limit))
            else:
                cursor.execute("""
                    SELECT 
                        e.*,
                        bm25(history_fts) as score
                    FROM history_fts f
                    JOIN history_entries e ON f.id = e.id
                    WHERE history_fts MATCH ?
                    ORDER BY score ASC
                    LIMIT ?
                """, (fts_query, limit))
            
            results = []
            for row in cursor.fetchall():
                record = self._row_to_record(row)
                # Determine match type
                query_lower = query.lower()
                match_type = "request"
                if query_lower in (record.llm_response or "").lower():
                    match_type = "response"
                elif query_lower in (record.reasoning_summary or "").lower():
                    match_type = "reasoning"
                
                results.append(SearchResult(
                    entry=record,
                    relevance_score=abs(row["score"]) if row["score"] else 0,
                    match_type=match_type,
                    matched_text=query,
                ))
            
            return results
    
    def get_by_session(
        self, 
        session_id: str,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[HistoryEntryRecord]:
        """Get all entries for a session, ordered by time."""
        with self._connection() as conn:
            cursor = conn.cursor()
            
            if limit:
                cursor.execute("""
                    SELECT * FROM history_entries 
                    WHERE session_id = ?
                    ORDER BY timestamp ASC
                    LIMIT ? OFFSET ?
                """, (session_id, limit, offset))
            else:
                cursor.execute("""
                    SELECT * FROM history_entries 
                    WHERE session_id = ?
                    ORDER BY timestamp ASC
                """, (session_id,))
            
            return [self._row_to_record(row) for row in cursor.fetchall()]
    
    def get_recent(
        self,
        limit: int = 20,
        session_id: Optional[str] = None,
    ) -> List[HistoryEntryRecord]:
        """Get most recent entries."""
        with self._connection() as conn:
            cursor = conn.cursor()
            
            if session_id:
                cursor.execute("""
                    SELECT * FROM history_entries 
                    WHERE session_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (session_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM history_entries 
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))
            
            return [self._row_to_record(row) for row in cursor.fetchall()]
    
    def get_by_time_range(
        self,
        start: datetime,
        end: datetime,
        session_id: Optional[str] = None,
    ) -> List[HistoryEntryRecord]:
        """Get entries within a time range."""
        with self._connection() as conn:
            cursor = conn.cursor()
            
            if session_id:
                cursor.execute("""
                    SELECT * FROM history_entries 
                    WHERE timestamp BETWEEN ? AND ?
                    AND session_id = ?
                    ORDER BY timestamp ASC
                """, (start.isoformat(), end.isoformat(), session_id))
            else:
                cursor.execute("""
                    SELECT * FROM history_entries 
                    WHERE timestamp BETWEEN ? AND ?
                    ORDER BY timestamp ASC
                """, (start.isoformat(), end.isoformat()))
            
            return [self._row_to_record(row) for row in cursor.fetchall()]
    
    def get_statistics(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics about stored history."""
        with self._connection() as conn:
            cursor = conn.cursor()
            
            if session_id:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_entries,
                        SUM(context_tokens) as total_context_tokens,
                        SUM(response_tokens) as total_response_tokens,
                        COUNT(CASE WHEN user_action = 'accepted' THEN 1 END) as accepted_count,
                        COUNT(CASE WHEN user_action = 'rejected' THEN 1 END) as rejected_count,
                        MIN(timestamp) as first_entry,
                        MAX(timestamp) as last_entry
                    FROM history_entries
                    WHERE session_id = ?
                """, (session_id,))
            else:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_entries,
                        SUM(context_tokens) as total_context_tokens,
                        SUM(response_tokens) as total_response_tokens,
                        COUNT(CASE WHEN user_action = 'accepted' THEN 1 END) as accepted_count,
                        COUNT(CASE WHEN user_action = 'rejected' THEN 1 END) as rejected_count,
                        MIN(timestamp) as first_entry,
                        MAX(timestamp) as last_entry
                    FROM history_entries
                """)
            
            row = cursor.fetchone()
            return dict(row) if row else {}
    
    def delete_entry(self, entry_id: str) -> bool:
        """Delete a specific entry."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM history_entries WHERE id = ?", (entry_id,))
            return cursor.rowcount > 0
    
    def delete_session(self, session_id: str) -> int:
        """Delete all entries for a session."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM history_entries WHERE session_id = ?", 
                (session_id,)
            )
            return cursor.rowcount

    def clear_all(self) -> int:
        """Delete all history entries for this project."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM history_entries")
            return cursor.rowcount
    
    def _row_to_record(self, row: sqlite3.Row) -> HistoryEntryRecord:
        """Convert database row to HistoryEntryRecord."""
        return HistoryEntryRecord(
            id=row["id"],
            session_id=row["session_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            user_request=row["user_request"],
            user_context=row["user_context"],
            llm_response=row["llm_response"],
            reasoning_summary=row["reasoning_summary"],
            patch_plan_json=row["patch_plan_json"],
            validation_result=row["validation_result"],
            validation_json=row["validation_json"],
            user_action=row["user_action"],
            user_feedback=row["user_feedback"],
            context_tokens=row["context_tokens"],
            response_tokens=row["response_tokens"],
        )