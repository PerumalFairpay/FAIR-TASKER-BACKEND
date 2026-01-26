from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.jobs.attendance_jobs import generate_daily_attendance_records, generate_today_preplanned_records
import logging

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None

def init_scheduler():
    """
    Initialize and start the background job scheduler.
    This should be called once when the application starts.
    """
    global scheduler
    
    if scheduler is not None:
        logger.warning("Scheduler already initialized")
        return scheduler
    
    logger.info("Initializing background job scheduler")
    
    # Create AsyncIOScheduler for non-blocking execution
    scheduler = AsyncIOScheduler()
    
    # 1. Morning Job: Generate Pre-planned Attendance (Leaves & Holidays)
    # Runs at 01:02 AM
    scheduler.add_job(
        generate_today_preplanned_records,
        trigger=CronTrigger(hour=0, minute=5),
        id="daily_preplanned_attendance",
        name="Generate Pre-planned Attendance (Leaves/Holidays)",
        replace_existing=True
    )
    
    # 2. Night Job: Generate Full Attendance (Absences)
    # Runs at 23:59 PM
    scheduler.add_job(
        generate_daily_attendance_records,
        trigger=CronTrigger(hour=23, minute=59),
        id="daily_full_attendance",
        name="Generate Daily Attendance Records (Absences)",
        replace_existing=True
    )
    
    logger.info("Scheduled jobs: Pre-planned at 01:02 AM, Full generation at 23:59 PM")
    
    # Start the scheduler
    scheduler.start()
    logger.info("Background job scheduler started successfully")
    
    return scheduler


def shutdown_scheduler():
    """
    Gracefully shutdown the scheduler.
    This should be called when the application is shutting down.
    """
    global scheduler
    
    if scheduler is not None:
        logger.info("Shutting down background job scheduler")
        scheduler.shutdown(wait=True)
        scheduler = None
        logger.info("Scheduler shutdown complete")
    else:
        logger.warning("Scheduler not running, nothing to shutdown")


def get_scheduler():
    """
    Get the current scheduler instance.
    Returns None if scheduler is not initialized.
    """
    return scheduler
