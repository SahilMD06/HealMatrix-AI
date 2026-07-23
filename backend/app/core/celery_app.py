"""Celery application and periodic schedule.

Long-running or recurring work (simulation ticks, nightly forecasts, PDF rendering,
FAISS refresh) runs here so API requests stay fast.
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "healmatrix",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    # Only modules that exist are listed. Celery imports every entry at worker
    # start, so naming a not-yet-written module crashes the worker on boot.
    # Phase 5 adds app.reports.tasks, registered here once it lands.
    include=[
        "app.simulator.tasks",
        "app.agents.tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,
    task_soft_time_limit=540,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_retry_delay=30,
    task_max_retries=3,
    result_expires=3600,
    # Keep a transient broker outage from crashing the worker/beat process. It
    # retries the connection instead of exiting, so a slow Redis start no longer
    # takes the whole stack down.
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=None,
    # The simulator tick is fire-and-forget; it does not need a stored result,
    # and not storing one removes beat's dependency on the result backend.
    task_ignore_result=True,
)

celery_app.conf.beat_schedule = {
    "simulator-tick": {
        "task": "app.simulator.tasks.run_simulation_tick",
        "schedule": float(settings.simulator_tick_seconds),
        "options": {"expires": settings.simulator_tick_seconds},
    },
    # Runs the disease-forecast/medicine/energy/water/waste/carbon/executive agent
    # chain for every active hospital. Every agent it invokes has a real fallback
    # with zero external dependencies, so this stays useful even with no
    # requirements-ai.txt installed and no GOOGLE_API_KEY configured — the
    # executive synthesis just runs the deterministic ranking instead of the
    # CrewAI path in that case (see app/agents/crews/executive_crew.py).
    "agents-scheduled-cycle": {
        "task": "app.agents.tasks.run_scheduled_cycle",
        "schedule": 3600.0,  # hourly; the underlying data (admissions, energy, water) is itself hourly-granular
        "options": {"expires": 3300},
    },
    # Scheduled entries for the RAG and report tasks are added alongside their
    # task modules in Phase 5. Beat fails fast on a schedule that points at an
    # unregistered task, so the schedule tracks reality.
}
