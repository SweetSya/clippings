"""Regresi QueuePool exhaustion di worker poll loop.

Setiap _execute_job menahan 1 sesi/koneksi selama handler berjalan
(render & vision pass bisa bermenit-menit). Dengan QueuePool default
(size 5 + overflow 10), klaim koneksi poll loop timeout 30s.
SQLite harus pakai NullPool + busy timeout.
"""

from sqlalchemy.pool import NullPool
from app.database import build_engine_kwargs


def test_sqlite_uses_null_pool_with_busy_timeout():
    kwargs = build_engine_kwargs("sqlite+aiosqlite:///./storage/autoshorts.db")
    assert kwargs["poolclass"] is NullPool
    assert kwargs["connect_args"]["check_same_thread"] is False
    assert kwargs["connect_args"]["timeout"] >= 30


def test_non_sqlite_keeps_pooled_settings():
    kwargs = build_engine_kwargs("mysql+aiomysql://u:p@host/db")
    assert "poolclass" not in kwargs
    assert kwargs["pool_pre_ping"] is True
    assert kwargs["pool_recycle"] == 3600
