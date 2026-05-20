import subprocess
import psycopg2
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(os.path.expanduser('~/fundguldasta/config/.env'))

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'dbname': os.getenv('DB_NAME', 'fundguldasta_dev'),
    'user': os.getenv('DB_USER', 'fundguldasta_user'),
}

BASE_DIR = os.path.expanduser('~/fundguldasta')

PIPELINES = [
    {
        'name': 'nav_ingestion',
        'script': 'data/nav_ingestion.py',
        'description': 'AMFI daily NAV update',
        'required': True,
    },
    {
        'name': 'manager_change_detection',
        'script': 'data/manager_change_detection.py',
        'description': 'Fund manager change monitoring',
        'required': True,
    },
    {
        'name': 'manager_ingestion',
        'script': 'data/manager_ingestion.py',
        'description': 'Category and metadata enrichment',
        'required': False,
    },
]

def run_pipeline(pipeline):
    script_path = os.path.join(BASE_DIR, pipeline['script'])
    python_path = os.path.join(BASE_DIR, 'venv/bin/python3')

    print(f"\n{'='*50}")
    print(f"Running: {pipeline['description']}")
    print(f"Script:  {pipeline['script']}")
    print(f"Started: {datetime.now()}")
    print(f"{'='*50}")

    result = subprocess.run(
        [python_path, script_path],
        cwd=BASE_DIR,
        capture_output=False,
    )

    success = result.returncode == 0
    status = 'SUCCESS' if success else 'FAILED'
    print(f"\nStatus: {status}")
    return success

def get_pipeline_summary():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            pipeline_name,
            MAX(run_date) as last_run,
            status,
            records_processed
        FROM pipeline_log
        WHERE run_date = CURRENT_DATE
        GROUP BY pipeline_name, status, records_processed
        ORDER BY pipeline_name
    """)
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

def main():
    print("=" * 50)
    print("FUNDGULDASTA PIPELINE ORCHESTRATOR")
    print(f"Started: {datetime.now()}")
    print("=" * 50)

    mode = sys.argv[1] if len(sys.argv) > 1 else 'daily'

    if mode == 'daily':
        pipelines_to_run = PIPELINES
    elif mode == 'nav_only':
        pipelines_to_run = [p for p in PIPELINES if p['name'] == 'nav_ingestion']
    else:
        pipelines_to_run = PIPELINES

    results = {}
    for pipeline in pipelines_to_run:
        success = run_pipeline(pipeline)
        results[pipeline['name']] = success

        if not success and pipeline['required']:
            print(f"\nCRITICAL: Required pipeline {pipeline['name']} failed. Stopping.")
            break

    print("\n" + "=" * 50)
    print("PIPELINE RUN SUMMARY")
    print("=" * 50)
    for name, success in results.items():
        status = "✓ SUCCESS" if success else "✗ FAILED"
        print(f"  {name:<35} {status}")

    summary = get_pipeline_summary()
    if summary:
        print("\nToday's pipeline log:")
        for row in summary:
            print(f"  {row[0]:<35} {row[2]:<10} {row[3]} records")

    print(f"\nCompleted: {datetime.now()}")

if __name__ == "__main__":
    main()
