from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.jobs.attendance_jobs import (
    generate_daily_attendance_records,
    generate_today_preplanned_records,
    generate_night_shift_attendance_records,
    process_unauthorized_absences,
    process_uncompensated_permissions
)
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
    # Runs at 06:35 PM UTC (12:05 AM IST)
    scheduler.add_job(
        generate_today_preplanned_records,
        trigger=CronTrigger(hour=18, minute=35),
        id="daily_preplanned_attendance",
        name="Generate Pre-planned Attendance (Leaves/Holidays)",
        replace_existing=True
    )
    
    # 2. Night Job: Generate Full Attendance (Absences)
    # Runs at 06:27 PM UTC (11:57 PM IST)
    scheduler.add_job(
        generate_daily_attendance_records,
        trigger=CronTrigger(hour=18, minute=27),
        id="daily_full_attendance",
        name="Generate Daily Attendance Records (Absences)",
        replace_existing=True
    )
    
    # 3. Night Shift Job: Generate Full Attendance for Night Shift (Mark Absent for Previous Night)
    # Runs at 02:30 AM UTC (08:00 AM IST)
    scheduler.add_job(
        generate_night_shift_attendance_records,
        trigger=CronTrigger(hour=2, minute=30),
        id="night_shift_full_attendance",
        name="Generate Night Shift Attendance (Absences)",
        replace_existing=True
    )
    
    # 4. Daily Job: Process Unauthorized Absences (2 consecutive days -> LOP)
    # Runs at 03:30 AM UTC (09:00 AM IST) to catch both Day and Night shift records
    scheduler.add_job(
        process_unauthorized_absences,
        trigger=CronTrigger(hour=3, minute=30),
        id="process_unauthorized_absences",
        name="Process Unauthorized Absences to LOP",
        replace_existing=True
    )
    
    # 5. Monthly Job: Process Uncompensated Permissions
    # Runs on the 1st of every month at 01:00 AM UTC (06:30 AM IST)
    scheduler.add_job(
        process_uncompensated_permissions,
        trigger=CronTrigger(day=1, hour=1, minute=0),
        id="process_uncompensated_permissions",
        name="Convert Uncompensated Permissions to LOP",
        replace_existing=True
    )
    
    logger.info("Scheduled all jobs successfully")
    
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
