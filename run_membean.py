#!/usr/bin/env python3
import argparse
import asyncio
import os
from membean import membean

def parse_args():
    parser = argparse.ArgumentParser(description='Run Membean automation in Docker')
    parser.add_argument('-e', '--email', required=True, help='Email address for login')
    parser.add_argument('-p', '--password', required=True, help='Password for login')
    parser.add_argument('-g', '--grade', required=True, choices=['A+', 'A', 'A-', 'B+', 'B', 'B-'], 
                        help='Target grade (A+, A, A-, B+, B, B-)')
    parser.add_argument('-q', '--quiz', choices=['True', 'False'], default='False',
                        help='Enable quiz mode (default: False)')
    return parser.parse_args()

async def main():
    args = parse_args()
    
    # Convert args to list format expected by membean.py
    argv = [
        '-e', args.email,
        '-p', args.password,
        '-g', args.grade,
        '-q', args.quiz
    ]
    
    try:
        await membean(argv)
    except KeyboardInterrupt:
        print("\nStopping Membean automation...")
    except Exception as e:
        print(f"Error running Membean automation: {e}")
        raise

if __name__ == '__main__':
    # Ensure we're in the correct directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    asyncio.run(main())
