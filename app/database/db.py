import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, List
from .models import Message, Conversation

class Database:
    def __init__(self, db_path: str = "conversations.db"):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES
        )
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    started_at timestamp NOT NULL,
                    last_message_at timestamp,
                    total_messages INTEGER DEFAULT 0
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations (id)
                )
            ''')
            conn.commit()

    def save_conversation(self, conversation: Conversation, new_message: Optional[Message] = None):
        with self.get_connection() as conn:
            c = conn.cursor()
            
            c.execute('''
                INSERT OR REPLACE INTO conversations (id, started_at, last_message_at, total_messages)
                VALUES (?, ?, ?, ?)
            ''', (
                conversation.id,
                conversation.started_at,
                conversation.last_message_at or datetime.utcnow(),
                conversation.total_messages
            ))
            
            if new_message:
                c.execute('''
                    INSERT INTO messages (conversation_id, role, content, timestamp)
                    VALUES (?, ?, ?, ?)
                ''', (
                    conversation.id,
                    new_message.role,
                    new_message.content,
                    new_message.timestamp
                ))
            
            conn.commit()

    def load_conversation(self, chat_id: str) -> Optional[Conversation]:
        with self.get_connection() as conn:
            c = conn.cursor()
            
            c.execute('''
                SELECT id, started_at as "started_at [timestamp]", 
                       last_message_at as "last_message_at [timestamp]", 
                       total_messages 
                FROM conversations WHERE id = ?
            ''', (chat_id,))
            conv_row = c.fetchone()
            
            if not conv_row:
                return None
            
            c.execute('''
                SELECT role, content, timestamp as "timestamp [timestamp]" 
                FROM messages 
                WHERE conversation_id = ? 
                ORDER BY timestamp
            ''', (chat_id,))
            
            messages = [
                Message(
                    role=row[0],
                    content=row[1],
                    timestamp=row[2] or datetime.utcnow()
                )
                for row in c.fetchall()
            ]
            
            return Conversation(
                id=conv_row[0],
                started_at=conv_row[1] or datetime.utcnow(),
                last_message_at=conv_row[2],
                total_messages=conv_row[3],
                messages=messages
            ) 

    def clear(self, chat_id: str):
        """Delete all messages for a given conversation ID."""
        with self.get_connection() as conn:
            c = conn.cursor()
            
            # Delete all messages for this conversation
            c.execute('DELETE FROM messages WHERE conversation_id = ?', (chat_id,))
            
            # Reset the total_messages count
            c.execute('''
                UPDATE conversations 
                SET total_messages = 0,
                    last_message_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (chat_id,))
            
            conn.commit() 