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
('H100 SXM5', 'NVIDIA', 'Hopper', 'SXM5', 80, 'HBM3', 3.35, 80, 'HBM3', 3.35, 1750, NULL, 3960, NULL, false, 700, 'air', 'NVLink 4', 900, 'NVLink 4', 'Any', '["inference", "training", "fine-tuning"]'::jsonb, 8, false, NULL, NULL, 30000, false, '2024-Q1', NOW(), NOW()),
('H200 SXM', 'NVIDIA', 'Hopper', 'SXM', 141, 'HBM3e', 4.8, 141, 'HBM3e', 4.8, 1970, NULL, 3960, NULL, false, 700, 'air', 'NVLink 4', 900, 'NVLink 4', 'Any', '["inference", "training", "fine-tuning"]'::jsonb, 8, false, NULL, NULL, 30000, false, '2024-Q1', NOW(), NOW()),
-- NVIDIA Blackwell
('B200 HGX', 'NVIDIA', 'Blackwell', 'HGX', 192, 'HBM3e', 8.0, 192, 'HBM3e', 8.0, 2250, NULL, 4500, 19000, true, 1000, 'air', 'NVLink 5', 1800, 'NVLink 5', 'Any', '["inference", "training", "fine-tuning"]'::jsonb, 8, false, NULL, NULL, 40000, false, '2025-Q1', NOW(), NOW()),
-- NVIDIA Blackwell Ultra
('B300 HGX', 'NVIDIA', 'Blackwell Ultra', 'HGX', 288, 'HBM3e', 8.0, 288, 'HBM3e', 8.0, 2250, NULL, 5600, 15000, true, 1200, 'liquid', 'NVLink 5+', 2000, 'NVLink 5+', 'DLC', '["inference", "training", "fine-tuning"]'::jsonb, 8, false, NULL, NULL, 50000, false, '2026-Q1', NOW(), NOW()),
-- NVIDIA Rack-Scale
('GB200 NVL72', 'NVIDIA', 'Blackwell', 'NVL72', 192, 'HBM3e', 8.0, 192, 'HBM3e', 8.0, 2250, NULL, 5000, 20000, true, 1200, 'liquid', 'NVLink 5 (NVL72)', 1800, 'NVLink 5', 'DLC', '["inference", "training", "fine-tuning"]'::jsonb, 72, true, 72, 130, 45000, false, '2025-Q2', NOW(), NOW()),
('GB300 NVL72', 'NVIDIA', 'Blackwell Ultra', 'NVL72', 288, 'HBM3e', 8.0, 288, 'HBM3e', 8.0, 2250, NULL, 8000, 25000, true, 1400, 'liquid', 'NVLink 5+ (NVL72)', 2000, 'NVLink 5+', 'DLC', '["inference", "training", "fine-tuning"]'::jsonb, 72, true, 72, 200, 75000, false, '2026-H2', NOW(), NOW()),
-- NVIDIA RTX PRO (inference only) — bf16_tflops=480, fp8=960 estimated
('RTX PRO 6000 BSE', 'NVIDIA', 'Blackwell', 'PCIe', 96, 'GDDR7', 1.6, 96, 'GDDR7', 1.6, 480, NULL, 960, 6600, true, 600, 'air', 'PCIe Gen 5 x16', 32, 'PCIe', 'Air', '["inference"]'::jsonb, 8, false, NULL, NULL, 8500, false, '2025-Q1', NOW(), NOW()),
-- AMD Instinct
('MI300X', 'AMD', 'Instinct MI300', 'OAM', 192, 'HBM3', 3.2, 192, 'HBM3', 3.2, 1300, NULL, NULL, NULL, false, 750, 'air', 'Infinity Fabric v3', 896, 'IF v3', 'Any', '["inference", "training", "fine-tuning"]'::jsonb, 8, false, NULL, NULL, 22000, false, '2024-Q1', NOW(), NOW()),
('MI350X', 'AMD', 'Instinct MI350', 'OAM', 256, 'HBM3e', 6.0, 256, 'HBM3e', 6.0, 1800, NULL, 3600, NULL, false, 750, 'air', 'Infinity Fabric v4', 1500, 'IF v4', 'Any', '["inference", "training", "fine-tuning"]'::jsonb, 8, false, NULL, NULL, 28000, false, '2025-H2', NOW(), NOW()),
('MI355X', 'AMD', 'Instinct MI355', 'OAM', 288, 'HBM3e', 6.4, 288, 'HBM3e', 6.4, 2000, NULL, 4000, NULL, false, 750, 'air', 'Infinity Fabric v4', 1600, 'IF v4', 'Any', '["inference", "training", "fine-tuning"]'::jsonb, 8, false, NULL, NULL, 26000, false, '2026-Q1', NOW(), NOW());

