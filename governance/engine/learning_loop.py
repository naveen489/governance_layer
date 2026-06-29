"""
Learning Loop Integration Adapter.
Responsible for emitting privacy-scrubbed governance events to the 
Learning Loop (e.g., via Kafka, RabbitMQ, or direct HTTP).
"""
import logging
from typing import Any

from governance.models.event import GovernanceEvent

logger = logging.getLogger(__name__)

def emit_to_learning_loop(event: GovernanceEvent) -> None:
    """
    Simulates emitting a privacy-scrubbed event to the Learning Loop.
    Real implementation would push to a message broker.
    """
    # Scrub sensitive data from payload
    scrubbed_payload = {}
    if event.event_payload:
        for k, v in event.event_payload.items():
            if k not in ("raw_prompt", "source_asset_url"):
                scrubbed_payload[k] = v

    message = {
        "event_id": event.id,
        "workspace_id": event.workspace_id,
        "target_type": event.target_type,
        "action": event.action,
        "reason_code": event.reason_code,
        "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
        "scrubbed_payload": scrubbed_payload,
    }
    
    # Mock emission
    logger.info(f"[Learning Loop Adapter] Emitting event: {message}")
    # e.g., kafka_producer.send("governance-events", value=message)
