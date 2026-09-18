"""Phase 4 — 7.1: verifikasi parallel render workers (implementasi sudah ada)."""

import asyncio
import uuid
import pytest
import app.database as db_module
from app.models import AppJob
from app.worker import BackgroundWorker


def test_semaphore_defaults_from_settings():
    from app.config import settings
    w = BackgroundWorker()
    assert settings.RENDER_CONCURRENCY == 2
    assert settings.TRANSCRIBE_CONCURRENCY == 1
    assert w._render_sem._value == 2
    assert w._transcribe_sem._value == 1


@pytest.mark.asyncio
async def test_render_jobs_bounded_parallel(monkeypatch):
    import app.worker as worker_mod

    active = 0
    peak = 0

    async def fake_render(job, session):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.2)
        active -= 1

    monkeypatch.setattr(worker_mod, "handle_render", fake_render)
    w = BackgroundWorker()

    job_ids = []
    async with db_module.AsyncSessionLocal() as session:
        for _ in range(3):
            jid = uuid.uuid4().hex
            session.add(AppJob(id=jid, job_type="RENDER", ref_id="x", status="QUEUED"))
            job_ids.append(jid)
        await session.commit()

    await asyncio.gather(*[w._execute_job(jid) for jid in job_ids])

    # 3 job × 0.2s dengan batas 2 → paralel terbatas (peak 2), bukan serial (peak 1)
    assert peak == 2

    async with db_module.AsyncSessionLocal() as session:
        for jid in job_ids:
            job = await session.get(AppJob, jid)
            assert job.status == "COMPLETED"
            await session.delete(job)
        await session.commit()
