"""
APScheduler setup for the Governance Layer.
Runs the retention evaluator every hour and exception expiry every 15 minutes.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

_scheduler: BackgroundScheduler | None = None


def _run_retention():
    from governance.database import SessionLocal
    from governance.engine.retention import evaluate_retention, delete_expired_assets
    db = SessionLocal()
    try:
        result = evaluate_retention(db)
        deleted = delete_expired_assets(db)
        print(f"[retention] expired assets={result['expired']} skipped={result['skipped_due_to_hold']} deleted={deleted}")
    finally:
        db.close()


def _run_exception_expiry():
    from governance.database import SessionLocal
    from governance.engine.retention import expire_exceptions
    db = SessionLocal()
    try:
        expired_exc = expire_exceptions(db)
        print(f"[exception_expiry] expired_exceptions={expired_exc}")
    finally:
        db.close()


def _run_anomaly_detection():
    from governance.database import SessionLocal
    from governance.engine.incident_engine import check_repeated_blocks, check_provider_policy_drift
    from governance.models.event import GovernanceEvent
    db = SessionLocal()
    try:
        # Get all distinct workspaces from audit events table
        workspaces = [r[0] for r in db.query(GovernanceEvent.workspace_id).distinct().all()]
        if "default" not in workspaces:
            workspaces.append("default")
            
        total_new_incidents = 0
        total_drifts = 0
        
        for ws in workspaces:
            if ws in ("system", "unknown"):
                continue
            incident = check_repeated_blocks(db, workspace_id=ws)
            drifts = check_provider_policy_drift(db, workspace_id=ws)
            
            if incident:
                total_new_incidents += 1
            total_drifts += len(drifts)
            
        print(f"[incident_engine] Anomaly scan run for workspaces {workspaces}. New incidents: {total_new_incidents}, Policy drifts: {total_drifts}")
    finally:
        db.close()


def start_scheduler():
    global _scheduler
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(_run_retention, IntervalTrigger(hours=1), id="retention_job", replace_existing=True)
    _scheduler.add_job(_run_exception_expiry, IntervalTrigger(minutes=15), id="exception_expiry_job", replace_existing=True)
    _scheduler.add_job(_run_anomaly_detection, IntervalTrigger(minutes=30), id="anomaly_detection_job", replace_existing=True)
    _scheduler.start()
    print("[scheduler] Started retention scheduler, exception expiry, and anomaly detection")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
