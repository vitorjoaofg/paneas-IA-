"""Celery task placeholders for speech analytics.

The analytics service currently processes jobs inline using asyncio tasks.
When moving heavy workloads to Celery workers, the logic can be migrated here.
"""

from typing import Dict


def speech_analytics_task(payload: Dict) -> Dict:
    """Placeholder task for future Celery integration."""
    return payload
