import os
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.config import settings
from app.utils.subprocess_utils import run_with_timeout

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("")
async def health_check(db: AsyncSession = Depends(get_db)):
    # 1. Check DB
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    # 2. Check storage writability
    storage_writable = False
    try:
        test_file = os.path.join(os.path.abspath(settings.STORAGE_ROOT), ".write_test")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        storage_writable = True
    except Exception:
        pass

    # 3. Check FFmpeg version
    ffmpeg_ver = "unknown"
    try:
        rc, stdout, _ = await run_with_timeout(["ffmpeg", "-version"], timeout_seconds=5.0)
        if rc == 0:
            first_line = stdout.splitlines()[0]
            parts = first_line.split("version")
            if len(parts) > 1:
                ffmpeg_ver = parts[1].split()[0]
    except Exception:
        pass

    return {
        "status": "ok" if (db_ok and storage_writable) else "degraded",
        "db": db_ok,
        "storage_writable": storage_writable,
        "ffmpeg": ffmpeg_ver
    }
