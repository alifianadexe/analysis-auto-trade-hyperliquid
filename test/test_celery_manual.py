#!/usr/bin/env python3
"""
Manual Celery Task Test
Test the discovery task directly through Celery
"""
import sys
import os
import logging

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)
logger = logging.getLogger(__name__)

def test_celery_task():
    """Test discovery task via Celery"""
    logger.info("🧪 Testing discovery task via Celery")
    
    try:
        from app.services.tasks.discovery_task import task_manage_discovery_stream
        
        # Test 1: Direct function call (should work)
        logger.info("Test 1: Direct function call")
        task_manage_discovery_stream()
        
        # Test 2: Celery delay (if worker is running)
        # logger.info("Test 2: Celery delay (async)")
        # result = task_manage_discovery_stream.delay()
        # logger.info(f"Task ID: {result.id}")
        
    except Exception as e:
        logger.error(f"❌ Error testing Celery task: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    test_celery_task()
