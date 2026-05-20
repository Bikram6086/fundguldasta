-- FUNDGULDASTA DATABASE SCHEMA
-- Run with: psql -h localhost -U fundguldasta_user -d fundguldasta_dev -f schema.sql

CREATE TABLE IF NOT EXISTS fund_metadata (
    scheme_code VARCHAR(20) PRIMARY KEY,
    scheme_name VARCHAR(300) NOT NULL,
    amc_name VARCHAR(150) NOT NULL,
    sebi_category VARCHAR(100),
    sebi_sub_category VARCHAR(100),
    inception_date DATE,
    benchmark_index VARCHAR(150),
    plan_type VARCHAR(20) CHECK (plan_type IN ('Direct', 'Regular')),
    fund_type VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    aum_crores DECIMAL(12,2),
    expense_ratio DECIMAL(5,3),
    exit_load VARCHAR(200),
    minimum_investment DECIMAL(12,2),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nav_data (
    scheme_code VARCHAR(20) NOT NULL,
    nav_date DATE NOT NULL,
    nav_value DECIMAL(15,4) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (scheme_code, nav_date)
);

CREATE TABLE IF NOT EXISTS fund_managers (
    id SERIAL PRIMARY KEY,
    scheme_code VARCHAR(20) NOT NULL,
    manager_name VARCHAR(200) NOT NULL,
    appointment_date DATE,
    departure_date DATE,
    is_current BOOLEAN DEFAULT TRUE,
    total_experience_years INTEGER,
    previous_amcs TEXT,
    qualifications TEXT,
    source VARCHAR(50) DEFAULT 'AMFI',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS manager_change_log (
    id SERIAL PRIMARY KEY,
    scheme_code VARCHAR(20) NOT NULL,
    old_manager_name VARCHAR(200),
    new_manager_name VARCHAR(200) NOT NULL,
    detected_date DATE NOT NULL,
    confirmed_date DATE,
    is_confirmed BOOLEAN DEFAULT FALSE,
    detection_source VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS portfolio_holdings (
    id SERIAL PRIMARY KEY,
    scheme_code VARCHAR(20) NOT NULL,
    disclosure_date DATE NOT NULL,
    stock_isin VARCHAR(20),
    stock_name VARCHAR(200) NOT NULL,
    weight_pct DECIMAL(7,4) NOT NULL,
    market_value_lakhs DECIMAL(15,2),
    sector VARCHAR(100),
    asset_type VARCHAR(50) DEFAULT 'Equity',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS benchmark_data (
    index_code VARCHAR(50) NOT NULL,
    index_name VARCHAR(150),
    price_date DATE NOT NULL,
    closing_value DECIMAL(15,4) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (index_code, price_date)
);

CREATE TABLE IF NOT EXISTS computed_metrics (
    id SERIAL PRIMARY KEY,
    scheme_code VARCHAR(20) NOT NULL,
    computation_date DATE NOT NULL,
    horizon_years INTEGER NOT NULL,
    cagr_pct DECIMAL(8,4),
    rolling_cagr_mean DECIMAL(8,4),
    rolling_cagr_median DECIMAL(8,4),
    rolling_cagr_std DECIMAL(8,4),
    pct_periods_beat_target DECIMAL(6,3),
    pct_periods_beat_benchmark DECIMAL(6,3),
    rolling_period_count INTEGER,
    sortino_ratio DECIMAL(8,4),
    sharpe_ratio DECIMAL(8,4),
    calmar_ratio DECIMAL(8,4),
    max_drawdown_pct DECIMAL(8,4),
    max_drawdown_duration_days INTEGER,
    upside_capture DECIMAL(8,4),
    downside_capture DECIMAL(8,4),
    fund_score DECIMAL(6,2),
    return_consistency_score DECIMAL(6,2),
    risk_adjusted_score DECIMAL(6,2),
    downside_score DECIMAL(6,2),
    manager_score DECIMAL(6,2),
    portfolio_quality_score DECIMAL(6,2),
    forward_context_score DECIMAL(6,2),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (scheme_code, computation_date, horizon_years)
);

CREATE TABLE IF NOT EXISTS bouquet_cache (
    id SERIAL PRIMARY KEY,
    archetype_id VARCHAR(50) NOT NULL,
    horizon_years INTEGER NOT NULL,
    target_cagr DECIMAL(6,2),
    computation_date DATE NOT NULL,
    funds_json TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    confidence_json TEXT NOT NULL,
    stress_test_json TEXT NOT NULL,
    overlap_json TEXT NOT NULL,
    methodology_json TEXT NOT NULL,
    devils_json TEXT NOT NULL,
    comparator_json TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (archetype_id, horizon_years, computation_date)
);

CREATE TABLE IF NOT EXISTS pipeline_log (
    id SERIAL PRIMARY KEY,
    pipeline_name VARCHAR(100) NOT NULL,
    run_date DATE NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    status VARCHAR(20) CHECK (status IN ('running', 'success', 'failed')),
    records_processed INTEGER,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_nav_scheme ON nav_data(scheme_code);
CREATE INDEX IF NOT EXISTS idx_nav_date ON nav_data(nav_date DESC);
CREATE INDEX IF NOT EXISTS idx_holdings_scheme_date ON portfolio_holdings(scheme_code, disclosure_date);
CREATE INDEX IF NOT EXISTS idx_metrics_scheme ON computed_metrics(scheme_code);
CREATE INDEX IF NOT EXISTS idx_cache_archetype ON bouquet_cache(archetype_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_name ON pipeline_log(pipeline_name);

SELECT table_name, 'CREATED' as status FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;