-- Insert availability data (all GPUs)
INSERT INTO availability (gpu_id, lead_time_weeks, supply_status) 
SELECT id, lead_time_weeks, supply_status FROM (VALUES
('H100 SXM5', 4, 'available'),
('H200 SXM', 8, 'available'),
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
SELECT id, t.date::date, price_usd, source FROM (VALUES
('H100 SXM5', '2025-04-01', 22000, 'market'),
('H200 SXM', '2025-04-01', 25000, 'market'),
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
SELECT g.id, t.benchmark_name, t.workload_category, t.workload_description, t.rating, t.bar_pct, t.metric_value, t.metric_numeric, t.metric_unit
FROM (VALUES
('H200 SXM', 'STAC-A2', 'quant', 'Tick analytics, options pricing (Black-Scholes), time-series aggregation on financial datasets', 'Baseline', 38, '~18B ops/s', 18, 'B ops/s'),
('B200 HGX', 'STAC-A2', 'quant', 'Tick analytics, options pricing (Black-Scholes), time-series aggregation on financial datasets', 'Strong', 62, '~36B ops/s', 36, 'B ops/s'),
('B300 HGX', 'STAC-A2', 'quant', 'Tick analytics, options pricing (Black-Scholes), time-series aggregation on financial datasets', 'Strong', 72, '~50B est.', 50, 'B'),
('GB200 NVL72', 'STAC-A2', 'quant', 'Tick analytics, options pricing (Black-Scholes), time-series aggregation on financial datasets', 'Best', 84, '~60B ops/s', 60, 'B ops/s'),
('GB300 NVL72', 'STAC-A2', 'quant', 'Tick analytics, options pricing (Black-Scholes), time-series aggregation on financial datasets', 'Best+', 96, '~90B est.', 90, 'B'),
('MI300X', 'STAC-A2', 'quant', 'Tick analytics, options pricing (Black-Scholes), time-series aggregation on financial datasets', 'Capable', 43, '~22B ops/s', 22, 'B ops/s'),
('MI350X', 'STAC-A2', 'quant', 'Tick analytics, options pricing (Black-Scholes), time-series aggregation on financial datasets', 'Strong', 59, '~34B est.', 34, 'B'),
('MI355X', 'STAC-A2', 'quant', 'Tick analytics, options pricing (Black-Scholes), time-series aggregation on financial datasets', 'Strong', 64, '~38B est.', 38, 'B'),
('H200 SXM', 'Monte Carlo FP64', 'quant', 'Path simulation for VaR, CVA, options — double-precision throughput-bound', 'Baseline', 36, '67 TFLOPS', 67, 'TFLOPS'),
('B200 HGX', 'Monte Carlo FP64', 'quant', 'Path simulation for VaR, CVA, options — double-precision throughput-bound', 'Strong', 60, '112 TFLOPS', 112, 'TFLOPS'),
('B300 HGX', 'Monte Carlo FP64', 'quant', 'Path simulation for VaR, CVA, options — double-precision throughput-bound', 'Best', 75, '~140 est.', 140, ''),
('GB200 NVL72', 'Monte Carlo FP64', 'quant', 'Path simulation for VaR, CVA, options — double-precision throughput-bound', 'Strong', 60, '90 TFLOPS/GPU', 90, 'TFLOPS/GPU'),
('GB300 NVL72', 'Monte Carlo FP64', 'quant', 'Path simulation for VaR, CVA, options — double-precision throughput-bound', 'Best+', 96, '~140 TFLOPS est.', 140, 'TFLOPS'),
('MI300X', 'Monte Carlo FP64', 'quant', 'Path simulation for VaR, CVA, options — double-precision throughput-bound', 'Capable', 45, '84 TFLOPS', 84, 'TFLOPS'),
('MI350X', 'Monte Carlo FP64', 'quant', 'Path simulation for VaR, CVA, options — double-precision throughput-bound', 'Strong', 58, '~108 est.', 108, ''),
('MI355X', 'Monte Carlo FP64', 'quant', 'Path simulation for VaR, CVA, options — double-precision throughput-bound', 'Strong', 63, '~116 est.', 116, ''),
('H200 SXM', 'cuBLAS / rocBLAS DGEMM', 'quant', 'Dense FP64 matrix multiply — covariance, factor calibration, portfolio optimisation, FINMA IMM', 'Baseline', 36, '67 TFLOPS', 67, 'TFLOPS'),
('B200 HGX', 'cuBLAS / rocBLAS DGEMM', 'quant', 'Dense FP64 matrix multiply — covariance, factor calibration, portfolio optimisation, FINMA IMM', 'Strong', 60, '112 TFLOPS', 112, 'TFLOPS'),
('B300 HGX', 'cuBLAS / rocBLAS DGEMM', 'quant', 'Dense FP64 matrix multiply — covariance, factor calibration, portfolio optimisation, FINMA IMM', 'Best', 75, '~140 est.', 140, ''),
('GB200 NVL72', 'cuBLAS / rocBLAS DGEMM', 'quant', 'Dense FP64 matrix multiply — covariance, factor calibration, portfolio optimisation, FINMA IMM', 'Strong', 60, '90 TFLOPS/GPU', 90, 'TFLOPS/GPU'),
('GB300 NVL72', 'cuBLAS / rocBLAS DGEMM', 'quant', 'Dense FP64 matrix multiply — covariance, factor calibration, portfolio optimisation, FINMA IMM', 'Best+', 96, '~140 TFLOPS est.', 140, 'TFLOPS'),
('MI300X', 'cuBLAS / rocBLAS DGEMM', 'quant', 'Dense FP64 matrix multiply — covariance, factor calibration, portfolio optimisation, FINMA IMM', 'Capable', 45, '84 TFLOPS', 84, 'TFLOPS'),
('MI350X', 'cuBLAS / rocBLAS DGEMM', 'quant', 'Dense FP64 matrix multiply — covariance, factor calibration, portfolio optimisation, FINMA IMM', 'Strong', 57, '~105 est.', 105, ''),
('MI355X', 'cuBLAS / rocBLAS DGEMM', 'quant', 'Dense FP64 matrix multiply — covariance, factor calibration, portfolio optimisation, FINMA IMM', 'Strong', 62, '~114 est.', 114, ''),
('H200 SXM', 'QuantLib GPU / XVA', 'risk', 'CVA/DVA/FVA computation, exposure profiles, netting sets — DORA Art.11 risk-critical', 'Baseline', 33, 'Ref.', NULL, ''),
('B200 HGX', 'QuantLib GPU / XVA', 'risk', 'CVA/DVA/FVA computation, exposure profiles, netting sets — DORA Art.11 risk-critical', 'Strong', 58, '~1.9× H200', 1.9, 'multiplier'),
('B300 HGX', 'QuantLib GPU / XVA', 'risk', 'CVA/DVA/FVA computation, exposure profiles, netting sets — DORA Art.11 risk-critical', 'Strong', 70, '~2.4× est.', 2.4, 'multiplier'),
('GB200 NVL72', 'QuantLib GPU / XVA', 'risk', 'CVA/DVA/FVA computation, exposure profiles, netting sets — DORA Art.11 risk-critical', 'Best', 82, '~3× H200', 3, 'multiplier'),
('GB300 NVL72', 'QuantLib GPU / XVA', 'risk', 'CVA/DVA/FVA computation, exposure profiles, netting sets — DORA Art.11 risk-critical', 'Best+', 96, '~4.5× est.', 4.5, 'multiplier'),
('MI300X', 'QuantLib GPU / XVA', 'risk', 'CVA/DVA/FVA computation, exposure profiles, netting sets — DORA Art.11 risk-critical', 'Capable', 42, '~1.3× H200', 1.3, 'multiplier'),
('MI350X', 'QuantLib GPU / XVA', 'risk', 'CVA/DVA/FVA computation, exposure profiles, netting sets — DORA Art.11 risk-critical', 'Strong', 57, '~1.8× est.', 1.8, 'multiplier'),
('MI355X', 'QuantLib GPU / XVA', 'risk', 'CVA/DVA/FVA computation, exposure profiles, netting sets — DORA Art.11 risk-critical', 'Strong', 62, '~2.0× est.', 2, 'multiplier'),
('H200 SXM', 'VaR / Stressed VaR Batch', 'risk', 'Historical simulation VaR, 10,000+ scenarios, FRTB IMA SA — EBA/MiFID II reporting', 'Baseline', 33, 'Ref.', NULL, ''),
('B200 HGX', 'VaR / Stressed VaR Batch', 'risk', 'Historical simulation VaR, 10,000+ scenarios, FRTB IMA SA — EBA/MiFID II reporting', 'Strong', 57, '~1.8× H200', 1.8, 'multiplier'),
('B300 HGX', 'VaR / Stressed VaR Batch', 'risk', 'Historical simulation VaR, 10,000+ scenarios, FRTB IMA SA — EBA/MiFID II reporting', 'Strong', 70, '~2.3× est.', 2.3, 'multiplier'),
('GB200 NVL72', 'VaR / Stressed VaR Batch', 'risk', 'Historical simulation VaR, 10,000+ scenarios, FRTB IMA SA — EBA/MiFID II reporting', 'Best', 82, '~2.8× H200', 2.8, 'multiplier'),
('GB300 NVL72', 'VaR / Stressed VaR Batch', 'risk', 'Historical simulation VaR, 10,000+ scenarios, FRTB IMA SA — EBA/MiFID II reporting', 'Best+', 96, '~4× est.', 4, 'multiplier'),
('MI300X', 'VaR / Stressed VaR Batch', 'risk', 'Historical simulation VaR, 10,000+ scenarios, FRTB IMA SA — EBA/MiFID II reporting', 'Capable', 42, '~1.3× H200', 1.3, 'multiplier'),
('MI350X', 'VaR / Stressed VaR Batch', 'risk', 'Historical simulation VaR, 10,000+ scenarios, FRTB IMA SA — EBA/MiFID II reporting', 'Strong', 56, '~1.7× est.', 1.7, 'multiplier'),
('MI355X', 'VaR / Stressed VaR Batch', 'risk', 'Historical simulation VaR, 10,000+ scenarios, FRTB IMA SA — EBA/MiFID II reporting', 'Strong', 61, '~1.9× est.', 1.9, 'multiplier'),
('H200 SXM', 'Stress Testing (DFAST/EBA)', 'risk', 'Macro scenario propagation through loan/trading book models — EBA annual cycle', 'Baseline', 33, 'Ref.', NULL, ''),
('B200 HGX', 'Stress Testing (DFAST/EBA)', 'risk', 'Macro scenario propagation through loan/trading book models — EBA annual cycle', 'Strong', 58, '~1.9× H200', 1.9, 'multiplier'),
('B300 HGX', 'Stress Testing (DFAST/EBA)', 'risk', 'Macro scenario propagation through loan/trading book models — EBA annual cycle', 'Strong', 70, '~2.4× est.', 2.4, 'multiplier'),
('GB200 NVL72', 'Stress Testing (DFAST/EBA)', 'risk', 'Macro scenario propagation through loan/trading book models — EBA annual cycle', 'Best', 82, '~2.8× H200', 2.8, 'multiplier'),
('GB300 NVL72', 'Stress Testing (DFAST/EBA)', 'risk', 'Macro scenario propagation through loan/trading book models — EBA annual cycle', 'Best+', 96, '~4× est.', 4, 'multiplier'),
('MI300X', 'Stress Testing (DFAST/EBA)', 'risk', 'Macro scenario propagation through loan/trading book models — EBA annual cycle', 'Capable', 41, '~1.3× H200', 1.3, 'multiplier'),
('MI350X', 'Stress Testing (DFAST/EBA)', 'risk', 'Macro scenario propagation through loan/trading book models — EBA annual cycle', 'Strong', 55, '~1.7× est.', 1.7, 'multiplier'),
('MI355X', 'Stress Testing (DFAST/EBA)', 'risk', 'Macro scenario propagation through loan/trading book models — EBA annual cycle', 'Strong', 60, '~1.9× est.', 1.9, 'multiplier'),
('H200 SXM', 'MLPerf Inference v4', 'inference', 'Llama2-70B, GPT-J, BERT-Large — server & offline, trade surveillance, comms NLP', 'Baseline', 27, '~22k tok/s', 22, 'k tok/s'),
('B200 HGX', 'MLPerf Inference v4', 'inference', 'Llama2-70B, GPT-J, BERT-Large — server & offline, trade surveillance, comms NLP', 'Strong', 52, '~52k tok/s', 52, 'k tok/s'),
('B300 HGX', 'MLPerf Inference v4', 'inference', 'Llama2-70B, GPT-J, BERT-Large — server & offline, trade surveillance, comms NLP', 'Strong', 63, '~68k est.', 68, 'k'),
('GB200 NVL72', 'MLPerf Inference v4', 'inference', 'Llama2-70B, GPT-J, BERT-Large — server & offline, trade surveillance, comms NLP', 'Best', 82, '~200k (rack)', 200, 'k (rack'),
('GB300 NVL72', 'MLPerf Inference v4', 'inference', 'Llama2-70B, GPT-J, BERT-Large — server & offline, trade surveillance, comms NLP', 'Best+', 97, '~320k est.', 320, 'k'),
('MI300X', 'MLPerf Inference v4', 'inference', 'Llama2-70B, GPT-J, BERT-Large — server & offline, trade surveillance, comms NLP', 'Capable', 37, '~26k tok/s', 26, 'k tok/s'),
('MI350X', 'MLPerf Inference v4', 'inference', 'Llama2-70B, GPT-J, BERT-Large — server & offline, trade surveillance, comms NLP', 'Strong', 50, '~42k est.', 42, 'k'),
('MI355X', 'MLPerf Inference v4', 'inference', 'Llama2-70B, GPT-J, BERT-Large — server & offline, trade surveillance, comms NLP', 'Strong', 56, '~50k est.', 50, 'k'),
('H200 SXM', 'vLLM / TRT-LLM Throughput', 'inference', 'Continuous batching LLM serving — regulatory filing analysis, client comms, AML NLP', 'Baseline', 27, '~4k tok/s/GPU', 4, 'k tok/s/GPU'),
('B200 HGX', 'vLLM / TRT-LLM Throughput', 'inference', 'Continuous batching LLM serving — regulatory filing analysis, client comms, AML NLP', 'Strong', 54, '~8.5k/GPU', 8.5, 'k/GPU'),
('B300 HGX', 'vLLM / TRT-LLM Throughput', 'inference', 'Continuous batching LLM serving — regulatory filing analysis, client comms, AML NLP', 'Strong', 65, '~11k est.', 11, 'k'),
('GB200 NVL72', 'vLLM / TRT-LLM Throughput', 'inference', 'Continuous batching LLM serving — regulatory filing analysis, client comms, AML NLP', 'Best', 80, '~9k tok/s/GPU', 9, 'k tok/s/GPU'),
('GB300 NVL72', 'vLLM / TRT-LLM Throughput', 'inference', 'Continuous batching LLM serving — regulatory filing analysis, client comms, AML NLP', 'Best+', 96, '~15k est.', 15, 'k'),
('MI300X', 'vLLM / TRT-LLM Throughput', 'inference', 'Continuous batching LLM serving — regulatory filing analysis, client comms, AML NLP', 'Capable', 37, '~3.5k/GPU', 3.5, 'k/GPU'),
('MI350X', 'vLLM / TRT-LLM Throughput', 'inference', 'Continuous batching LLM serving — regulatory filing analysis, client comms, AML NLP', 'Strong', 52, '~5.5k est.', 5.5, 'k'),
('MI355X', 'vLLM / TRT-LLM Throughput', 'inference', 'Continuous batching LLM serving — regulatory filing analysis, client comms, AML NLP', 'Strong', 57, '~6.5k est.', 6.5, 'k'),
('H200 SXM', 'ONNX RT / ROCm Inference', 'inference', 'Credit scoring, fraud, AML, KYC classification — SR 11-7 model validation environments', 'Strong', 55, 'Ref.', NULL, ''),
('B200 HGX', 'ONNX RT / ROCm Inference', 'inference', 'Credit scoring, fraud, AML, KYC classification — SR 11-7 model validation environments', 'Strong', 72, '~1.5× H200', 1.5, 'multiplier'),
('B300 HGX', 'ONNX RT / ROCm Inference', 'inference', 'Credit scoring, fraud, AML, KYC classification — SR 11-7 model validation environments', 'Best', 82, '~1.9× est.', 1.9, 'multiplier'),
('GB200 NVL72', 'ONNX RT / ROCm Inference', 'inference', 'Credit scoring, fraud, AML, KYC classification — SR 11-7 model validation environments', 'Strong', 72, '~1.5× H200', 1.5, 'multiplier'),
('GB300 NVL72', 'ONNX RT / ROCm Inference', 'inference', 'Credit scoring, fraud, AML, KYC classification — SR 11-7 model validation environments', 'Best+', 94, '~2.2× est.', 2.2, 'multiplier'),
('MI300X', 'ONNX RT / ROCm Inference', 'inference', 'Credit scoring, fraud, AML, KYC classification — SR 11-7 model validation environments', 'Capable', 50, '~1.1× H200', 1.1, 'multiplier'),
('MI350X', 'ONNX RT / ROCm Inference', 'inference', 'Credit scoring, fraud, AML, KYC classification — SR 11-7 model validation environments', 'Strong', 64, '~1.4× est.', 1.4, 'multiplier'),
('MI355X', 'ONNX RT / ROCm Inference', 'inference', 'Credit scoring, fraud, AML, KYC classification — SR 11-7 model validation environments', 'Strong', 68, '~1.5× est.', 1.5, 'multiplier'),
('H200 SXM', 'HPL / LINPACK', 'hpc', 'Dense FP64 FLOPS — actuarial (Solvency II), capital adequacy, FINMA IMM internal model', 'Baseline', 36, '67 TFLOPS', 67, 'TFLOPS'),
('B200 HGX', 'HPL / LINPACK', 'hpc', 'Dense FP64 FLOPS — actuarial (Solvency II), capital adequacy, FINMA IMM internal model', 'Strong', 60, '112 TFLOPS', 112, 'TFLOPS'),
('B300 HGX', 'HPL / LINPACK', 'hpc', 'Dense FP64 FLOPS — actuarial (Solvency II), capital adequacy, FINMA IMM internal model', 'Best', 75, '~140 est.', 140, ''),
('GB200 NVL72', 'HPL / LINPACK', 'hpc', 'Dense FP64 FLOPS — actuarial (Solvency II), capital adequacy, FINMA IMM internal model', 'Strong', 60, '90 TFLOPS/GPU', 90, 'TFLOPS/GPU'),
('GB300 NVL72', 'HPL / LINPACK', 'hpc', 'Dense FP64 FLOPS — actuarial (Solvency II), capital adequacy, FINMA IMM internal model', 'Best+', 96, '~140 TFLOPS est.', 140, 'TFLOPS'),
('MI300X', 'HPL / LINPACK', 'hpc', 'Dense FP64 FLOPS — actuarial (Solvency II), capital adequacy, FINMA IMM internal model', 'Capable', 45, '84 TFLOPS', 84, 'TFLOPS'),
('MI350X', 'HPL / LINPACK', 'hpc', 'Dense FP64 FLOPS — actuarial (Solvency II), capital adequacy, FINMA IMM internal model', 'Strong', 58, '~108 est.', 108, ''),
('MI355X', 'HPL / LINPACK', 'hpc', 'Dense FP64 FLOPS — actuarial (Solvency II), capital adequacy, FINMA IMM internal model', 'Strong', 62, '~116 est.', 116, ''),
('H200 SXM', 'HPCG (Sparse CG)', 'hpc', 'Sparse linear algebra — credit network graphs, interconnected counterparty exposure modelling', 'Baseline', 33, 'Ref.', NULL, ''),
('B200 HGX', 'HPCG (Sparse CG)', 'hpc', 'Sparse linear algebra — credit network graphs, interconnected counterparty exposure modelling', 'Strong', 62, '~2.1× H200', 2.1, 'multiplier'),
('B300 HGX', 'HPCG (Sparse CG)', 'hpc', 'Sparse linear algebra — credit network graphs, interconnected counterparty exposure modelling', 'Best', 79, '~3× est.', 3, 'multiplier'),
('GB200 NVL72', 'HPCG (Sparse CG)', 'hpc', 'Sparse linear algebra — credit network graphs, interconnected counterparty exposure modelling', 'Strong', 62, '~2.1× H200', 2.1, 'multiplier'),
('GB300 NVL72', 'HPCG (Sparse CG)', 'hpc', 'Sparse linear algebra — credit network graphs, interconnected counterparty exposure modelling', 'Best+', 96, '~3.5× est.', 3.5, 'multiplier'),
('MI300X', 'HPCG (Sparse CG)', 'hpc', 'Sparse linear algebra — credit network graphs, interconnected counterparty exposure modelling', 'Capable', 47, '~1.6× H200', 1.6, 'multiplier'),
('MI350X', 'HPCG (Sparse CG)', 'hpc', 'Sparse linear algebra — credit network graphs, interconnected counterparty exposure modelling', 'Strong', 62, '~2.1× est.', 2.1, 'multiplier'),
('MI355X', 'HPCG (Sparse CG)', 'hpc', 'Sparse linear algebra — credit network graphs, interconnected counterparty exposure modelling', 'Strong', 66, '~2.2× est.', 2.2, 'multiplier'),
('H200 SXM', 'STREAM (Memory BW)', 'hpc', 'Sustained HBM bandwidth — large portfolio streaming, factor data loading, time-series scan', 'Baseline', 30, '4.8 TB/s', 4.8, 'TB/s'),
('B200 HGX', 'STREAM (Memory BW)', 'hpc', 'Sustained HBM bandwidth — large portfolio streaming, factor data loading, time-series scan', 'Capable', 50, '8.0 TB/s', 8, 'TB/s'),
('B300 HGX', 'STREAM (Memory BW)', 'hpc', 'Sustained HBM bandwidth — large portfolio streaming, factor data loading, time-series scan', 'Best', 100, '~16 TB/s', 16, 'TB/s'),
('GB200 NVL72', 'STREAM (Memory BW)', 'hpc', 'Sustained HBM bandwidth — large portfolio streaming, factor data loading, time-series scan', 'Capable', 50, '8 TB/s/GPU', 8, 'TB/s/GPU'),
('GB300 NVL72', 'STREAM (Memory BW)', 'hpc', 'Sustained HBM bandwidth — large portfolio streaming, factor data loading, time-series scan', 'Best+', 100, '~16 TB/s/GPU', 16, 'TB/s/GPU'),
('MI300X', 'STREAM (Memory BW)', 'hpc', 'Sustained HBM bandwidth — large portfolio streaming, factor data loading, time-series scan', 'Capable', 33, '5.3 TB/s', 5.3, 'TB/s'),
('MI350X', 'STREAM (Memory BW)', 'hpc', 'Sustained HBM bandwidth — large portfolio streaming, factor data loading, time-series scan', 'Strong', 50, '~8 TB/s est.', 8, 'TB/s'),
('MI355X', 'STREAM (Memory BW)', 'hpc', 'Sustained HBM bandwidth — large portfolio streaming, factor data loading, time-series scan', 'Strong', 50, '~8 TB/s est.', 8, 'TB/s'),
('H200 SXM', 'GPU-Direct RDMA / FIO', 'trading', 'Storage-to-GPU bandwidth — tick history replay, EOD P&L recalc, MiFID II 5yr audit pipelines', 'Strong', 45, '~100 GB/s', 1e+11, 'B/s'),
('B200 HGX', 'GPU-Direct RDMA / FIO', 'trading', 'Storage-to-GPU bandwidth — tick history replay, EOD P&L recalc, MiFID II 5yr audit pipelines', 'Strong', 64, '~200 GB/s', 2e+11, 'B/s'),
('B300 HGX', 'GPU-Direct RDMA / FIO', 'trading', 'Storage-to-GPU bandwidth — tick history replay, EOD P&L recalc, MiFID II 5yr audit pipelines', 'Best', 80, '~300 GB/s est.', 3e+11, 'B/s'),
('GB200 NVL72', 'GPU-Direct RDMA / FIO', 'trading', 'Storage-to-GPU bandwidth — tick history replay, EOD P&L recalc, MiFID II 5yr audit pipelines', 'Strong', 64, '~200 GB/s', 2e+11, 'B/s'),
('GB300 NVL72', 'GPU-Direct RDMA / FIO', 'trading', 'Storage-to-GPU bandwidth — tick history replay, EOD P&L recalc, MiFID II 5yr audit pipelines', 'Best+', 96, '~400 GB/s est.', 4e+11, 'B/s'),
('MI300X', 'GPU-Direct RDMA / FIO', 'trading', 'Storage-to-GPU bandwidth — tick history replay, EOD P&L recalc, MiFID II 5yr audit pipelines', 'Capable', 40, '~90 GB/s', 9e+10, 'B/s'),
('MI350X', 'GPU-Direct RDMA / FIO', 'trading', 'Storage-to-GPU bandwidth — tick history replay, EOD P&L recalc, MiFID II 5yr audit pipelines', 'Strong', 56, '~155 GB/s est.', 1.55e+11, 'B/s'),
('MI355X', 'GPU-Direct RDMA / FIO', 'trading', 'Storage-to-GPU bandwidth — tick history replay, EOD P&L recalc, MiFID II 5yr audit pipelines', 'Strong', 62, '~175 GB/s est.', 1.75e+11, 'B/s'),
('H200 SXM', 'Interconnect BW (NVLink / Infinity Fabric)', 'trading', 'Peer-to-peer GPU fabric bandwidth — model parallelism for trading signal ensembles and large risk models', 'Limited', 18, 'NVL4: 900 GB/s', 900, 'GB/s'),
('B200 HGX', 'Interconnect BW (NVLink / Infinity Fabric)', 'trading', 'Peer-to-peer GPU fabric bandwidth — model parallelism for trading signal ensembles and large risk models', 'Capable', 30, 'NVL5: 1.8 TB/s', 1.8, 'TB/s'),
('B300 HGX', 'Interconnect BW (NVLink / Infinity Fabric)', 'trading', 'Peer-to-peer GPU fabric bandwidth — model parallelism for trading signal ensembles and large risk models', 'Strong', 40, 'NVL5+: ~2 TB/s', NULL, ''),
('GB200 NVL72', 'Interconnect BW (NVLink / Infinity Fabric)', 'trading', 'Peer-to-peer GPU fabric bandwidth — model parallelism for trading signal ensembles and large risk models', 'Best', 88, 'NVL72: 130 TB/s', 130, 'TB/s'),
('GB300 NVL72', 'Interconnect BW (NVLink / Infinity Fabric)', 'trading', 'Peer-to-peer GPU fabric bandwidth — model parallelism for trading signal ensembles and large risk models', 'Best+', 99, 'NVL72: ~200 TB/s', NULL, ''),
('MI300X', 'Interconnect BW (NVLink / Infinity Fabric)', 'trading', 'Peer-to-peer GPU fabric bandwidth — model parallelism for trading signal ensembles and large risk models', 'Limited', 22, 'IF v3: 896 GB/s', 896, 'GB/s'),
('MI350X', 'Interconnect BW (NVLink / Infinity Fabric)', 'trading', 'Peer-to-peer GPU fabric bandwidth — model parallelism for trading signal ensembles and large risk models', 'Strong', 33, 'IF v4: ~1.5 TB/s', NULL, ''),
('MI355X', 'Interconnect BW (NVLink / Infinity Fabric)', 'trading', 'Peer-to-peer GPU fabric bandwidth — model parallelism for trading signal ensembles and large risk models', 'Strong', 36, 'IF v4: ~1.6 TB/s', NULL, ''),
('H200 SXM', 'Prefill Throughput', 'tokenization', 'Prompt ingestion rate — regulatory document analysis, long-form contract NLP, FRTB/DORA policy parsing at scale', 'Baseline', 28, '~18K tok/s', 18000, 'tok/s'),
('B200 HGX', 'Prefill Throughput', 'tokenization', 'Prompt ingestion rate — regulatory document analysis, long-form contract NLP, FRTB/DORA policy parsing at scale', 'Strong', 58, '~45K tok/s', 45000, 'tok/s'),
('B300 HGX', 'Prefill Throughput', 'tokenization', 'Prompt ingestion rate — regulatory document analysis, long-form contract NLP, FRTB/DORA policy parsing at scale', 'Best', 78, '~70K tok/s est.', 70000, 'tok/s'),
('GB200 NVL72', 'Prefill Throughput', 'tokenization', 'Prompt ingestion rate — regulatory document analysis, long-form contract NLP, FRTB/DORA policy parsing at scale', 'Best', 88, '~82K tok/s rack', 82000, 'tok/s rack'),
('GB300 NVL72', 'Prefill Throughput', 'tokenization', 'Prompt ingestion rate — regulatory document analysis, long-form contract NLP, FRTB/DORA policy parsing at scale', 'Best+', 99, '~130K tok/s est.', 130000, 'tok/s'),
('MI300X', 'Prefill Throughput', 'tokenization', 'Prompt ingestion rate — regulatory document analysis, long-form contract NLP, FRTB/DORA policy parsing at scale', 'Capable', 32, '~22K tok/s', 22000, 'tok/s'),
('MI350X', 'Prefill Throughput', 'tokenization', 'Prompt ingestion rate — regulatory document analysis, long-form contract NLP, FRTB/DORA policy parsing at scale', 'Strong', 52, '~38K tok/s est.', 38000, 'tok/s'),
('MI355X', 'Prefill Throughput', 'tokenization', 'Prompt ingestion rate — regulatory document analysis, long-form contract NLP, FRTB/DORA policy parsing at scale', 'Strong', 60, '~46K tok/s est.', 46000, 'tok/s'),
('H200 SXM', 'Decode Throughput', 'tokenization', 'Autoregressive generation rate — real-time AML alert narratives, automated DORA incident reports, client advisory drafting, trade surveillance summaries', 'Baseline', 30, '~55 tok/s', 55, 'tok/s'),
('B200 HGX', 'Decode Throughput', 'tokenization', 'Autoregressive generation rate — real-time AML alert narratives, automated DORA incident reports, client advisory drafting, trade surveillance summaries', 'Strong', 60, '~115 tok/s', 115, 'tok/s'),
('B300 HGX', 'Decode Throughput', 'tokenization', 'Autoregressive generation rate — real-time AML alert narratives, automated DORA incident reports, client advisory drafting, trade surveillance summaries', 'Best', 80, '~170 tok/s est.', 170, 'tok/s'),
('GB200 NVL72', 'Decode Throughput', 'tokenization', 'Autoregressive generation rate — real-time AML alert narratives, automated DORA incident reports, client advisory drafting, trade surveillance summaries', 'Best', 88, '~200 tok/s', 200, 'tok/s'),
('GB300 NVL72', 'Decode Throughput', 'tokenization', 'Autoregressive generation rate — real-time AML alert narratives, automated DORA incident reports, client advisory drafting, trade surveillance summaries', 'Best+', 97, '~280 tok/s est.', 280, 'tok/s'),
('MI300X', 'Decode Throughput', 'tokenization', 'Autoregressive generation rate — real-time AML alert narratives, automated DORA incident reports, client advisory drafting, trade surveillance summaries', 'Capable', 38, '~70 tok/s', 70, 'tok/s'),
('MI350X', 'Decode Throughput', 'tokenization', 'Autoregressive generation rate — real-time AML alert narratives, automated DORA incident reports, client advisory drafting, trade surveillance summaries', 'Strong', 54, '~100 tok/s est.', 100, 'tok/s'),
('MI355X', 'Decode Throughput', 'tokenization', 'Autoregressive generation rate — real-time AML alert narratives, automated DORA incident reports, client advisory drafting, trade surveillance summaries', 'Strong', 62, '~118 tok/s est.', 118, 'tok/s'),
('H200 SXM', 'Batched Decode (BS=128)', 'tokenization', 'High-concurrency generation — parallel AML case processing, multi-analyst regulatory Q&A, concurrent trade commentary across desks', 'Baseline', 26, '~4.2K tok/s', 4200, 'tok/s'),
('B200 HGX', 'Batched Decode (BS=128)', 'tokenization', 'High-concurrency generation — parallel AML case processing, multi-analyst regulatory Q&A, concurrent trade commentary across desks', 'Strong', 58, '~10K tok/s', 10000, 'tok/s'),
('B300 HGX', 'Batched Decode (BS=128)', 'tokenization', 'High-concurrency generation — parallel AML case processing, multi-analyst regulatory Q&A, concurrent trade commentary across desks', 'Best', 80, '~16K tok/s est.', 16000, 'tok/s'),
('GB200 NVL72', 'Batched Decode (BS=128)', 'tokenization', 'High-concurrency generation — parallel AML case processing, multi-analyst regulatory Q&A, concurrent trade commentary across desks', 'Best', 90, '~19K tok/s', 19000, 'tok/s'),
('GB300 NVL72', 'Batched Decode (BS=128)', 'tokenization', 'High-concurrency generation — parallel AML case processing, multi-analyst regulatory Q&A, concurrent trade commentary across desks', 'Best+', 99, '~26K tok/s est.', 26000, 'tok/s'),
('MI300X', 'Batched Decode (BS=128)', 'tokenization', 'High-concurrency generation — parallel AML case processing, multi-analyst regulatory Q&A, concurrent trade commentary across desks', 'Capable', 36, '~5.8K tok/s', 5800, 'tok/s'),
('MI350X', 'Batched Decode (BS=128)', 'tokenization', 'High-concurrency generation — parallel AML case processing, multi-analyst regulatory Q&A, concurrent trade commentary across desks', 'Strong', 52, '~8.5K tok/s est.', 8500, 'tok/s'),
('MI355X', 'Batched Decode (BS=128)', 'tokenization', 'High-concurrency generation — parallel AML case processing, multi-analyst regulatory Q&A, concurrent trade commentary across desks', 'Strong', 60, '~10K tok/s est.', 10000, 'tok/s'),
('H200 SXM', 'KV Cache Capacity', 'tokenization', 'Concurrent context slots in VRAM — long-document analysis (ISDA agreements, prospectuses), extended regulatory dialogue, multi-turn audit assistant sessions', 'Baseline', 22, '~3 slots (141GB)', 3, 'slots (141GB'),
('B200 HGX', 'KV Cache Capacity', 'tokenization', 'Concurrent context slots in VRAM — long-document analysis (ISDA agreements, prospectuses), extended regulatory dialogue, multi-turn audit assistant sessions', 'Capable', 36, '~5 slots (192GB)', 5, 'slots (192GB'),
('B300 HGX', 'KV Cache Capacity', 'tokenization', 'Concurrent context slots in VRAM — long-document analysis (ISDA agreements, prospectuses), extended regulatory dialogue, multi-turn audit assistant sessions', 'Strong', 58, '~8 slots (288GB)', 8, 'slots (288GB'),
('GB200 NVL72', 'KV Cache Capacity', 'tokenization', 'Concurrent context slots in VRAM — long-document analysis (ISDA agreements, prospectuses), extended regulatory dialogue, multi-turn audit assistant sessions', 'Best', 96, '360+ slots (NVL72)', 360, '+ slots (NVL72'),
('GB300 NVL72', 'KV Cache Capacity', 'tokenization', 'Concurrent context slots in VRAM — long-document analysis (ISDA agreements, prospectuses), extended regulatory dialogue, multi-turn audit assistant sessions', 'Best+', 99, '600+ slots (NVL72)', 600, '+ slots (NVL72'),
('MI300X', 'KV Cache Capacity', 'tokenization', 'Concurrent context slots in VRAM — long-document analysis (ISDA agreements, prospectuses), extended regulatory dialogue, multi-turn audit assistant sessions', 'Capable', 36, '~5 slots (192GB)', 5, 'slots (192GB'),
('MI350X', 'KV Cache Capacity', 'tokenization', 'Concurrent context slots in VRAM — long-document analysis (ISDA agreements, prospectuses), extended regulatory dialogue, multi-turn audit assistant sessions', 'Strong', 58, '~8 slots (288GB)', 8, 'slots (288GB'),
('MI355X', 'KV Cache Capacity', 'tokenization', 'Concurrent context slots in VRAM — long-document analysis (ISDA agreements, prospectuses), extended regulatory dialogue, multi-turn audit assistant sessions', 'Strong', 58, '~8 slots (288GB)', 8, 'slots (288GB'),
('H200 SXM', 'Time-to-First-Token', 'tokenization', 'Prefill latency for 4K prompt — real-time trade surveillance alert triage, intraday risk NLP query response, latency-sensitive compliance workflows', 'Capable', 55, '~220ms', 220, 'ms'),
('B200 HGX', 'Time-to-First-Token', 'tokenization', 'Prefill latency for 4K prompt — real-time trade surveillance alert triage, intraday risk NLP query response, latency-sensitive compliance workflows', 'Strong', 75, '~110ms', 110, 'ms'),
('B300 HGX', 'Time-to-First-Token', 'tokenization', 'Prefill latency for 4K prompt — real-time trade surveillance alert triage, intraday risk NLP query response, latency-sensitive compliance workflows', 'Best', 88, '~75ms est.', 75, 'ms'),
('GB200 NVL72', 'Time-to-First-Token', 'tokenization', 'Prefill latency for 4K prompt — real-time trade surveillance alert triage, intraday risk NLP query response, latency-sensitive compliance workflows', 'Best', 92, '~60ms', 60, 'ms'),
('GB300 NVL72', 'Time-to-First-Token', 'tokenization', 'Prefill latency for 4K prompt — real-time trade surveillance alert triage, intraday risk NLP query response, latency-sensitive compliance workflows', 'Best+', 99, '~40ms est.', 40, 'ms'),
('MI300X', 'Time-to-First-Token', 'tokenization', 'Prefill latency for 4K prompt — real-time trade surveillance alert triage, intraday risk NLP query response, latency-sensitive compliance workflows', 'Capable', 48, '~180ms', 180, 'ms'),
('MI350X', 'Time-to-First-Token', 'tokenization', 'Prefill latency for 4K prompt — real-time trade surveillance alert triage, intraday risk NLP query response, latency-sensitive compliance workflows', 'Strong', 64, '~125ms est.', 125, 'ms'),
('MI355X', 'Time-to-First-Token', 'tokenization', 'Prefill latency for 4K prompt — real-time trade surveillance alert triage, intraday risk NLP query response, latency-sensitive compliance workflows', 'Strong', 70, '~105ms est.', 105, 'ms'),
('H200 SXM', 'Max Context Length', 'tokenization', 'Longest document processable in-VRAM without paging — full Basel IV framework analysis, complete MiFID II rulebook Q&A, entire loan agreement review in single pass', 'Capable', 30, '~96K tokens', 96000, 'tokens'),
('B200 HGX', 'Max Context Length', 'tokenization', 'Longest document processable in-VRAM without paging — full Basel IV framework analysis, complete MiFID II rulebook Q&A, entire loan agreement review in single pass', 'Strong', 48, '~160K tokens', 160000, 'tokens'),
('B300 HGX', 'Max Context Length', 'tokenization', 'Longest document processable in-VRAM without paging — full Basel IV framework analysis, complete MiFID II rulebook Q&A, entire loan agreement review in single pass', 'Best', 72, '~280K tokens est.', 280000, 'tokens'),
('GB200 NVL72', 'Max Context Length', 'tokenization', 'Longest document processable in-VRAM without paging — full Basel IV framework analysis, complete MiFID II rulebook Q&A, entire loan agreement review in single pass', 'Best', 94, '1M+ tokens (NVL72)', 1e+06, '+ tokens (NVL72'),
('GB300 NVL72', 'Max Context Length', 'tokenization', 'Longest document processable in-VRAM without paging — full Basel IV framework analysis, complete MiFID II rulebook Q&A, entire loan agreement review in single pass', 'Best+', 99, '2M+ tokens (NVL72)', 2e+06, '+ tokens (NVL72'),
('MI300X', 'Max Context Length', 'tokenization', 'Longest document processable in-VRAM without paging — full Basel IV framework analysis, complete MiFID II rulebook Q&A, entire loan agreement review in single pass', 'Capable', 48, '~160K tokens', 160000, 'tokens'),
('MI350X', 'Max Context Length', 'tokenization', 'Longest document processable in-VRAM without paging — full Basel IV framework analysis, complete MiFID II rulebook Q&A, entire loan agreement review in single pass', 'Strong', 72, '~280K tokens est.', 280000, 'tokens'),
('MI355X', 'Max Context Length', 'tokenization', 'Longest document processable in-VRAM without paging — full Basel IV framework analysis, complete MiFID II rulebook Q&A, entire loan agreement review in single pass', 'Strong', 72, '~280K tokens est.', 280000, 'tokens'),
('H200 SXM', 'FP8 Quantised Throughput', 'tokenization', 'Inference throughput at INT8/FP8 precision — maximising token volume for batch regulatory processing, overnight compliance report generation, cost-optimised AML screening', 'N/A', 10, 'No FP8 (H200)', NULL, ''),
('B200 HGX', 'FP8 Quantised Throughput', 'tokenization', 'Inference throughput at INT8/FP8 precision — maximising token volume for batch regulatory processing, overnight compliance report generation, cost-optimised AML screening', 'Strong', 76, '~1.9× vs FP16', 1.9, 'multiplier'),
('B300 HGX', 'FP8 Quantised Throughput', 'tokenization', 'Inference throughput at INT8/FP8 precision — maximising token volume for batch regulatory processing, overnight compliance report generation, cost-optimised AML screening', 'Best', 88, '~2.1× vs FP16 est.', 2.1, 'multiplier'),
('GB200 NVL72', 'FP8 Quantised Throughput', 'tokenization', 'Inference throughput at INT8/FP8 precision — maximising token volume for batch regulatory processing, overnight compliance report generation, cost-optimised AML screening', 'Best', 92, '~2.2× vs FP16', 2.2, 'multiplier'),
('GB300 NVL72', 'FP8 Quantised Throughput', 'tokenization', 'Inference throughput at INT8/FP8 precision — maximising token volume for batch regulatory processing, overnight compliance report generation, cost-optimised AML screening', 'Best+', 99, '~2.4× vs FP16 est.', 2.4, 'multiplier'),
('MI300X', 'FP8 Quantised Throughput', 'tokenization', 'Inference throughput at INT8/FP8 precision — maximising token volume for batch regulatory processing, overnight compliance report generation, cost-optimised AML screening', 'Limited', 22, 'FP8 partial support', NULL, ''),
('MI350X', 'FP8 Quantised Throughput', 'tokenization', 'Inference throughput at INT8/FP8 precision — maximising token volume for batch regulatory processing, overnight compliance report generation, cost-optimised AML screening', 'Strong', 66, '~1.7× est.', 1.7, 'multiplier'),
('MI355X', 'FP8 Quantised Throughput', 'tokenization', 'Inference throughput at INT8/FP8 precision — maximising token volume for batch regulatory processing, overnight compliance report generation, cost-optimised AML screening', 'Strong', 72, '~1.8× est.', 1.8, 'multiplier')
) AS t(gpu_name, benchmark_name, workload_category, workload_description, rating, bar_pct, metric_value, metric_numeric, metric_unit)
JOIN gpus g ON g.name = t.gpu_name;

-- =====================================================
-- Additional price history data (Q1–Q3 2025 trend)
-- =====================================================
INSERT INTO price_history (gpu_id, date, price_usd, source)
SELECT id, t.date::date, price_usd, source FROM (VALUES
('H100 SXM5', '2025-01-01', 30000, 'market'),
('H100 SXM5', '2025-02-01', 23500, 'market'),
('H100 SXM5', '2025-03-01', 22500, 'market'),
('H200 SXM', '2025-01-01', 30000, 'msrp'),
('H200 SXM', '2025-02-01', 28000, 'market'),
('H200 SXM', '2025-03-01', 26000, 'market'),
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
