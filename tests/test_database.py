import tempfile
import unittest
from pathlib import Path

from database import Database


class DatabaseTests(unittest.TestCase):
    def test_subscription_and_request(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Database(str(Path(directory) / "test.db"))
            db.initialize()
            db.set_subscription(123, True)
            request_id = db.add_request(123, "Карточки по теме EVDE")
            rows = db.list_user_requests(123)

            self.assertEqual(request_id, 1)
            self.assertEqual(rows[0]["text"], "Карточки по теме EVDE")
            subscribed = db.connection.execute(
                "SELECT subscribed FROM users WHERE vk_id=123"
            ).fetchone()[0]
            self.assertEqual(subscribed, 1)


if __name__ == "__main__":
    unittest.main()

