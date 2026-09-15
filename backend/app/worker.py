import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
from app.database import AsyncSessionLocal
from app.models import AppJob, SourceVideo, RenderedShort, GoogleDriveExport
from app.config import settings
from app.services.pipeline import (
    handle_audio_extract,
    handle_transcribe,
    handle_llm_analyze,
    handle_render,
    handle_gdrive_upload
)

logger = logging.getLogger("worker")

class BackgroundWorker:
    def __init__(self):
        self.is_running = False
        self._poll_task = None
        self._reaper_task = None
        self._transcribe_sem = asyncio.Semaphore(settings.TRANSCRIBE_CONCURRENCY)
        self._render_sem = asyncio.Semaphore(settings.RENDER_CONCURRENCY)

    def start(self):
        if not self.is_running:
            self.is_running = True
            self._poll_task = asyncio.create_task(self._poll_loop())
            self._reaper_task = asyncio.create_task(self._reaper_loop())
            logger.info("Background job worker started.")

    async def stop(self):
        self.is_running = False
        if self._poll_task:
            self._poll_task.cancel()
        if self._reaper_task:
            self._reaper_task.cancel()
        logger.info("Background job worker stopped.")

    async def _poll_loop(self):
        while self.is_running:
            try:
                job_id = await self._claim_next_job()
                if job_id:
                    asyncio.create_task(self._execute_job(job_id))
                else:
                    await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in worker poll loop: {e}")
                await asyncio.sleep(2.0)

    async def _claim_next_job(self) -> str | None:
        async with AsyncSessionLocal() as session:
            # Query oldest QUEUED job
            stmt = select(AppJob).where(AppJob.status == "QUEUED").order_by(AppJob.created_at.asc()).limit(1)
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()
            if job:
                job.status = "RUNNING"
                job.started_at = datetime.now(timezone.utc)
                job.attempts += 1
                job_id = job.id
                await session.commit()
                return job_id
        return None

    async def _execute_job(self, job_id: str):
        async with AsyncSessionLocal() as session:
            job = await session.get(AppJob, job_id)
            if not job:
                return

            try:
                if job.job_type == "AUDIO_EXTRACT":
                    await handle_audio_extract(job, session)
                elif job.job_type == "TRANSCRIBE":
                    async with self._transcribe_sem:
                        await handle_transcribe(job, session)
                elif job.job_type == "LLM_ANALYZE":
                    await handle_llm_analyze(job, session)
                elif job.job_type == "RENDER":
                    async with self._render_sem:
                        await handle_render(job, session)
                elif job.job_type == "GDRIVE_UPLOAD":
                    await handle_gdrive_upload(job, session)
                else:
                    raise ValueError(f"Unknown job type: {job.job_type}")

                job.status = "COMPLETED"
                job.progress = 100
                job.finished_at = datetime.now(timezone.utc)
                job.error_message = None
                await session.commit()

            except Exception as e:
                logger.exception(f"Job {job_id} ({job.job_type}) failed: {e}")
                err_msg = str(e)[-500:]
                job.error_message = err_msg

                if job.attempts < job.max_attempts and job.job_type not in ["AUDIO_EXTRACT", "RENDER"]:
                    # Retry
                    job.status = "QUEUED"
                else:
                    job.status = "FAILED"
                    job.finished_at = datetime.now(timezone.utc)
                    # Propagate failure to related entity
                    await self._mark_entity_failed(job, session, err_msg)

                await session.commit()

    async def _mark_entity_failed(self, job: AppJob, session, err_msg: str):
        try:
            if job.job_type in ["AUDIO_EXTRACT", "TRANSCRIBE", "LLM_ANALYZE"]:
                video = await session.get(SourceVideo, job.ref_id)
                if video:
                    video.status = "FAILED"
                    video.error_message = err_msg
            elif job.job_type == "RENDER":
                short = await session.get(RenderedShort, job.ref_id)
                if short:
                    short.render_status = "FAILED"
                    short.error_message = err_msg
            elif job.job_type == "GDRIVE_UPLOAD":
                export_rec = await session.get(GoogleDriveExport, job.ref_id)
                if export_rec:
                    export_rec.upload_status = "FAILED"
                    export_rec.error_message = err_msg
        except Exception:
            pass

    async def _reaper_loop(self):
        """Reap orphan running jobs older than 30 minutes."""
        while self.is_running:
            try:
                await asyncio.sleep(60.0)
                cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
                async with AsyncSessionLocal() as session:
                    stmt = select(AppJob).where(
                        AppJob.status == "RUNNING",
                        AppJob.started_at < cutoff
                    )
                    orphans = (await session.execute(stmt)).scalars().all()
                    for o in orphans:
                        logger.warning(f"Reaping orphan job {o.id} ({o.job_type}), resetting to QUEUED")
                        o.status = "QUEUED"
                    if orphans:
                        await session.commit()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in job reaper loop: {e}")

worker_instance = BackgroundWorker()
