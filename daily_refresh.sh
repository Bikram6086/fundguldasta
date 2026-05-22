#!/bin/bash
# FundGuldasta daily NAV and bouquet cache refresh
# Scheduled: weekdays 11:00 PM IST (17:30 UTC)

LOG=/tmp/fundguldasta_daily.log
echo "" >> $LOG
echo "==============================" >> $LOG
echo "Daily refresh started: $(date '+%Y-%m-%d %H:%M:%S')" >> $LOG

cd /home/hpbikram6086/fundguldasta
source venv/bin/activate

echo "Step 1: NAV ingestion..." >> $LOG
python3 data/nav_ingestion.py >> $LOG 2>&1 && echo "NAV OK" >> $LOG || echo "NAV FAILED" >> $LOG

echo "Step 2: Benchmark ingestion..." >> $LOG
python3 data/benchmark_ingestion.py >> $LOG 2>&1 && echo "Benchmark OK" >> $LOG || echo "Benchmark FAILED" >> $LOG

echo "Step 3: Bouquet cache (all horizons)..." >> $LOG
python3 data/run_precompute_all.py >> $LOG 2>&1 && echo "Precompute OK" >> $LOG || echo "Precompute FAILED" >> $LOG

# Weekly pipelines — run only on Monday (day of week = 1)
DOW=$(date +%u)
if [ "$DOW" = "1" ]; then
    echo "Step 4 (Monday): AMFI scheme master..." >> $LOG
    python3 data/amfi_scheme_master.py >> $LOG 2>&1 && echo "Scheme master OK" >> $LOG || echo "Scheme master FAILED" >> $LOG

    echo "Step 5 (Monday): Manager change detection..." >> $LOG
    python3 data/manager_change_detection.py >> $LOG 2>&1 && echo "Manager detection OK" >> $LOG || echo "Manager detection FAILED" >> $LOG

    echo "Step 6 (Monday): Manager ingestion..." >> $LOG
    python3 data/manager_ingestion.py >> $LOG 2>&1 && echo "Manager ingestion OK" >> $LOG || echo "Manager ingestion FAILED" >> $LOG
fi

echo "Daily refresh complete: $(date '+%Y-%m-%d %H:%M:%S')" >> $LOG
echo "==============================" >> $LOG
