import sqlite3

class DiscordDatabaseManager:
    """Database manager for Discord data - matching your schema"""
    
    def __init__(self, db_name, db_channel_name):
        """Initialize the database connection and create tables."""
        self.db_name = db_name
        self.db_channel_name = db_channel_name
        self.conn = None
        self.cursor = None
        self.connect()
        self.create_tables()
    
    def connect(self):
        try:
            self.conn = sqlite3.connect(self.db_name)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            print(f"✓ Connected to database: {self.db_name}")
        except Exception as e:
            print(f"✗ Error connecting to database: {e}")
    
    def create_tables(self):
        try:
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS servers (
                    data_id TEXT PRIMARY KEY,
                    data_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data_announcement TEXT
                )
            ''')
            self.conn.commit()
            print("✓ Tables created or already exist.")
        except Exception as e:
            print(f"✗ Error creating tables: {e}")
    
    def add_announcements_batch(self, announcements):
      try:
          self.cursor.executemany('''
              INSERT OR REPLACE INTO servers (data_id, data_date, data_announcement)
              VALUES (?, ?, ?)
          ''', announcements)  # Insert all at once!
          self.conn.commit()
          return True
      except Exception as e:
          print(f"✗ Error in batch insert: {e}")
          return False
    
    def get_announcement_count(self, date_from=None):
        """Get count of announcements, optionally filtered by date"""
        try:
            if date_from:
                self.cursor.execute('''
                    SELECT COUNT(*) as count FROM servers
                    WHERE data_date >= ?
                ''', (date_from,))
            else:
                self.cursor.execute('SELECT COUNT(*) as count FROM servers')
            
            result = self.cursor.fetchone()
            return result['count'] if result else 0
        except Exception as e:
            print(f"✗ Error getting count: {e}")
            return 0
    
    def get_recent_announcements(self, limit=10):
        """Get recent announcements"""
        try:
            self.cursor.execute('''
                SELECT * FROM servers
                ORDER BY data_date DESC
                LIMIT ?
            ''', (limit,))
            return self.cursor.fetchall()
        except Exception as e:
            print(f"✗ Error getting announcements: {e}")
            return []
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            print(f"✓ Database connection closed: {self.db_name}")
