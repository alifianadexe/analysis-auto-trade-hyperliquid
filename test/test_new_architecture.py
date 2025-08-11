"""
Test the new architecture - Celery tasks only
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.tasks.tracking_task import task_track_traders_batch
from app.services.tasks.leaderboard_task import task_calculate_leaderboard

def test_celery_tasks():
    """Test Celery tasks directly"""
    print("🧪 Testing Celery Tasks (without WebSocket discovery)")
    
    try:
        print("\n📊 Testing leaderboard calculation task...")
        result = task_calculate_leaderboard()
        print(f"✅ Leaderboard task completed: {result}")
        
        print("\n👥 Testing trader tracking task...")
        result = task_track_traders_batch()
        print(f"✅ Tracking task completed: {result}")
        
        print("\n✅ All Celery tasks working correctly!")
        
    except Exception as e:
        print(f"❌ Error testing tasks: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_celery_tasks()
