import os
import sys
import asyncio
import logging

sys.stdout.reconfigure(encoding='utf-8')

from app.scheduler.daily_job import execute_daily_workflow

logging.basicConfig(level=logging.INFO)

async def main():
    print("Starting manual execution of execute_daily_workflow()...")
    await execute_daily_workflow()
    print("Workflow execution finished!")

if __name__ == "__main__":
    asyncio.run(main())
