-- Neon Database Update Script for GPU Integration
-- Run this script directly on your Neon database

-- Add new columns to GPU table if they don't exist
DO $$ 
BEGIN
    -- Add memory_gb column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='gpus' AND column_name='memory_gb') THEN
        ALTER TABLE gpus ADD COLUMN memory_gb INTEGER;
    END IF;
    
    -- Add memory_type column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='gpus' AND column_name='memory_type') THEN
        ALTER TABLE gpus ADD COLUMN memory_type VARCHAR(50);
    END IF;
    
    -- Add memory_bandwidth_tbps column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='gpus' AND column_name='memory_bandwidth_tbps') THEN
        ALTER TABLE gpus ADD COLUMN memory_bandwidth_tbps FLOAT;
    END IF;
    
    -- Add supports_fp4 column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='gpus' AND column_name='supports_fp4') THEN
        ALTER TABLE gpus ADD COLUMN supports_fp4 BOOLEAN;
    END IF;
    
    -- Add interconnect_type column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='gpus' AND column_name='interconnect_type') THEN
        ALTER TABLE gpus ADD COLUMN interconnect_type VARCHAR(50);
    END IF;
    
    -- Add cooling_requirement column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='gpus' AND column_name='cooling_requirement') THEN
        ALTER TABLE gpus ADD COLUMN cooling_requirement VARCHAR(20);
    END IF;
    
    -- Add supported_workloads column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='gpus' AND column_name='supported_workloads') THEN
        ALTER TABLE gpus ADD COLUMN supported_workloads JSONB;
    END IF;
    
    -- Add fp4_tflops column if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='gpus' AND column_name='fp4_tflops') THEN
        ALTER TABLE gpus ADD COLUMN fp4_tflops FLOAT;
    END IF;
END $$;

-- Ensure supported_workloads is JSONB (may have been created as JSON in a prior run)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='gpus' AND column_name='supported_workloads' AND data_type='json'
    ) THEN
        ALTER TABLE gpus ALTER COLUMN supported_workloads TYPE JSONB USING supported_workloads::jsonb;
    END IF;
END $$;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_gpu_memory_gb ON gpus(memory_gb);
CREATE INDEX IF NOT EXISTS idx_gpu_supports_fp4 ON gpus(supports_fp4);
CREATE INDEX IF NOT EXISTS idx_gpu_cooling_requirement ON gpus(cooling_requirement);

-- Clear existing GPU data to reseed with new specifications
DELETE FROM benchmarks;
DELETE FROM price_history;
DELETE FROM availability;
DELETE FROM gpus;

-- Insert new GPU data (corrected values — see review plan for details)
-- bf16_tflops / fp8_tflops / fp4_tflops aligned with HTML source + seed.py
INSERT INTO gpus (name, vendor, generation, form_factor, hbm_capacity_gb, hbm_type, mem_bandwidth_tb_s, memory_gb, memory_type, memory_bandwidth_tbps, bf16_tflops, fp64_tflops, fp8_tflops, fp4_tflops, supports_fp4, tdp_watts, cooling_type, intra_node_interconnect, interconnect_bw_gb_s, interconnect_type, cooling_requirement, supported_workloads, max_gpus_per_node, is_rack_scale, rack_gpu_count, rack_fabric_bw_tb_s, msrp_usd, is_estimated, release_date, created_at, updated_at) VALUES
-- NVIDIA Hopper
('H100 SXM5', 'NVIDIA', 'Hopper', 'SXM5', 80, 'HBM3', 3.35, 80, 'HBM3', 3.35, 1750, NULL, 3960, NULL, false, 700, 'air', 'NVLink 4', 900, 'NVLink 4', 'Any', '["inference", "training", "fine-tuning"]'::jsonb, 8, false, NULL, NULL, 25000, false, '2024-Q1', NOW(), NOW()),
('H200 SXM', 'NVIDIA', 'Hopper', 'SXM', 141, 'HBM3e', 4.8, 141, 'HBM3e', 4.8, 1970, NULL, 3960, NULL, false, 700, 'air', 'NVLink 4', 900, 'NVLink 4', 'Any', '["inference", "training", "fine-tuning"]'::jsonb, 8, false, NULL, NULL, 30000, false, '2024-Q1', NOW(), NOW()),
-- NVIDIA Blackwell
('B100 HGX', 'NVIDIA', 'Blackwell', 'HGX', 192, 'HBM3e', 8.0, 192, 'HBM3e', 8.0, 1750, NULL, 3600, 14000, true, 700, 'air', 'NVLink 5', 1800, 'NVLink 5', 'Any', '["inference", "training", "fine-tuning"]'::jsonb, 8, false, NULL, NULL, 35000, false, '2025-Q1', NOW(), NOW()),
('B200 HGX', 'NVIDIA', 'Blackwell', 'HGX', 192, 'HBM3e', 8.0, 192, 'HBM3e', 8.0, 2250, NULL, 4500, 19000, true, 1000, 'air', 'NVLink 5', 1800, 'NVLink 5', 'Any', '["inference", "training", "fine-tuning"]'::jsonb, 8, false, NULL, NULL, 40000, false, '2025-Q1', NOW(), NOW()),
-- NVIDIA Blackwell Ultra
('B300 HGX', 'NVIDIA', 'Blackwell Ultra', 'HGX', 288, 'HBM3e', 8.0, 288, 'HBM3e', 8.0, 2250, NULL, 5600, 15000, true, 1200, 'liquid', 'NVLink 5+', 2000, 'NVLink 5+', 'DLC', '["inference", "training", "fine-tuning"]'::jsonb, 8, false, NULL, NULL, 50000, false, '2026-Q1', NOW(), NOW()),
-- NVIDIA Rack-Scale
('GB200 NVL72', 'NVIDIA', 'Blackwell', 'NVL72', 192, 'HBM3e', 8.0, 192, 'HBM3e', 8.0, 2250, NULL, 5000, 20000, true, 1200, 'liquid', 'NVLink 5 (NVL72)', 1800, 'NVLink 5', 'DLC', '["inference", "training", "fine-tuning"]'::jsonb, 72, true, 72, 130, 40000, false, '2025-Q2', NOW(), NOW()),
('GB300 NVL72', 'NVIDIA', 'Blackwell Ultra', 'NVL72', 288, 'HBM3e', 8.0, 288, 'HBM3e', 8.0, 2250, NULL, 8000, 25000, true, 1400, 'liquid', 'NVLink 5+ (NVL72)', 2000, 'NVLink 5+', 'DLC', '["inference", "training", "fine-tuning"]'::jsonb, 72, true, 72, 200, 55000, false, '2026-H2', NOW(), NOW()),
-- NVIDIA RTX PRO (inference only) — bf16_tflops=480, fp8=960 estimated
('RTX PRO 6000 BSE', 'NVIDIA', 'Blackwell', 'PCIe', 96, 'GDDR7', 1.6, 96, 'GDDR7', 1.6, 480, NULL, 960, 6600, true, 600, 'air', 'PCIe Gen 5 x16', 32, 'PCIe', 'Air', '["inference"]'::jsonb, 8, false, NULL, NULL, 8500, false, '2025-Q1', NOW(), NOW()),
-- AMD Instinct
('MI300X', 'AMD', 'Instinct MI300', 'OAM', 192, 'HBM3', 3.2, 192, 'HBM3', 3.2, 1300, NULL, NULL, NULL, false, 750, 'air', 'Infinity Fabric v3', 896, 'IF v3', 'Any', '["inference", "training", "fine-tuning"]'::jsonb, 8, false, NULL, NULL, 22000, false, '2024-Q1', NOW(), NOW()),
('MI350X', 'AMD', 'Instinct MI350', 'OAM', 256, 'HBM3e', 6.0, 256, 'HBM3e', 6.0, 1800, NULL, 3600, NULL, false, 750, 'air', 'Infinity Fabric v4', 1500, 'IF v4', 'Any', '["inference", "training", "fine-tuning"]'::jsonb, 8, false, NULL, NULL, 28000, false, '2025-H2', NOW(), NOW()),
('MI355X', 'AMD', 'Instinct MI355', 'OAM', 288, 'HBM3e', 6.4, 288, 'HBM3e', 6.4, 2000, NULL, 4000, NULL, false, 750, 'air', 'Infinity Fabric v4', 1600, 'IF v4', 'Any', '["inference", "training", "fine-tuning"]'::jsonb, 8, false, NULL, NULL, 32000, false, '2026-Q1', NOW(), NOW());

