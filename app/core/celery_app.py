"""
Celery stub — not used in local mode.

The app processes documents synchronously via DocumentProcessingAgent.
This module exists only so old imports don't break.
"""

# No Celery, no Redis — everything runs inline.
celery_app = None
