from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def executescript(self, script: str) -> None:
        with self.connect() as connection:
            connection.executescript(script)

    def execute(self, query: str, params: Iterable[object] = ()) -> sqlite3.Cursor:
        with self.connect() as connection:
            cursor = connection.execute(query, tuple(params))
            connection.commit()
            return cursor