-- Insert availability data (all GPUs)
INSERT INTO availability (gpu_id, lead_time_weeks, supply_status) 
SELECT id, lead_time_weeks, supply_status FROM (VALUES
('H100 SXM5', 4, 'available'),
('H200 SXM', 8, 'available'),
('B100 HGX', 12, 'available'),
('B200 HGX', 16, 'constrained'),
('B300 HGX', 40, 'announced'),
('GB200 NVL72', 24, 'constrained'),
('GB300 NVL72', 52, 'announced'),
('RTX PRO 6000 BSE', 8, 'available'),
('MI300X', 6, 'available'),
('MI350X', 20, 'announced'),
('MI355X', 36, 'announced')
) AS t(name, lead_time_weeks, supply_status)
JOIN gpus ON gpus.name = t.name;

-- Insert price history data (all GPUs, latest market price)
INSERT INTO price_history (gpu_id, date, price_usd, source)
SELECT id, date, price_usd, source FROM (VALUES
('H100 SXM5', '2025-04-01', 22000, 'market'),
('H200 SXM', '2025-04-01', 25000, 'market'),
('B100 HGX', '2025-04-01', 34000, 'market'),
('B200 HGX', '2025-04-01', 40000, 'market'),
('B300 HGX', '2025-04-01', 50000, 'estimate'),
('GB200 NVL72', '2025-04-01', 1950000, 'market'),
('GB300 NVL72', '2025-04-01', 2500000, 'estimate'),
('RTX PRO 6000 BSE', '2025-04-01', 8500, 'market'),
('MI300X', '2025-04-01', 10000, 'market'),
('MI350X', '2025-04-01', 18000, 'estimate'),
('MI355X', '2025-04-01', 22000, 'estimate')
) AS t(name, date, price_usd, source)
JOIN gpus ON gpus.name = t.name;

