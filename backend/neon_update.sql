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
        ALTER TABLE gpus ADD COLUMN supported_workloads JSON;
    END IF;
    
    -- Add fp4_tflops column if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='gpus' AND column_name='fp4_tflops') THEN
        ALTER TABLE gpus ADD COLUMN fp4_tflops FLOAT;
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
('H100 SXM5', 'NVIDIA', 'Hopper', 'SXM5', 80, 'HBM3', 3.35, 80, 'HBM3', 3.35, 1750, NULL, 3960, NULL, false, 700, 'air', 'NVLink 4', 900, 'NVLink 4', 'Any', '["inference", "training", "fine-tuning"]', 8, false, NULL, NULL, 25000, false, '2024-Q1', NOW(), NOW()),
('H200 SXM', 'NVIDIA', 'Hopper', 'SXM', 141, 'HBM3e', 4.8, 141, 'HBM3e', 4.8, 1970, NULL, 3960, NULL, false, 700, 'air', 'NVLink 4', 900, 'NVLink 4', 'Any', '["inference", "training", "fine-tuning"]', 8, false, NULL, NULL, 30000, false, '2024-Q1', NOW(), NOW()),
-- NVIDIA Blackwell
('B100 HGX', 'NVIDIA', 'Blackwell', 'HGX', 192, 'HBM3e', 8.0, 192, 'HBM3e', 8.0, 1750, NULL, 3600, 14000, true, 700, 'air', 'NVLink 5', 1800, 'NVLink 5', 'Any', '["inference", "training", "fine-tuning"]', 8, false, NULL, NULL, 35000, false, '2025-Q1', NOW(), NOW()),
('B200 HGX', 'NVIDIA', 'Blackwell', 'HGX', 192, 'HBM3e', 8.0, 192, 'HBM3e', 8.0, 2250, NULL, 4500, 19000, true, 1000, 'air', 'NVLink 5', 1800, 'NVLink 5', 'Any', '["inference", "training", "fine-tuning"]', 8, false, NULL, NULL, 40000, false, '2025-Q1', NOW(), NOW()),
-- NVIDIA Blackwell Ultra
('B300 HGX', 'NVIDIA', 'Blackwell Ultra', 'HGX', 288, 'HBM3e', 8.0, 288, 'HBM3e', 8.0, 2250, NULL, 5600, 15000, true, 1200, 'liquid', 'NVLink 5+', 2000, 'NVLink 5+', 'DLC', '["inference", "training", "fine-tuning"]', 8, false, NULL, NULL, 50000, false, '2026-Q1', NOW(), NOW()),
-- NVIDIA Rack-Scale
('GB200 NVL72', 'NVIDIA', 'Blackwell', 'NVL72', 192, 'HBM3e', 8.0, 192, 'HBM3e', 8.0, 2250, NULL, 5000, 20000, true, 1200, 'liquid', 'NVLink 5 (NVL72)', 1800, 'NVLink 5', 'DLC', '["inference", "training", "fine-tuning"]', 72, true, 72, 130, 40000, false, '2025-Q2', NOW(), NOW()),
('GB300 NVL72', 'NVIDIA', 'Blackwell Ultra', 'NVL72', 288, 'HBM3e', 8.0, 288, 'HBM3e', 8.0, 2250, NULL, 8000, 25000, true, 1400, 'liquid', 'NVLink 5+ (NVL72)', 2000, 'NVLink 5+', 'DLC', '["inference", "training", "fine-tuning"]', 72, true, 72, 200, 55000, false, '2026-H2', NOW(), NOW()),
-- NVIDIA RTX PRO (inference only) — bf16_tflops=480, fp8=960 estimated
('RTX PRO 6000 BSE', 'NVIDIA', 'Blackwell', 'PCIe', 96, 'GDDR7', 1.6, 96, 'GDDR7', 1.6, 480, NULL, 960, 6600, true, 600, 'air', 'PCIe Gen 5 x16', 32, 'PCIe', 'Air', '["inference"]', 8, false, NULL, NULL, 8500, false, '2025-Q1', NOW(), NOW()),
-- AMD Instinct
('MI300X', 'AMD', 'Instinct MI300', 'OAM', 192, 'HBM3', 3.2, 192, 'HBM3', 3.2, 1300, NULL, NULL, NULL, false, 750, 'air', 'Infinity Fabric v3', 896, 'IF v3', 'Any', '["inference", "training", "fine-tuning"]', 8, false, NULL, NULL, 22000, false, '2024-Q1', NOW(), NOW()),
('MI350X', 'AMD', 'Instinct MI350', 'OAM', 256, 'HBM3e', 6.0, 256, 'HBM3e', 6.0, 1800, NULL, 3600, NULL, false, 750, 'air', 'Infinity Fabric v4', 1500, 'IF v4', 'Any', '["inference", "training", "fine-tuning"]', 8, false, NULL, NULL, 28000, false, '2025-H2', NOW(), NOW()),
('MI355X', 'AMD', 'Instinct MI355', 'OAM', 288, 'HBM3e', 6.4, 288, 'HBM3e', 6.4, 2000, NULL, 4000, NULL, false, 750, 'air', 'Infinity Fabric v4', 1600, 'IF v4', 'Any', '["inference", "training", "fine-tuning"]', 8, false, NULL, NULL, 32000, false, '2026-Q1', NOW(), NOW());

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

-- Verify the data was inserted
SELECT 
    name,
    memory_gb,
    memory_type,
    supports_fp4,
    cooling_requirement,
    supported_workloads
FROM gpus 
ORDER BY 
    CASE 
        WHEN name = 'RTX PRO 6000 BSE' THEN 1
        WHEN name LIKE 'H100%' THEN 2
        WHEN name LIKE 'H200%' THEN 3
        WHEN name LIKE 'B100%' THEN 4
        WHEN name LIKE 'B200%' THEN 5
        WHEN name LIKE 'B300%' THEN 6
        WHEN name LIKE 'GB200%' THEN 7
        WHEN name LIKE 'GB300%' THEN 8
    END;

SELECT COUNT(*) as total_gpus FROM gpus;
SELECT COUNT(*) as total_availability FROM availability;
