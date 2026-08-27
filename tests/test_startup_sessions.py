import gc
import os
import sys
import tempfile
import unittest


class _Vfs:
    translatePath = staticmethod(lambda value: value)


sys.modules.setdefault("xbmcvfs", _Vfs())

from resources.lib import database


class StartupSessionTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.previous_profile = database.PROFILE
        self.previous_db_path = database.DB_PATH
        database.PROFILE = self.tempdir.name
        database.DB_PATH = os.path.join(self.tempdir.name, "games.db")
        with database.connect() as conn:
            conn.execute(
                "INSERT INTO games (id, name, executable) VALUES ('g1', 'Example', 'game.exe')"
            )

    def tearDown(self):
        database.PROFILE = self.previous_profile
        database.DB_PATH = self.previous_db_path
        gc.collect()
        self.tempdir.cleanup()

    def test_startup_quarantines_old_pending_but_allows_new_launch(self):
        old_session = database.queue_launch("g1")

        result = database.reconcile_startup_sessions(set())

        self.assertEqual(result["watermark"], old_session)
        self.assertEqual(result["pending_quarantined"], 1)
        with database.connect() as conn:
            old = conn.execute(
                "SELECT status, error, ended_at FROM sessions WHERE id = ?",
                (old_session,),
            ).fetchone()
        self.assertEqual(old["status"], "failed")
        self.assertIn("pending when Kodi service started", old["error"])
        self.assertIsNotNone(old["ended_at"])

        new_session = database.queue_launch("g1")
        pending = database.next_pending_session(after_session_id=result["watermark"])
        self.assertEqual(pending["session_id"], new_session)
        self.assertEqual(pending["session_status"], "pending")
        with database.connect() as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT status FROM sessions WHERE id = ?", (new_session,)
                ).fetchone()["status"],
                "starting",
            )

    def test_startup_reconciles_absent_processes_idempotently(self):
        with database.connect() as conn:
            conn.execute(
                "INSERT INTO sessions (game_id, status, process_id) VALUES ('g1', 'running', 101)"
            )
            conn.execute(
                "INSERT INTO sessions (game_id, status, process_id) VALUES ('g1', 'running', 202)"
            )
            conn.execute(
                "INSERT INTO sessions (game_id, status) VALUES ('g1', 'starting')"
            )

        first = database.reconcile_startup_sessions({101})
        self.assertEqual(first["stale_reconciled"], 2)
        with database.connect() as conn:
            rows = conn.execute(
                "SELECT status, process_id, error FROM sessions ORDER BY id"
            ).fetchall()
        self.assertEqual(rows[0]["status"], "running")
        self.assertEqual(rows[1]["status"], "failed")
        self.assertIn("202", rows[1]["error"])
        self.assertEqual(rows[2]["status"], "failed")
        self.assertIn("had not recorded", rows[2]["error"])

        second = database.reconcile_startup_sessions({101})
        self.assertEqual(second["pending_quarantined"], 0)
        self.assertEqual(second["stale_reconciled"], 0)


if __name__ == "__main__":
    unittest.main()
