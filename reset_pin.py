#!/usr/bin/env python3
import sys
import os
import sqlite3
import secrets
from argon2 import PasswordHasher

DB_PATH = "storage/autoshorts.db"

def main():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} belum dibuat. Jalankan server terlebih dahulu.")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if len(sys.argv) > 1:
        new_pin = sys.argv[1].strip()
        if len(new_pin) < 4 or len(new_pin) > 8 or not new_pin.isdigit():
            print("❌ Error: PIN harus berupa 4 sampai 8 digit angka numerik.")
            return

        ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, hash_len=32, salt_len=16)
        p_hash = ph.hash(new_pin)
        salt = secrets.token_hex(16)

        c.execute("DELETE FROM auth_pin")
        c.execute("INSERT INTO auth_pin (pin_hash, salt, is_active) VALUES (?, ?, 1)", (p_hash, salt))
        conn.commit()
        print(f"✅ PIN berhasil diubah menjadi: {new_pin}")
    else:
        c.execute("DELETE FROM auth_pin")
        conn.commit()
        print("✅ PIN berhasil di-reset!")
        print("👉 Silakan buka atau refresh Web UI (http://localhost:3000) untuk membuat PIN baru Anda.")

if __name__ == "__main__":
    main()
