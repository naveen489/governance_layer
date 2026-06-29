"""
APScheduler setup for the Governance Layer.
Runs the retention evaluator every hour and exception expiry every 15 minutes.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

_scheduler: BackgroundScheduler | None = None


def _run_retention():
    from governance.database import SessionLocal
    from governance.engine.retention import evaluate_retention, expire_exceptions, delete_expired_assets
    db = SessionLocal()
    try:
        result = evaluate_retention(db)
        expired_exc = expire_exceptions(db)
        deleted = delete_expired_assets(db)
        print(f"[retention] expired assets={result['expired']} skipped={result['skipped_due_to_hold']} expired_exceptions={expired_exc} deleted={deleted}")
    finally:
        db.close()


def _run_anomaly_detection():
    from governance.database import SessionLocal
    from governance.engine.incident_engine import check_repeated_blocks, check_provider_policy_drift
    db = SessionLocal()
    try:
        # Defaulting to "default" workspace for MVP simulation
        incident = check_repeated_blocks(db, workspace_id="default")
        drifts = check_provider_policy_drift(db, workspace_id="default")
        print(f"[incident_engine] Anomaly scan run. New incidents: {1 if incident else 0}, Policy drifts: {len(drifts)}")
    finally:
        db.close()


def start_scheduler():
    global _scheduler
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(_run_retention, IntervalTrigger(hours=1), id="retention_job", replace_existing=True)
    _scheduler.add_job(_run_retention, IntervalTrigger(minutes=15), id="exception_expiry_job", replace_existing=True)
    _scheduler.add_job(_run_anomaly_detection, IntervalTrigger(minutes=30), id="anomaly_detection_job", replace_existing=True)
    _scheduler.start()
    print("[scheduler] Started retention scheduler and anomaly detection")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
