#!/usr/bin/env python3
"""
Master Test Runner for All Tasks
Runs comprehensive tests for Discovery, Tracking, and Leaderboard tasks
"""
import sys
import os
import asyncio
import logging
import time
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def run_test_file(test_file, test_name):
    """Run a specific test file"""
    logger.info(f"🧪 STARTING {test_name.upper()} TESTS")
    logger.info("="*60)
    
    start_time = time.time()
    
    try:
        # Import and run the test
        if test_file == "discovery":
            from test_discovery_complete import main as discovery_main
            await discovery_main()
        elif test_file == "tracking":
            from test_tracking_complete import main as tracking_main
            await tracking_main()
        elif test_file == "leaderboard":
            from test_leaderboard_complete import main as leaderboard_main
            await leaderboard_main()
        
        end_time = time.time()
        duration = end_time - start_time
        
        logger.info("="*60)
        logger.info(f"✅ {test_name.upper()} TESTS COMPLETED in {duration:.1f} seconds")
        return True
        
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        
        logger.error("="*60)
        logger.error(f"❌ {test_name.upper()} TESTS FAILED after {duration:.1f} seconds")
        logger.error(f"Error: {e}")
        return False

async def run_system_health_check():
    """Run basic system health checks"""
    logger.info("🏥 RUNNING SYSTEM HEALTH CHECKS")
    logger.info("="*60)
    
    try:
        # Check database connection
        from app.database.database import SessionLocal
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        logger.info("✅ Database connection: OK")
        
        # Check Celery broker connection
        try:
            from app.services.celery_app import celery_app
            # This will raise an exception if broker is not available
            inspect = celery_app.control.inspect()
            stats = inspect.stats()
            if stats:
                logger.info("✅ Celery broker connection: OK")
            else:
                logger.warning("⚠️ Celery broker: No workers found")
        except Exception as e:
            logger.warning(f"⚠️ Celery broker check failed: {e}")
        
        # Check Hyperliquid API
        try:
            from app.services.hyperliquid_client import hyperliquid_client
            meta = await hyperliquid_client.get_perp_meta()
            if meta:
                logger.info("✅ Hyperliquid API connection: OK")
            else:
                logger.warning("⚠️ Hyperliquid API: No response")
        except Exception as e:
            logger.warning(f"⚠️ Hyperliquid API check failed: {e}")
        
        # Check Redis connection (if used)
        try:
            from app.core.config import settings
            if hasattr(settings, 'REDIS_URL'):
                import redis
                r = redis.from_url(settings.REDIS_URL)
                r.ping()
                logger.info("✅ Redis connection: OK")
        except Exception as e:
            logger.warning(f"⚠️ Redis check failed: {e}")
        
        logger.info("="*60)
        logger.info("🏥 HEALTH CHECK COMPLETED")
        return True
        
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        return False

def print_test_summary(results):
    """Print a summary of all test results"""
    logger.info("\n" + "="*60)
    logger.info("📊 TEST EXECUTION SUMMARY")
    logger.info("="*60)
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    failed_tests = total_tests - passed_tests
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name.ljust(20)}: {status}")
    
    logger.info("="*60)
    logger.info(f"Total Tests: {total_tests}")
    logger.info(f"Passed: {passed_tests}")
    logger.info(f"Failed: {failed_tests}")
    logger.info(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    if failed_tests == 0:
        logger.info("🎉 ALL TESTS PASSED!")
    else:
        logger.error(f"⚠️ {failed_tests} TEST(S) FAILED")
    
    return failed_tests == 0

async def main():
    """Run all tests in sequence"""
    start_time = datetime.utcnow()
    logger.info("🚀 STARTING COMPREHENSIVE TASK TESTING")
    logger.info(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    logger.info("="*60)
    
    results = {}
    
    # Run health check first
    health_ok = await run_system_health_check()
    results["Health Check"] = health_ok
    
    if not health_ok:
        logger.warning("⚠️ Some health checks failed, but continuing with tests...")
    
    # Add separator between health check and tests
    logger.info("\n" + "🧪 STARTING TASK-SPECIFIC TESTS" + "\n")
    
    # Run each test suite
    test_suites = [
        ("discovery", "Discovery Task"),
        ("tracking", "Tracking Task"), 
        ("leaderboard", "Leaderboard Task")
    ]
    
    for test_file, test_name in test_suites:
        try:
            result = await run_test_file(test_file, test_name)
            results[test_name] = result
            
            # Add a pause between test suites
            if test_file != "leaderboard":  # Don't pause after the last test
                logger.info(f"\n⏸️ Pausing 5 seconds before next test suite...\n")
                await asyncio.sleep(5)
                
        except Exception as e:
            logger.error(f"❌ Failed to run {test_name} tests: {e}")
            results[test_name] = False
    
    # Print final summary
    end_time = datetime.utcnow()
    total_duration = (end_time - start_time).total_seconds()
    
    logger.info(f"\n⏰ Total test duration: {total_duration:.1f} seconds")
    logger.info(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    success = print_test_summary(results)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())
