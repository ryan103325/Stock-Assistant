import sys
import os
import argparse

# Import modules
from run_day import main as run_day_main
from run_night import main as run_night_main
from run_weekly import main as run_weekly_main

def main():
    parser = argparse.ArgumentParser(description="Stock Scheduler CLI Bridge")
    parser.add_argument('--daily', action='store_true', help='Run Daily Routine (Afternoon)')
    parser.add_argument('--report', action='store_true', help='Run Night Routine (Report)')
    parser.add_argument('--weekly', action='store_true', help='Run Weekly Maintenance')
    parser.add_argument('--force', action='store_true', help='Force run regardless of trading day check')
    
    args = parser.parse_args()
    
    # Check for arguments
    if args.daily:
        print(f"bridge: Calling run_day.py (Force={args.force})...")
        run_day_main(force=args.force)
        
    if args.report:
        print(f"bridge: Calling run_night.py (Force={args.force})...")
        run_night_main(force=args.force)

    if args.weekly:
        print(f"bridge: Calling run_weekly.py (Force={args.force})...")
        run_weekly_main(force=args.force)
        
    if not args.daily and not args.report and not args.weekly:
        print("Usage: python scheduler.py [--daily] [--report] [--weekly]")

if __name__ == "__main__":
    main()