-- =====================================================
-- Benchmark data from Finance GPU Benchmark Matrix HTML
-- 189 rows across 9 GPUs, 21 benchmark types
-- =====================================================

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'STAC-A2', 'quant', 'Tick analytics, options pricing (Black-Scholes), time-series aggregation on financial datasets', 'Baseline', 38.0, '~18B ops/s', 18.0, 'B ops/s' FROM gpus g WHERE g.name = 'H200 SXM';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'STAC-A2', 'quant', 'Tick analytics, options pricing (Black-Scholes), time-series aggregation on financial datasets', 'Capable', 52.0, '~28B ops/s', 28.0, 'B ops/s' FROM gpus g WHERE g.name = 'B100 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'STAC-A2', 'quant', 'Tick analytics, options pricing (Black-Scholes), time-series aggregation on financial datasets', 'Strong', 62.0, '~36B ops/s', 36.0, 'B ops/s' FROM gpus g WHERE g.name = 'B200 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'STAC-A2', 'quant', 'Tick analytics, options pricing (Black-Scholes), time-series aggregation on financial datasets', 'Strong', 72.0, '~50B est.', 50.0, 'B' FROM gpus g WHERE g.name = 'B300 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'STAC-A2', 'quant', 'Tick analytics, options pricing (Black-Scholes), time-series aggregation on financial datasets', 'Best', 84.0, '~60B ops/s', 60.0, 'B ops/s' FROM gpus g WHERE g.name = 'GB200 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'STAC-A2', 'quant', 'Tick analytics, options pricing (Black-Scholes), time-series aggregation on financial datasets', 'Best+', 96.0, '~90B est.', 90.0, 'B' FROM gpus g WHERE g.name = 'GB300 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'STAC-A2', 'quant', 'Tick analytics, options pricing (Black-Scholes), time-series aggregation on financial datasets', 'Capable', 43.0, '~22B ops/s', 22.0, 'B ops/s' FROM gpus g WHERE g.name = 'MI300X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'STAC-A2', 'quant', 'Tick analytics, options pricing (Black-Scholes), time-series aggregation on financial datasets', 'Strong', 59.0, '~34B est.', 34.0, 'B' FROM gpus g WHERE g.name = 'MI350X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'STAC-A2', 'quant', 'Tick analytics, options pricing (Black-Scholes), time-series aggregation on financial datasets', 'Strong', 64.0, '~38B est.', 38.0, 'B' FROM gpus g WHERE g.name = 'MI355X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Monte Carlo FP64', 'quant', 'Path simulation for VaR, CVA, options — double-precision throughput-bound', 'Baseline', 36.0, '67 TFLOPS', 67.0, 'TFLOPS' FROM gpus g WHERE g.name = 'H200 SXM';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Monte Carlo FP64', 'quant', 'Path simulation for VaR, CVA, options — double-precision throughput-bound', 'Capable', 48.0, '90 TFLOPS', 90.0, 'TFLOPS' FROM gpus g WHERE g.name = 'B100 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Monte Carlo FP64', 'quant', 'Path simulation for VaR, CVA, options — double-precision throughput-bound', 'Strong', 60.0, '112 TFLOPS', 112.0, 'TFLOPS' FROM gpus g WHERE g.name = 'B200 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Monte Carlo FP64', 'quant', 'Path simulation for VaR, CVA, options — double-precision throughput-bound', 'Best', 75.0, '~140 est.', 140.0, '' FROM gpus g WHERE g.name = 'B300 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Monte Carlo FP64', 'quant', 'Path simulation for VaR, CVA, options — double-precision throughput-bound', 'Strong', 60.0, '90 TFLOPS/GPU', 90.0, 'TFLOPS/GPU' FROM gpus g WHERE g.name = 'GB200 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Monte Carlo FP64', 'quant', 'Path simulation for VaR, CVA, options — double-precision throughput-bound', 'Best+', 96.0, '~140 TFLOPS est.', 140.0, 'TFLOPS' FROM gpus g WHERE g.name = 'GB300 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Monte Carlo FP64', 'quant', 'Path simulation for VaR, CVA, options — double-precision throughput-bound', 'Capable', 45.0, '84 TFLOPS', 84.0, 'TFLOPS' FROM gpus g WHERE g.name = 'MI300X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Monte Carlo FP64', 'quant', 'Path simulation for VaR, CVA, options — double-precision throughput-bound', 'Strong', 58.0, '~108 est.', 108.0, '' FROM gpus g WHERE g.name = 'MI350X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Monte Carlo FP64', 'quant', 'Path simulation for VaR, CVA, options — double-precision throughput-bound', 'Strong', 63.0, '~116 est.', 116.0, '' FROM gpus g WHERE g.name = 'MI355X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'cuBLAS / rocBLAS DGEMM', 'quant', 'Dense FP64 matrix multiply — covariance, factor calibration, portfolio optimisation, FINMA IMM', 'Baseline', 36.0, '67 TFLOPS', 67.0, 'TFLOPS' FROM gpus g WHERE g.name = 'H200 SXM';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'cuBLAS / rocBLAS DGEMM', 'quant', 'Dense FP64 matrix multiply — covariance, factor calibration, portfolio optimisation, FINMA IMM', 'Capable', 48.0, '90 TFLOPS', 90.0, 'TFLOPS' FROM gpus g WHERE g.name = 'B100 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'cuBLAS / rocBLAS DGEMM', 'quant', 'Dense FP64 matrix multiply — covariance, factor calibration, portfolio optimisation, FINMA IMM', 'Strong', 60.0, '112 TFLOPS', 112.0, 'TFLOPS' FROM gpus g WHERE g.name = 'B200 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'cuBLAS / rocBLAS DGEMM', 'quant', 'Dense FP64 matrix multiply — covariance, factor calibration, portfolio optimisation, FINMA IMM', 'Best', 75.0, '~140 est.', 140.0, '' FROM gpus g WHERE g.name = 'B300 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'cuBLAS / rocBLAS DGEMM', 'quant', 'Dense FP64 matrix multiply — covariance, factor calibration, portfolio optimisation, FINMA IMM', 'Strong', 60.0, '90 TFLOPS/GPU', 90.0, 'TFLOPS/GPU' FROM gpus g WHERE g.name = 'GB200 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'cuBLAS / rocBLAS DGEMM', 'quant', 'Dense FP64 matrix multiply — covariance, factor calibration, portfolio optimisation, FINMA IMM', 'Best+', 96.0, '~140 TFLOPS est.', 140.0, 'TFLOPS' FROM gpus g WHERE g.name = 'GB300 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'cuBLAS / rocBLAS DGEMM', 'quant', 'Dense FP64 matrix multiply — covariance, factor calibration, portfolio optimisation, FINMA IMM', 'Capable', 45.0, '84 TFLOPS', 84.0, 'TFLOPS' FROM gpus g WHERE g.name = 'MI300X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'cuBLAS / rocBLAS DGEMM', 'quant', 'Dense FP64 matrix multiply — covariance, factor calibration, portfolio optimisation, FINMA IMM', 'Strong', 57.0, '~105 est.', 105.0, '' FROM gpus g WHERE g.name = 'MI350X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'cuBLAS / rocBLAS DGEMM', 'quant', 'Dense FP64 matrix multiply — covariance, factor calibration, portfolio optimisation, FINMA IMM', 'Strong', 62.0, '~114 est.', 114.0, '' FROM gpus g WHERE g.name = 'MI355X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'QuantLib GPU / XVA', 'risk', 'CVA/DVA/FVA computation, exposure profiles, netting sets — DORA Art.11 risk-critical', 'Baseline', 33.0, 'Ref.', NULL, '' FROM gpus g WHERE g.name = 'H200 SXM';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'QuantLib GPU / XVA', 'risk', 'CVA/DVA/FVA computation, exposure profiles, netting sets — DORA Art.11 risk-critical', 'Capable', 46.0, '~1.5× H200', 1.5, 'multiplier' FROM gpus g WHERE g.name = 'B100 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'QuantLib GPU / XVA', 'risk', 'CVA/DVA/FVA computation, exposure profiles, netting sets — DORA Art.11 risk-critical', 'Strong', 58.0, '~1.9× H200', 1.9, 'multiplier' FROM gpus g WHERE g.name = 'B200 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'QuantLib GPU / XVA', 'risk', 'CVA/DVA/FVA computation, exposure profiles, netting sets — DORA Art.11 risk-critical', 'Strong', 70.0, '~2.4× est.', 2.4, 'multiplier' FROM gpus g WHERE g.name = 'B300 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'QuantLib GPU / XVA', 'risk', 'CVA/DVA/FVA computation, exposure profiles, netting sets — DORA Art.11 risk-critical', 'Best', 82.0, '~3× H200', 3.0, 'multiplier' FROM gpus g WHERE g.name = 'GB200 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'QuantLib GPU / XVA', 'risk', 'CVA/DVA/FVA computation, exposure profiles, netting sets — DORA Art.11 risk-critical', 'Best+', 96.0, '~4.5× est.', 4.5, 'multiplier' FROM gpus g WHERE g.name = 'GB300 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'QuantLib GPU / XVA', 'risk', 'CVA/DVA/FVA computation, exposure profiles, netting sets — DORA Art.11 risk-critical', 'Capable', 42.0, '~1.3× H200', 1.3, 'multiplier' FROM gpus g WHERE g.name = 'MI300X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'QuantLib GPU / XVA', 'risk', 'CVA/DVA/FVA computation, exposure profiles, netting sets — DORA Art.11 risk-critical', 'Strong', 57.0, '~1.8× est.', 1.8, 'multiplier' FROM gpus g WHERE g.name = 'MI350X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'QuantLib GPU / XVA', 'risk', 'CVA/DVA/FVA computation, exposure profiles, netting sets — DORA Art.11 risk-critical', 'Strong', 62.0, '~2.0× est.', 2.0, 'multiplier' FROM gpus g WHERE g.name = 'MI355X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'VaR / Stressed VaR Batch', 'risk', 'Historical simulation VaR, 10,000+ scenarios, FRTB IMA SA — EBA/MiFID II reporting', 'Baseline', 33.0, 'Ref.', NULL, '' FROM gpus g WHERE g.name = 'H200 SXM';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'VaR / Stressed VaR Batch', 'risk', 'Historical simulation VaR, 10,000+ scenarios, FRTB IMA SA — EBA/MiFID II reporting', 'Capable', 46.0, '~1.5× H200', 1.5, 'multiplier' FROM gpus g WHERE g.name = 'B100 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'VaR / Stressed VaR Batch', 'risk', 'Historical simulation VaR, 10,000+ scenarios, FRTB IMA SA — EBA/MiFID II reporting', 'Strong', 57.0, '~1.8× H200', 1.8, 'multiplier' FROM gpus g WHERE g.name = 'B200 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'VaR / Stressed VaR Batch', 'risk', 'Historical simulation VaR, 10,000+ scenarios, FRTB IMA SA — EBA/MiFID II reporting', 'Strong', 70.0, '~2.3× est.', 2.3, 'multiplier' FROM gpus g WHERE g.name = 'B300 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'VaR / Stressed VaR Batch', 'risk', 'Historical simulation VaR, 10,000+ scenarios, FRTB IMA SA — EBA/MiFID II reporting', 'Best', 82.0, '~2.8× H200', 2.8, 'multiplier' FROM gpus g WHERE g.name = 'GB200 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'VaR / Stressed VaR Batch', 'risk', 'Historical simulation VaR, 10,000+ scenarios, FRTB IMA SA — EBA/MiFID II reporting', 'Best+', 96.0, '~4× est.', 4.0, 'multiplier' FROM gpus g WHERE g.name = 'GB300 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'VaR / Stressed VaR Batch', 'risk', 'Historical simulation VaR, 10,000+ scenarios, FRTB IMA SA — EBA/MiFID II reporting', 'Capable', 42.0, '~1.3× H200', 1.3, 'multiplier' FROM gpus g WHERE g.name = 'MI300X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'VaR / Stressed VaR Batch', 'risk', 'Historical simulation VaR, 10,000+ scenarios, FRTB IMA SA — EBA/MiFID II reporting', 'Strong', 56.0, '~1.7× est.', 1.7, 'multiplier' FROM gpus g WHERE g.name = 'MI350X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'VaR / Stressed VaR Batch', 'risk', 'Historical simulation VaR, 10,000+ scenarios, FRTB IMA SA — EBA/MiFID II reporting', 'Strong', 61.0, '~1.9× est.', 1.9, 'multiplier' FROM gpus g WHERE g.name = 'MI355X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Stress Testing (DFAST/EBA)', 'risk', 'Macro scenario propagation through loan/trading book models — EBA annual cycle', 'Baseline', 33.0, 'Ref.', NULL, '' FROM gpus g WHERE g.name = 'H200 SXM';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Stress Testing (DFAST/EBA)', 'risk', 'Macro scenario propagation through loan/trading book models — EBA annual cycle', 'Capable', 46.0, '~1.5× H200', 1.5, 'multiplier' FROM gpus g WHERE g.name = 'B100 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Stress Testing (DFAST/EBA)', 'risk', 'Macro scenario propagation through loan/trading book models — EBA annual cycle', 'Strong', 58.0, '~1.9× H200', 1.9, 'multiplier' FROM gpus g WHERE g.name = 'B200 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Stress Testing (DFAST/EBA)', 'risk', 'Macro scenario propagation through loan/trading book models — EBA annual cycle', 'Strong', 70.0, '~2.4× est.', 2.4, 'multiplier' FROM gpus g WHERE g.name = 'B300 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Stress Testing (DFAST/EBA)', 'risk', 'Macro scenario propagation through loan/trading book models — EBA annual cycle', 'Best', 82.0, '~2.8× H200', 2.8, 'multiplier' FROM gpus g WHERE g.name = 'GB200 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Stress Testing (DFAST/EBA)', 'risk', 'Macro scenario propagation through loan/trading book models — EBA annual cycle', 'Best+', 96.0, '~4× est.', 4.0, 'multiplier' FROM gpus g WHERE g.name = 'GB300 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Stress Testing (DFAST/EBA)', 'risk', 'Macro scenario propagation through loan/trading book models — EBA annual cycle', 'Capable', 41.0, '~1.3× H200', 1.3, 'multiplier' FROM gpus g WHERE g.name = 'MI300X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Stress Testing (DFAST/EBA)', 'risk', 'Macro scenario propagation through loan/trading book models — EBA annual cycle', 'Strong', 55.0, '~1.7× est.', 1.7, 'multiplier' FROM gpus g WHERE g.name = 'MI350X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Stress Testing (DFAST/EBA)', 'risk', 'Macro scenario propagation through loan/trading book models — EBA annual cycle', 'Strong', 60.0, '~1.9× est.', 1.9, 'multiplier' FROM gpus g WHERE g.name = 'MI355X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'MLPerf Inference v4', 'inference', 'Llama2-70B, GPT-J, BERT-Large — server & offline, trade surveillance, comms NLP', 'Baseline', 27.0, '~22k tok/s', 22.0, 'k tok/s' FROM gpus g WHERE g.name = 'H200 SXM';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'MLPerf Inference v4', 'inference', 'Llama2-70B, GPT-J, BERT-Large — server & offline, trade surveillance, comms NLP', 'Capable', 40.0, '~38k tok/s', 38.0, 'k tok/s' FROM gpus g WHERE g.name = 'B100 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'MLPerf Inference v4', 'inference', 'Llama2-70B, GPT-J, BERT-Large — server & offline, trade surveillance, comms NLP', 'Strong', 52.0, '~52k tok/s', 52.0, 'k tok/s' FROM gpus g WHERE g.name = 'B200 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'MLPerf Inference v4', 'inference', 'Llama2-70B, GPT-J, BERT-Large — server & offline, trade surveillance, comms NLP', 'Strong', 63.0, '~68k est.', 68.0, 'k' FROM gpus g WHERE g.name = 'B300 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'MLPerf Inference v4', 'inference', 'Llama2-70B, GPT-J, BERT-Large — server & offline, trade surveillance, comms NLP', 'Best', 82.0, '~200k (rack)', 200.0, 'k (rack' FROM gpus g WHERE g.name = 'GB200 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'MLPerf Inference v4', 'inference', 'Llama2-70B, GPT-J, BERT-Large — server & offline, trade surveillance, comms NLP', 'Best+', 97.0, '~320k est.', 320.0, 'k' FROM gpus g WHERE g.name = 'GB300 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'MLPerf Inference v4', 'inference', 'Llama2-70B, GPT-J, BERT-Large — server & offline, trade surveillance, comms NLP', 'Capable', 37.0, '~26k tok/s', 26.0, 'k tok/s' FROM gpus g WHERE g.name = 'MI300X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'MLPerf Inference v4', 'inference', 'Llama2-70B, GPT-J, BERT-Large — server & offline, trade surveillance, comms NLP', 'Strong', 50.0, '~42k est.', 42.0, 'k' FROM gpus g WHERE g.name = 'MI350X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'MLPerf Inference v4', 'inference', 'Llama2-70B, GPT-J, BERT-Large — server & offline, trade surveillance, comms NLP', 'Strong', 56.0, '~50k est.', 50.0, 'k' FROM gpus g WHERE g.name = 'MI355X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'vLLM / TRT-LLM Throughput', 'inference', 'Continuous batching LLM serving — regulatory filing analysis, client comms, AML NLP', 'Baseline', 27.0, '~4k tok/s/GPU', 4.0, 'k tok/s/GPU' FROM gpus g WHERE g.name = 'H200 SXM';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'vLLM / TRT-LLM Throughput', 'inference', 'Continuous batching LLM serving — regulatory filing analysis, client comms, AML NLP', 'Capable', 42.0, '~6.5k/GPU', 6.5, 'k/GPU' FROM gpus g WHERE g.name = 'B100 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'vLLM / TRT-LLM Throughput', 'inference', 'Continuous batching LLM serving — regulatory filing analysis, client comms, AML NLP', 'Strong', 54.0, '~8.5k/GPU', 8.5, 'k/GPU' FROM gpus g WHERE g.name = 'B200 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'vLLM / TRT-LLM Throughput', 'inference', 'Continuous batching LLM serving — regulatory filing analysis, client comms, AML NLP', 'Strong', 65.0, '~11k est.', 11.0, 'k' FROM gpus g WHERE g.name = 'B300 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'vLLM / TRT-LLM Throughput', 'inference', 'Continuous batching LLM serving — regulatory filing analysis, client comms, AML NLP', 'Best', 80.0, '~9k tok/s/GPU', 9.0, 'k tok/s/GPU' FROM gpus g WHERE g.name = 'GB200 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'vLLM / TRT-LLM Throughput', 'inference', 'Continuous batching LLM serving — regulatory filing analysis, client comms, AML NLP', 'Best+', 96.0, '~15k est.', 15.0, 'k' FROM gpus g WHERE g.name = 'GB300 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'vLLM / TRT-LLM Throughput', 'inference', 'Continuous batching LLM serving — regulatory filing analysis, client comms, AML NLP', 'Capable', 37.0, '~3.5k/GPU', 3.5, 'k/GPU' FROM gpus g WHERE g.name = 'MI300X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'vLLM / TRT-LLM Throughput', 'inference', 'Continuous batching LLM serving — regulatory filing analysis, client comms, AML NLP', 'Strong', 52.0, '~5.5k est.', 5.5, 'k' FROM gpus g WHERE g.name = 'MI350X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'vLLM / TRT-LLM Throughput', 'inference', 'Continuous batching LLM serving — regulatory filing analysis, client comms, AML NLP', 'Strong', 57.0, '~6.5k est.', 6.5, 'k' FROM gpus g WHERE g.name = 'MI355X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'ONNX RT / ROCm Inference', 'inference', 'Credit scoring, fraud, AML, KYC classification — SR 11-7 model validation environments', 'Strong', 55.0, 'Ref.', NULL, '' FROM gpus g WHERE g.name = 'H200 SXM';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'ONNX RT / ROCm Inference', 'inference', 'Credit scoring, fraud, AML, KYC classification — SR 11-7 model validation environments', 'Strong', 64.0, '~1.3× H200', 1.3, 'multiplier' FROM gpus g WHERE g.name = 'B100 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'ONNX RT / ROCm Inference', 'inference', 'Credit scoring, fraud, AML, KYC classification — SR 11-7 model validation environments', 'Strong', 72.0, '~1.5× H200', 1.5, 'multiplier' FROM gpus g WHERE g.name = 'B200 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'ONNX RT / ROCm Inference', 'inference', 'Credit scoring, fraud, AML, KYC classification — SR 11-7 model validation environments', 'Best', 82.0, '~1.9× est.', 1.9, 'multiplier' FROM gpus g WHERE g.name = 'B300 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'ONNX RT / ROCm Inference', 'inference', 'Credit scoring, fraud, AML, KYC classification — SR 11-7 model validation environments', 'Strong', 72.0, '~1.5× H200', 1.5, 'multiplier' FROM gpus g WHERE g.name = 'GB200 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'ONNX RT / ROCm Inference', 'inference', 'Credit scoring, fraud, AML, KYC classification — SR 11-7 model validation environments', 'Best+', 94.0, '~2.2× est.', 2.2, 'multiplier' FROM gpus g WHERE g.name = 'GB300 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'ONNX RT / ROCm Inference', 'inference', 'Credit scoring, fraud, AML, KYC classification — SR 11-7 model validation environments', 'Capable', 50.0, '~1.1× H200', 1.1, 'multiplier' FROM gpus g WHERE g.name = 'MI300X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'ONNX RT / ROCm Inference', 'inference', 'Credit scoring, fraud, AML, KYC classification — SR 11-7 model validation environments', 'Strong', 64.0, '~1.4× est.', 1.4, 'multiplier' FROM gpus g WHERE g.name = 'MI350X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'ONNX RT / ROCm Inference', 'inference', 'Credit scoring, fraud, AML, KYC classification — SR 11-7 model validation environments', 'Strong', 68.0, '~1.5× est.', 1.5, 'multiplier' FROM gpus g WHERE g.name = 'MI355X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'HPL / LINPACK', 'hpc', 'Dense FP64 FLOPS — actuarial (Solvency II), capital adequacy, FINMA IMM internal model', 'Baseline', 36.0, '67 TFLOPS', 67.0, 'TFLOPS' FROM gpus g WHERE g.name = 'H200 SXM';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'HPL / LINPACK', 'hpc', 'Dense FP64 FLOPS — actuarial (Solvency II), capital adequacy, FINMA IMM internal model', 'Capable', 48.0, '90 TFLOPS', 90.0, 'TFLOPS' FROM gpus g WHERE g.name = 'B100 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'HPL / LINPACK', 'hpc', 'Dense FP64 FLOPS — actuarial (Solvency II), capital adequacy, FINMA IMM internal model', 'Strong', 60.0, '112 TFLOPS', 112.0, 'TFLOPS' FROM gpus g WHERE g.name = 'B200 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'HPL / LINPACK', 'hpc', 'Dense FP64 FLOPS — actuarial (Solvency II), capital adequacy, FINMA IMM internal model', 'Best', 75.0, '~140 est.', 140.0, '' FROM gpus g WHERE g.name = 'B300 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'HPL / LINPACK', 'hpc', 'Dense FP64 FLOPS — actuarial (Solvency II), capital adequacy, FINMA IMM internal model', 'Strong', 60.0, '90 TFLOPS/GPU', 90.0, 'TFLOPS/GPU' FROM gpus g WHERE g.name = 'GB200 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'HPL / LINPACK', 'hpc', 'Dense FP64 FLOPS — actuarial (Solvency II), capital adequacy, FINMA IMM internal model', 'Best+', 96.0, '~140 TFLOPS est.', 140.0, 'TFLOPS' FROM gpus g WHERE g.name = 'GB300 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'HPL / LINPACK', 'hpc', 'Dense FP64 FLOPS — actuarial (Solvency II), capital adequacy, FINMA IMM internal model', 'Capable', 45.0, '84 TFLOPS', 84.0, 'TFLOPS' FROM gpus g WHERE g.name = 'MI300X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'HPL / LINPACK', 'hpc', 'Dense FP64 FLOPS — actuarial (Solvency II), capital adequacy, FINMA IMM internal model', 'Strong', 58.0, '~108 est.', 108.0, '' FROM gpus g WHERE g.name = 'MI350X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'HPL / LINPACK', 'hpc', 'Dense FP64 FLOPS — actuarial (Solvency II), capital adequacy, FINMA IMM internal model', 'Strong', 62.0, '~116 est.', 116.0, '' FROM gpus g WHERE g.name = 'MI355X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'HPCG (Sparse CG)', 'hpc', 'Sparse linear algebra — credit network graphs, interconnected counterparty exposure modelling', 'Baseline', 33.0, 'Ref.', NULL, '' FROM gpus g WHERE g.name = 'H200 SXM';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'HPCG (Sparse CG)', 'hpc', 'Sparse linear algebra — credit network graphs, interconnected counterparty exposure modelling', 'Capable', 50.0, '~1.7× H200', 1.7, 'multiplier' FROM gpus g WHERE g.name = 'B100 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'HPCG (Sparse CG)', 'hpc', 'Sparse linear algebra — credit network graphs, interconnected counterparty exposure modelling', 'Strong', 62.0, '~2.1× H200', 2.1, 'multiplier' FROM gpus g WHERE g.name = 'B200 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'HPCG (Sparse CG)', 'hpc', 'Sparse linear algebra — credit network graphs, interconnected counterparty exposure modelling', 'Best', 79.0, '~3× est.', 3.0, 'multiplier' FROM gpus g WHERE g.name = 'B300 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'HPCG (Sparse CG)', 'hpc', 'Sparse linear algebra — credit network graphs, interconnected counterparty exposure modelling', 'Strong', 62.0, '~2.1× H200', 2.1, 'multiplier' FROM gpus g WHERE g.name = 'GB200 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'HPCG (Sparse CG)', 'hpc', 'Sparse linear algebra — credit network graphs, interconnected counterparty exposure modelling', 'Best+', 96.0, '~3.5× est.', 3.5, 'multiplier' FROM gpus g WHERE g.name = 'GB300 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'HPCG (Sparse CG)', 'hpc', 'Sparse linear algebra — credit network graphs, interconnected counterparty exposure modelling', 'Capable', 47.0, '~1.6× H200', 1.6, 'multiplier' FROM gpus g WHERE g.name = 'MI300X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'HPCG (Sparse CG)', 'hpc', 'Sparse linear algebra — credit network graphs, interconnected counterparty exposure modelling', 'Strong', 62.0, '~2.1× est.', 2.1, 'multiplier' FROM gpus g WHERE g.name = 'MI350X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'HPCG (Sparse CG)', 'hpc', 'Sparse linear algebra — credit network graphs, interconnected counterparty exposure modelling', 'Strong', 66.0, '~2.2× est.', 2.2, 'multiplier' FROM gpus g WHERE g.name = 'MI355X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'STREAM (Memory BW)', 'hpc', 'Sustained HBM bandwidth — large portfolio streaming, factor data loading, time-series scan', 'Baseline', 30.0, '4.8 TB/s', 4.8, 'TB/s' FROM gpus g WHERE g.name = 'H200 SXM';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'STREAM (Memory BW)', 'hpc', 'Sustained HBM bandwidth — large portfolio streaming, factor data loading, time-series scan', 'Capable', 50.0, '8.0 TB/s', 8.0, 'TB/s' FROM gpus g WHERE g.name = 'B100 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'STREAM (Memory BW)', 'hpc', 'Sustained HBM bandwidth — large portfolio streaming, factor data loading, time-series scan', 'Capable', 50.0, '8.0 TB/s', 8.0, 'TB/s' FROM gpus g WHERE g.name = 'B200 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'STREAM (Memory BW)', 'hpc', 'Sustained HBM bandwidth — large portfolio streaming, factor data loading, time-series scan', 'Best', 100.0, '~16 TB/s', 16.0, 'TB/s' FROM gpus g WHERE g.name = 'B300 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'STREAM (Memory BW)', 'hpc', 'Sustained HBM bandwidth — large portfolio streaming, factor data loading, time-series scan', 'Capable', 50.0, '8 TB/s/GPU', 8.0, 'TB/s/GPU' FROM gpus g WHERE g.name = 'GB200 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'STREAM (Memory BW)', 'hpc', 'Sustained HBM bandwidth — large portfolio streaming, factor data loading, time-series scan', 'Best+', 100.0, '~16 TB/s/GPU', 16.0, 'TB/s/GPU' FROM gpus g WHERE g.name = 'GB300 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'STREAM (Memory BW)', 'hpc', 'Sustained HBM bandwidth — large portfolio streaming, factor data loading, time-series scan', 'Capable', 33.0, '5.3 TB/s', 5.3, 'TB/s' FROM gpus g WHERE g.name = 'MI300X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'STREAM (Memory BW)', 'hpc', 'Sustained HBM bandwidth — large portfolio streaming, factor data loading, time-series scan', 'Strong', 50.0, '~8 TB/s est.', 8.0, 'TB/s' FROM gpus g WHERE g.name = 'MI350X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'STREAM (Memory BW)', 'hpc', 'Sustained HBM bandwidth — large portfolio streaming, factor data loading, time-series scan', 'Strong', 50.0, '~8 TB/s est.', 8.0, 'TB/s' FROM gpus g WHERE g.name = 'MI355X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'GPU-Direct RDMA / FIO', 'trading', 'Storage-to-GPU bandwidth — tick history replay, EOD P&L recalc, MiFID II 5yr audit pipelines', 'Strong', 45.0, '~100 GB/s', 100000000000.0, 'B/s' FROM gpus g WHERE g.name = 'H200 SXM';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'GPU-Direct RDMA / FIO', 'trading', 'Storage-to-GPU bandwidth — tick history replay, EOD P&L recalc, MiFID II 5yr audit pipelines', 'Strong', 56.0, '~160 GB/s', 160000000000.0, 'B/s' FROM gpus g WHERE g.name = 'B100 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'GPU-Direct RDMA / FIO', 'trading', 'Storage-to-GPU bandwidth — tick history replay, EOD P&L recalc, MiFID II 5yr audit pipelines', 'Strong', 64.0, '~200 GB/s', 200000000000.0, 'B/s' FROM gpus g WHERE g.name = 'B200 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'GPU-Direct RDMA / FIO', 'trading', 'Storage-to-GPU bandwidth — tick history replay, EOD P&L recalc, MiFID II 5yr audit pipelines', 'Best', 80.0, '~300 GB/s est.', 300000000000.0, 'B/s' FROM gpus g WHERE g.name = 'B300 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'GPU-Direct RDMA / FIO', 'trading', 'Storage-to-GPU bandwidth — tick history replay, EOD P&L recalc, MiFID II 5yr audit pipelines', 'Strong', 64.0, '~200 GB/s', 200000000000.0, 'B/s' FROM gpus g WHERE g.name = 'GB200 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'GPU-Direct RDMA / FIO', 'trading', 'Storage-to-GPU bandwidth — tick history replay, EOD P&L recalc, MiFID II 5yr audit pipelines', 'Best+', 96.0, '~400 GB/s est.', 400000000000.0, 'B/s' FROM gpus g WHERE g.name = 'GB300 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'GPU-Direct RDMA / FIO', 'trading', 'Storage-to-GPU bandwidth — tick history replay, EOD P&L recalc, MiFID II 5yr audit pipelines', 'Capable', 40.0, '~90 GB/s', 90000000000.0, 'B/s' FROM gpus g WHERE g.name = 'MI300X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'GPU-Direct RDMA / FIO', 'trading', 'Storage-to-GPU bandwidth — tick history replay, EOD P&L recalc, MiFID II 5yr audit pipelines', 'Strong', 56.0, '~155 GB/s est.', 155000000000.0, 'B/s' FROM gpus g WHERE g.name = 'MI350X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'GPU-Direct RDMA / FIO', 'trading', 'Storage-to-GPU bandwidth — tick history replay, EOD P&L recalc, MiFID II 5yr audit pipelines', 'Strong', 62.0, '~175 GB/s est.', 175000000000.0, 'B/s' FROM gpus g WHERE g.name = 'MI355X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Interconnect BW (NVLink / Infinity Fabric)', 'trading', 'Peer-to-peer GPU fabric bandwidth — model parallelism for trading signal ensembles and large risk models', 'Limited', 18.0, 'NVL4: 900 GB/s', 900.0, 'GB/s' FROM gpus g WHERE g.name = 'H200 SXM';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Interconnect BW (NVLink / Infinity Fabric)', 'trading', 'Peer-to-peer GPU fabric bandwidth — model parallelism for trading signal ensembles and large risk models', 'Capable', 30.0, 'NVL5: 1.8 TB/s', 1.8, 'TB/s' FROM gpus g WHERE g.name = 'B100 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Interconnect BW (NVLink / Infinity Fabric)', 'trading', 'Peer-to-peer GPU fabric bandwidth — model parallelism for trading signal ensembles and large risk models', 'Capable', 30.0, 'NVL5: 1.8 TB/s', 1.8, 'TB/s' FROM gpus g WHERE g.name = 'B200 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Interconnect BW (NVLink / Infinity Fabric)', 'trading', 'Peer-to-peer GPU fabric bandwidth — model parallelism for trading signal ensembles and large risk models', 'Strong', 40.0, 'NVL5+: ~2 TB/s', NULL, '' FROM gpus g WHERE g.name = 'B300 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Interconnect BW (NVLink / Infinity Fabric)', 'trading', 'Peer-to-peer GPU fabric bandwidth — model parallelism for trading signal ensembles and large risk models', 'Best', 88.0, 'NVL72: 130 TB/s', 130.0, 'TB/s' FROM gpus g WHERE g.name = 'GB200 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Interconnect BW (NVLink / Infinity Fabric)', 'trading', 'Peer-to-peer GPU fabric bandwidth — model parallelism for trading signal ensembles and large risk models', 'Best+', 99.0, 'NVL72: ~200 TB/s', NULL, '' FROM gpus g WHERE g.name = 'GB300 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Interconnect BW (NVLink / Infinity Fabric)', 'trading', 'Peer-to-peer GPU fabric bandwidth — model parallelism for trading signal ensembles and large risk models', 'Limited', 22.0, 'IF v3: 896 GB/s', 896.0, 'GB/s' FROM gpus g WHERE g.name = 'MI300X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Interconnect BW (NVLink / Infinity Fabric)', 'trading', 'Peer-to-peer GPU fabric bandwidth — model parallelism for trading signal ensembles and large risk models', 'Strong', 33.0, 'IF v4: ~1.5 TB/s', NULL, '' FROM gpus g WHERE g.name = 'MI350X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Interconnect BW (NVLink / Infinity Fabric)', 'trading', 'Peer-to-peer GPU fabric bandwidth — model parallelism for trading signal ensembles and large risk models', 'Strong', 36.0, 'IF v4: ~1.6 TB/s', NULL, '' FROM gpus g WHERE g.name = 'MI355X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Prefill Throughput', 'tokenization', 'Prompt ingestion rate — regulatory document analysis, long-form contract NLP, FRTB/DORA policy parsing at scale', 'Baseline', 28.0, '~18K tok/s', 18000.0, 'tok/s' FROM gpus g WHERE g.name = 'H200 SXM';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Prefill Throughput', 'tokenization', 'Prompt ingestion rate — regulatory document analysis, long-form contract NLP, FRTB/DORA policy parsing at scale', 'Capable', 44.0, '~32K tok/s', 32000.0, 'tok/s' FROM gpus g WHERE g.name = 'B100 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Prefill Throughput', 'tokenization', 'Prompt ingestion rate — regulatory document analysis, long-form contract NLP, FRTB/DORA policy parsing at scale', 'Strong', 58.0, '~45K tok/s', 45000.0, 'tok/s' FROM gpus g WHERE g.name = 'B200 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Prefill Throughput', 'tokenization', 'Prompt ingestion rate — regulatory document analysis, long-form contract NLP, FRTB/DORA policy parsing at scale', 'Best', 78.0, '~70K tok/s est.', 70000.0, 'tok/s' FROM gpus g WHERE g.name = 'B300 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Prefill Throughput', 'tokenization', 'Prompt ingestion rate — regulatory document analysis, long-form contract NLP, FRTB/DORA policy parsing at scale', 'Best', 88.0, '~82K tok/s rack', 82000.0, 'tok/s rack' FROM gpus g WHERE g.name = 'GB200 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Prefill Throughput', 'tokenization', 'Prompt ingestion rate — regulatory document analysis, long-form contract NLP, FRTB/DORA policy parsing at scale', 'Best+', 99.0, '~130K tok/s est.', 130000.0, 'tok/s' FROM gpus g WHERE g.name = 'GB300 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Prefill Throughput', 'tokenization', 'Prompt ingestion rate — regulatory document analysis, long-form contract NLP, FRTB/DORA policy parsing at scale', 'Capable', 32.0, '~22K tok/s', 22000.0, 'tok/s' FROM gpus g WHERE g.name = 'MI300X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Prefill Throughput', 'tokenization', 'Prompt ingestion rate — regulatory document analysis, long-form contract NLP, FRTB/DORA policy parsing at scale', 'Strong', 52.0, '~38K tok/s est.', 38000.0, 'tok/s' FROM gpus g WHERE g.name = 'MI350X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Prefill Throughput', 'tokenization', 'Prompt ingestion rate — regulatory document analysis, long-form contract NLP, FRTB/DORA policy parsing at scale', 'Strong', 60.0, '~46K tok/s est.', 46000.0, 'tok/s' FROM gpus g WHERE g.name = 'MI355X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Decode Throughput', 'tokenization', 'Autoregressive generation rate — real-time AML alert narratives, automated DORA incident reports, client advisory drafting, trade surveillance summaries', 'Baseline', 30.0, '~55 tok/s', 55.0, 'tok/s' FROM gpus g WHERE g.name = 'H200 SXM';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Decode Throughput', 'tokenization', 'Autoregressive generation rate — real-time AML alert narratives, automated DORA incident reports, client advisory drafting, trade surveillance summaries', 'Capable', 46.0, '~90 tok/s', 90.0, 'tok/s' FROM gpus g WHERE g.name = 'B100 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Decode Throughput', 'tokenization', 'Autoregressive generation rate — real-time AML alert narratives, automated DORA incident reports, client advisory drafting, trade surveillance summaries', 'Strong', 60.0, '~115 tok/s', 115.0, 'tok/s' FROM gpus g WHERE g.name = 'B200 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Decode Throughput', 'tokenization', 'Autoregressive generation rate — real-time AML alert narratives, automated DORA incident reports, client advisory drafting, trade surveillance summaries', 'Best', 80.0, '~170 tok/s est.', 170.0, 'tok/s' FROM gpus g WHERE g.name = 'B300 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Decode Throughput', 'tokenization', 'Autoregressive generation rate — real-time AML alert narratives, automated DORA incident reports, client advisory drafting, trade surveillance summaries', 'Best', 88.0, '~200 tok/s', 200.0, 'tok/s' FROM gpus g WHERE g.name = 'GB200 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Decode Throughput', 'tokenization', 'Autoregressive generation rate — real-time AML alert narratives, automated DORA incident reports, client advisory drafting, trade surveillance summaries', 'Best+', 97.0, '~280 tok/s est.', 280.0, 'tok/s' FROM gpus g WHERE g.name = 'GB300 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Decode Throughput', 'tokenization', 'Autoregressive generation rate — real-time AML alert narratives, automated DORA incident reports, client advisory drafting, trade surveillance summaries', 'Capable', 38.0, '~70 tok/s', 70.0, 'tok/s' FROM gpus g WHERE g.name = 'MI300X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Decode Throughput', 'tokenization', 'Autoregressive generation rate — real-time AML alert narratives, automated DORA incident reports, client advisory drafting, trade surveillance summaries', 'Strong', 54.0, '~100 tok/s est.', 100.0, 'tok/s' FROM gpus g WHERE g.name = 'MI350X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Decode Throughput', 'tokenization', 'Autoregressive generation rate — real-time AML alert narratives, automated DORA incident reports, client advisory drafting, trade surveillance summaries', 'Strong', 62.0, '~118 tok/s est.', 118.0, 'tok/s' FROM gpus g WHERE g.name = 'MI355X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Batched Decode (BS=128)', 'tokenization', 'High-concurrency generation — parallel AML case processing, multi-analyst regulatory Q&A, concurrent trade commentary across desks', 'Baseline', 26.0, '~4.2K tok/s', 4200.0, 'tok/s' FROM gpus g WHERE g.name = 'H200 SXM';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Batched Decode (BS=128)', 'tokenization', 'High-concurrency generation — parallel AML case processing, multi-analyst regulatory Q&A, concurrent trade commentary across desks', 'Capable', 44.0, '~7.5K tok/s', 7500.0, 'tok/s' FROM gpus g WHERE g.name = 'B100 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Batched Decode (BS=128)', 'tokenization', 'High-concurrency generation — parallel AML case processing, multi-analyst regulatory Q&A, concurrent trade commentary across desks', 'Strong', 58.0, '~10K tok/s', 10000.0, 'tok/s' FROM gpus g WHERE g.name = 'B200 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Batched Decode (BS=128)', 'tokenization', 'High-concurrency generation — parallel AML case processing, multi-analyst regulatory Q&A, concurrent trade commentary across desks', 'Best', 80.0, '~16K tok/s est.', 16000.0, 'tok/s' FROM gpus g WHERE g.name = 'B300 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Batched Decode (BS=128)', 'tokenization', 'High-concurrency generation — parallel AML case processing, multi-analyst regulatory Q&A, concurrent trade commentary across desks', 'Best', 90.0, '~19K tok/s', 19000.0, 'tok/s' FROM gpus g WHERE g.name = 'GB200 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Batched Decode (BS=128)', 'tokenization', 'High-concurrency generation — parallel AML case processing, multi-analyst regulatory Q&A, concurrent trade commentary across desks', 'Best+', 99.0, '~26K tok/s est.', 26000.0, 'tok/s' FROM gpus g WHERE g.name = 'GB300 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Batched Decode (BS=128)', 'tokenization', 'High-concurrency generation — parallel AML case processing, multi-analyst regulatory Q&A, concurrent trade commentary across desks', 'Capable', 36.0, '~5.8K tok/s', 5800.0, 'tok/s' FROM gpus g WHERE g.name = 'MI300X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Batched Decode (BS=128)', 'tokenization', 'High-concurrency generation — parallel AML case processing, multi-analyst regulatory Q&A, concurrent trade commentary across desks', 'Strong', 52.0, '~8.5K tok/s est.', 8500.0, 'tok/s' FROM gpus g WHERE g.name = 'MI350X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Batched Decode (BS=128)', 'tokenization', 'High-concurrency generation — parallel AML case processing, multi-analyst regulatory Q&A, concurrent trade commentary across desks', 'Strong', 60.0, '~10K tok/s est.', 10000.0, 'tok/s' FROM gpus g WHERE g.name = 'MI355X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'KV Cache Capacity', 'tokenization', 'Concurrent context slots in VRAM — long-document analysis (ISDA agreements, prospectuses), extended regulatory dialogue, multi-turn audit assistant sessions', 'Baseline', 22.0, '~3 slots (141GB)', 3.0, 'slots (141GB' FROM gpus g WHERE g.name = 'H200 SXM';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'KV Cache Capacity', 'tokenization', 'Concurrent context slots in VRAM — long-document analysis (ISDA agreements, prospectuses), extended regulatory dialogue, multi-turn audit assistant sessions', 'Capable', 36.0, '~5 slots (192GB)', 5.0, 'slots (192GB' FROM gpus g WHERE g.name = 'B100 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'KV Cache Capacity', 'tokenization', 'Concurrent context slots in VRAM — long-document analysis (ISDA agreements, prospectuses), extended regulatory dialogue, multi-turn audit assistant sessions', 'Capable', 36.0, '~5 slots (192GB)', 5.0, 'slots (192GB' FROM gpus g WHERE g.name = 'B200 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'KV Cache Capacity', 'tokenization', 'Concurrent context slots in VRAM — long-document analysis (ISDA agreements, prospectuses), extended regulatory dialogue, multi-turn audit assistant sessions', 'Strong', 58.0, '~8 slots (288GB)', 8.0, 'slots (288GB' FROM gpus g WHERE g.name = 'B300 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'KV Cache Capacity', 'tokenization', 'Concurrent context slots in VRAM — long-document analysis (ISDA agreements, prospectuses), extended regulatory dialogue, multi-turn audit assistant sessions', 'Best', 96.0, '360+ slots (NVL72)', 360.0, '+ slots (NVL72' FROM gpus g WHERE g.name = 'GB200 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'KV Cache Capacity', 'tokenization', 'Concurrent context slots in VRAM — long-document analysis (ISDA agreements, prospectuses), extended regulatory dialogue, multi-turn audit assistant sessions', 'Best+', 99.0, '600+ slots (NVL72)', 600.0, '+ slots (NVL72' FROM gpus g WHERE g.name = 'GB300 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'KV Cache Capacity', 'tokenization', 'Concurrent context slots in VRAM — long-document analysis (ISDA agreements, prospectuses), extended regulatory dialogue, multi-turn audit assistant sessions', 'Capable', 36.0, '~5 slots (192GB)', 5.0, 'slots (192GB' FROM gpus g WHERE g.name = 'MI300X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'KV Cache Capacity', 'tokenization', 'Concurrent context slots in VRAM — long-document analysis (ISDA agreements, prospectuses), extended regulatory dialogue, multi-turn audit assistant sessions', 'Strong', 58.0, '~8 slots (288GB)', 8.0, 'slots (288GB' FROM gpus g WHERE g.name = 'MI350X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'KV Cache Capacity', 'tokenization', 'Concurrent context slots in VRAM — long-document analysis (ISDA agreements, prospectuses), extended regulatory dialogue, multi-turn audit assistant sessions', 'Strong', 58.0, '~8 slots (288GB)', 8.0, 'slots (288GB' FROM gpus g WHERE g.name = 'MI355X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Time-to-First-Token', 'tokenization', 'Prefill latency for 4K prompt — real-time trade surveillance alert triage, intraday risk NLP query response, latency-sensitive compliance workflows', 'Capable', 55.0, '~220ms', 220.0, 'ms' FROM gpus g WHERE g.name = 'H200 SXM';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Time-to-First-Token', 'tokenization', 'Prefill latency for 4K prompt — real-time trade surveillance alert triage, intraday risk NLP query response, latency-sensitive compliance workflows', 'Strong', 68.0, '~140ms', 140.0, 'ms' FROM gpus g WHERE g.name = 'B100 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Time-to-First-Token', 'tokenization', 'Prefill latency for 4K prompt — real-time trade surveillance alert triage, intraday risk NLP query response, latency-sensitive compliance workflows', 'Strong', 75.0, '~110ms', 110.0, 'ms' FROM gpus g WHERE g.name = 'B200 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Time-to-First-Token', 'tokenization', 'Prefill latency for 4K prompt — real-time trade surveillance alert triage, intraday risk NLP query response, latency-sensitive compliance workflows', 'Best', 88.0, '~75ms est.', 75.0, 'ms' FROM gpus g WHERE g.name = 'B300 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Time-to-First-Token', 'tokenization', 'Prefill latency for 4K prompt — real-time trade surveillance alert triage, intraday risk NLP query response, latency-sensitive compliance workflows', 'Best', 92.0, '~60ms', 60.0, 'ms' FROM gpus g WHERE g.name = 'GB200 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Time-to-First-Token', 'tokenization', 'Prefill latency for 4K prompt — real-time trade surveillance alert triage, intraday risk NLP query response, latency-sensitive compliance workflows', 'Best+', 99.0, '~40ms est.', 40.0, 'ms' FROM gpus g WHERE g.name = 'GB300 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Time-to-First-Token', 'tokenization', 'Prefill latency for 4K prompt — real-time trade surveillance alert triage, intraday risk NLP query response, latency-sensitive compliance workflows', 'Capable', 48.0, '~180ms', 180.0, 'ms' FROM gpus g WHERE g.name = 'MI300X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Time-to-First-Token', 'tokenization', 'Prefill latency for 4K prompt — real-time trade surveillance alert triage, intraday risk NLP query response, latency-sensitive compliance workflows', 'Strong', 64.0, '~125ms est.', 125.0, 'ms' FROM gpus g WHERE g.name = 'MI350X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Time-to-First-Token', 'tokenization', 'Prefill latency for 4K prompt — real-time trade surveillance alert triage, intraday risk NLP query response, latency-sensitive compliance workflows', 'Strong', 70.0, '~105ms est.', 105.0, 'ms' FROM gpus g WHERE g.name = 'MI355X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Max Context Length', 'tokenization', 'Longest document processable in-VRAM without paging — full Basel IV framework analysis, complete MiFID II rulebook Q&A, entire loan agreement review in single pass', 'Capable', 30.0, '~96K tokens', 96000.0, 'tokens' FROM gpus g WHERE g.name = 'H200 SXM';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Max Context Length', 'tokenization', 'Longest document processable in-VRAM without paging — full Basel IV framework analysis, complete MiFID II rulebook Q&A, entire loan agreement review in single pass', 'Strong', 48.0, '~160K tokens', 160000.0, 'tokens' FROM gpus g WHERE g.name = 'B100 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Max Context Length', 'tokenization', 'Longest document processable in-VRAM without paging — full Basel IV framework analysis, complete MiFID II rulebook Q&A, entire loan agreement review in single pass', 'Strong', 48.0, '~160K tokens', 160000.0, 'tokens' FROM gpus g WHERE g.name = 'B200 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Max Context Length', 'tokenization', 'Longest document processable in-VRAM without paging — full Basel IV framework analysis, complete MiFID II rulebook Q&A, entire loan agreement review in single pass', 'Best', 72.0, '~280K tokens est.', 280000.0, 'tokens' FROM gpus g WHERE g.name = 'B300 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Max Context Length', 'tokenization', 'Longest document processable in-VRAM without paging — full Basel IV framework analysis, complete MiFID II rulebook Q&A, entire loan agreement review in single pass', 'Best', 94.0, '1M+ tokens (NVL72)', 1000000.0, '+ tokens (NVL72' FROM gpus g WHERE g.name = 'GB200 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Max Context Length', 'tokenization', 'Longest document processable in-VRAM without paging — full Basel IV framework analysis, complete MiFID II rulebook Q&A, entire loan agreement review in single pass', 'Best+', 99.0, '2M+ tokens (NVL72)', 2000000.0, '+ tokens (NVL72' FROM gpus g WHERE g.name = 'GB300 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Max Context Length', 'tokenization', 'Longest document processable in-VRAM without paging — full Basel IV framework analysis, complete MiFID II rulebook Q&A, entire loan agreement review in single pass', 'Capable', 48.0, '~160K tokens', 160000.0, 'tokens' FROM gpus g WHERE g.name = 'MI300X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Max Context Length', 'tokenization', 'Longest document processable in-VRAM without paging — full Basel IV framework analysis, complete MiFID II rulebook Q&A, entire loan agreement review in single pass', 'Strong', 72.0, '~280K tokens est.', 280000.0, 'tokens' FROM gpus g WHERE g.name = 'MI350X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'Max Context Length', 'tokenization', 'Longest document processable in-VRAM without paging — full Basel IV framework analysis, complete MiFID II rulebook Q&A, entire loan agreement review in single pass', 'Strong', 72.0, '~280K tokens est.', 280000.0, 'tokens' FROM gpus g WHERE g.name = 'MI355X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'FP8 Quantised Throughput', 'tokenization', 'Inference throughput at INT8/FP8 precision — maximising token volume for batch regulatory processing, overnight compliance report generation, cost-optimised AML screening', 'N/A', 10.0, 'No FP8 (H200)', NULL, '' FROM gpus g WHERE g.name = 'H200 SXM';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'FP8 Quantised Throughput', 'tokenization', 'Inference throughput at INT8/FP8 precision — maximising token volume for batch regulatory processing, overnight compliance report generation, cost-optimised AML screening', 'Strong', 70.0, '~1.8× vs FP16', 1.8, 'multiplier' FROM gpus g WHERE g.name = 'B100 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'FP8 Quantised Throughput', 'tokenization', 'Inference throughput at INT8/FP8 precision — maximising token volume for batch regulatory processing, overnight compliance report generation, cost-optimised AML screening', 'Strong', 76.0, '~1.9× vs FP16', 1.9, 'multiplier' FROM gpus g WHERE g.name = 'B200 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'FP8 Quantised Throughput', 'tokenization', 'Inference throughput at INT8/FP8 precision — maximising token volume for batch regulatory processing, overnight compliance report generation, cost-optimised AML screening', 'Best', 88.0, '~2.1× vs FP16 est.', 2.1, 'multiplier' FROM gpus g WHERE g.name = 'B300 HGX';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'FP8 Quantised Throughput', 'tokenization', 'Inference throughput at INT8/FP8 precision — maximising token volume for batch regulatory processing, overnight compliance report generation, cost-optimised AML screening', 'Best', 92.0, '~2.2× vs FP16', 2.2, 'multiplier' FROM gpus g WHERE g.name = 'GB200 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'FP8 Quantised Throughput', 'tokenization', 'Inference throughput at INT8/FP8 precision — maximising token volume for batch regulatory processing, overnight compliance report generation, cost-optimised AML screening', 'Best+', 99.0, '~2.4× vs FP16 est.', 2.4, 'multiplier' FROM gpus g WHERE g.name = 'GB300 NVL72';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'FP8 Quantised Throughput', 'tokenization', 'Inference throughput at INT8/FP8 precision — maximising token volume for batch regulatory processing, overnight compliance report generation, cost-optimised AML screening', 'Limited', 22.0, 'FP8 partial support', NULL, '' FROM gpus g WHERE g.name = 'MI300X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'FP8 Quantised Throughput', 'tokenization', 'Inference throughput at INT8/FP8 precision — maximising token volume for batch regulatory processing, overnight compliance report generation, cost-optimised AML screening', 'Strong', 66.0, '~1.7× est.', 1.7, 'multiplier' FROM gpus g WHERE g.name = 'MI350X';

INSERT INTO benchmarks (gpu_id, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
SELECT g.id, 'FP8 Quantised Throughput', 'tokenization', 'Inference throughput at INT8/FP8 precision — maximising token volume for batch regulatory processing, overnight compliance report generation, cost-optimised AML screening', 'Strong', 72.0, '~1.8× est.', 1.8, 'multiplier' FROM gpus g WHERE g.name = 'MI355X';

-- =====================================================
-- Additional price history data (Q1–Q3 2025 trend)
-- =====================================================
INSERT INTO price_history (gpu_id, date, price_usd, source)
SELECT id, date, price_usd, source FROM (VALUES
('H100 SXM5', '2025-01-01', 25000, 'market'),
('H100 SXM5', '2025-02-01', 23500, 'market'),
('H100 SXM5', '2025-03-01', 22500, 'market'),
('H200 SXM', '2025-01-01', 30000, 'msrp'),
('H200 SXM', '2025-02-01', 28000, 'market'),
('H200 SXM', '2025-03-01', 26000, 'market'),
('B100 HGX', '2025-01-01', 35000, 'msrp'),
('B100 HGX', '2025-02-01', 35000, 'msrp'),
('B100 HGX', '2025-03-01', 34500, 'market'),
('B200 HGX', '2025-01-01', 40000, 'msrp'),
('B200 HGX', '2025-02-01', 40000, 'msrp'),
('B200 HGX', '2025-03-01', 40000, 'msrp'),
('RTX PRO 6000 BSE', '2025-01-01', 8500, 'msrp'),
('RTX PRO 6000 BSE', '2025-02-01', 8500, 'msrp'),
('RTX PRO 6000 BSE', '2025-03-01', 8500, 'market'),
('MI300X', '2025-01-01', 15000, 'market'),
('MI300X', '2025-02-01', 12000, 'market'),
('MI300X', '2025-03-01', 10500, 'market')
) AS t(name, date, price_usd, source)
JOIN gpus ON gpus.name = t.name;

-- =====================================================
-- Verification queries
-- =====================================================
SELECT 
    name,
    memory_gb,
    memory_type,
    bf16_tflops,
    fp8_tflops,
    supports_fp4,
    cooling_requirement,
    supported_workloads
FROM gpus 
ORDER BY 
    CASE 
        WHEN name LIKE 'H100%' THEN 1
        WHEN name LIKE 'H200%' THEN 2
        WHEN name LIKE 'B100%' THEN 3
        WHEN name LIKE 'B200%' THEN 4
        WHEN name LIKE 'B300%' THEN 5
        WHEN name LIKE 'GB200%' THEN 6
        WHEN name LIKE 'GB300%' THEN 7
        WHEN name = 'RTX PRO 6000 BSE' THEN 8
        WHEN name = 'MI300X' THEN 9
        WHEN name = 'MI350X' THEN 10
        WHEN name = 'MI355X' THEN 11
    END;

SELECT COUNT(*) as total_gpus FROM gpus;
SELECT COUNT(*) as total_availability FROM availability;
SELECT COUNT(*) as total_benchmarks FROM benchmarks;
SELECT COUNT(*) as total_price_history FROM price_history;
