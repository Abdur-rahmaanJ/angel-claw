import unittest
from unittest.mock import MagicMock, patch, patch
from datetime import datetime, UTC
from angel_claw.models import UserContext, Message, Role
from angel_claw.runtime.persistence import PersistentHistory

class TestPostgresPersistence(unittest.TestCase):
    @patch('sqlalchemy.create_engine')
    @patch('angel_claw.config.settings')
    def test_init_db_postgres(self, mock_settings, mock_create_engine):
        # Setup mocks
        mock_settings.history_database_uri = "postgresql://user:pass@localhost/db"
        
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        
        ctx = UserContext(user_id="user123", email="u@e.com", roles=[], channel_type="t", channel_identifier="s")
        
        # Initialize (should trigger _init_db)
        history = PersistentHistory(ctx)
        
        # Verify sqlalchemy was used
        mock_create_engine.assert_called_with("postgresql://user:pass@localhost/db")
        # Check that CREATE TABLE was called (at least once)
        found = False
        for call in mock_conn.execute.call_args_list:
            sql = str(call[0][0])
            if "CREATE TABLE IF NOT EXISTS history" in sql:
                found = True
                break
        self.assertTrue(found)

    @patch('sqlalchemy.create_engine')
    @patch('angel_claw.config.settings')
    def test_add_message_postgres(self, mock_settings, mock_create_engine):
        mock_settings.history_database_uri = "postgresql://user:pass@localhost/db"
        
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        mock_conn = mock_engine.connect.return_value.__enter__.return_value
        
        ctx = UserContext(user_id="user123", email="u@e.com", roles=[], channel_type="t", channel_identifier="s")
        history = PersistentHistory(ctx)
        
        msg = Message(role=Role.USER, content="Hello")
        history.add_message("session_abc", msg)
        
        # Verify INSERT call
        found = False
        for call in mock_conn.execute.call_args_list:
            sql = str(call[0][0])
            if "INSERT INTO history" in sql:
                found = True
                break
        self.assertTrue(found)

if __name__ == "__main__":
    unittest.main()
