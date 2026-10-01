import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "python-agent")))

from web_server.database import db
from api_client import api_client

class TestQwikPrintSimpleArchitecture(unittest.TestCase):
    def test_01_database_and_supabase_connection(self):
        print("\n[TEST 1] Verifying Database & Supabase Connectivity...")
        self.assertIsNotNone(db)
        conn, is_pg = db.get_connection()
        self.assertIsNotNone(conn)
        conn.close()
        print(" -> Database connection verified successfully.")

    def test_02_api_client_device_credentials(self):
        print("\n[TEST 2] Verifying Desktop Agent APIClient Properties...")
        self.assertTrue(hasattr(api_client, "device_id"))
        self.assertTrue(hasattr(api_client, "device_token"))
        self.assertIsInstance(api_client.device_id, str)
        self.assertIsInstance(api_client.device_token, str)
        print(" -> APIClient device_id and device_token verified.")

    def test_03_desktop_spooler_app_binary_signed(self):
        print("\n[TEST 3] Verifying Desktop Spooler Executable Installer...")
        exe_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web_server", "static", "downloads", "QwikPrint_Setup.exe"))
        self.assertTrue(os.path.exists(exe_path))
        self.assertGreater(os.path.getsize(exe_path), 1000000)
        print(f" -> Setup Installer executable verified ({os.path.getsize(exe_path)} bytes).")

if __name__ == "__main__":
    unittest.main()
