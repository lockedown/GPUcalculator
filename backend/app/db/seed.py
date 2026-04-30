"""Seed the database with GPU specs, networking, software stacks, availability, and benchmarks."""

from pathlib import Path

from sqlalchemy.orm import Session

from app.db.database import engine, Base, SessionLocal
from app.db.parse_benchmark_html import parse_html_file, GPU_COLUMN_ORDER, EXCLUDED_GPUS
from app.models import GPU, Benchmark, Networking, SoftwareStack, Availability, PriceHistory
from app.config import settings


# Manual data not in the HTML: TDP, pricing, cooling, interconnect details
GPU_EXTRA_DATA = {
    "H100 SXM5": {
        # Spec-equivalent fields (H100 is not in the parsed HTML, so seed.py
        # builds the GPU row entirely from this dict). See _build_gpu_from_extra.
        "vendor": "NVIDIA",
        "form_factor": "SXM5",
        "hbm_capacity_gb": 80,
        "hbm_type": "HBM3",
        "mem_bandwidth_tb_s": 3.35,
        "bf16_tflops": 989,   # NVIDIA dense BF16 (sparse is 1979)
        "fp64_tflops": 67,
        "is_estimated": False,
        # Manual / extras
        "generation": "Hopper",
        "memory_gb": 80,
        "memory_type": "HBM3",
        "memory_bandwidth_tbps": 3.35,
        "supports_fp4": False,
        "interconnect_type": "NVLink 4",
        "cooling_requirement": "Any",
        "supported_workloads": ["inference", "training", "fine-tuning"],
        "tdp_watts": 700,
        # 2026 SXM5 channel reality is $30-35k; was $25k at 2024 launch.
        "msrp_usd": 30000,
        "cooling_type": "air",
        "intra_node_interconnect": "NVLink 4",
        "interconnect_bw_gb_s": 900,
        "max_gpus_per_node": 8,
        "is_rack_scale": False,
        "fp8_tflops": 3960,
        "release_date": "2024-Q1",
    },
    "H200 SXM": {
        "generation": "Hopper",
        "memory_gb": 141,
        "memory_type": "HBM3e",
        "memory_bandwidth_tbps": 4.8,
        "supports_fp4": False,
        "interconnect_type": "NVLink 4",
        "cooling_requirement": "Any",
        "supported_workloads": ["inference", "training", "fine-tuning"],
        "tdp_watts": 700,
        "msrp_usd": 30000,
        "cooling_type": "air",
        "intra_node_interconnect": "NVLink 4",
        "interconnect_bw_gb_s": 900,
        "max_gpus_per_node": 8,
        "is_rack_scale": False,
        "fp8_tflops": 3960,  # Same Hopper compute die as H100
        "release_date": "2024-Q1",
    },
    "B200 HGX": {
        "generation": "Blackwell",
        "memory_gb": 192,
        "memory_type": "HBM3e",
        "memory_bandwidth_tbps": 8.0,
        "supports_fp4": True,
        "interconnect_type": "NVLink 5",
        "cooling_requirement": "Any",
        "supported_workloads": ["inference", "training", "fine-tuning"],
        "tdp_watts": 1000,
        "msrp_usd": 40000,
        "cooling_type": "air",
        "intra_node_interconnect": "NVLink 5",
        "interconnect_bw_gb_s": 1800,
        "max_gpus_per_node": 8,
        "is_rack_scale": False,
        "fp8_tflops": 4500,
        "fp4_tflops": 19000,
        "release_date": "2025-Q1",
    },
    "B300 HGX": {
        "generation": "Blackwell Ultra",
        "memory_gb": 288,
        "memory_type": "HBM3e",
        "memory_bandwidth_tbps": 8.0,
        "supports_fp4": True,
        "interconnect_type": "NVLink 5+",
        "cooling_requirement": "DLC",
        "supported_workloads": ["inference", "training", "fine-tuning"],
        "tdp_watts": 1200,
        "msrp_usd": 50000,
        "cooling_type": "liquid",
        "intra_node_interconnect": "NVLink 5+",
        "interconnect_bw_gb_s": 2000,
        "max_gpus_per_node": 8,
        "is_rack_scale": False,
        "fp8_tflops": 5600,
        "fp4_tflops": 15000,
        "release_date": "2026-Q1",
    },
    "GB200 NVL72": {
        "generation": "Blackwell",
        "memory_gb": 192,
        "memory_type": "HBM3e",
        "memory_bandwidth_tbps": 8.0,
        "supports_fp4": True,
        "interconnect_type": "NVLink 5",
        "cooling_requirement": "DLC",
        "supported_workloads": ["inference", "training", "fine-tuning"],
        "tdp_watts": 1200,
        # Per-GPU equivalent: rack pricing $3.0-3.4M / 72 GPUs ≈ $42-47k.
        "msrp_usd": 45000,
        "cooling_type": "liquid",
        "intra_node_interconnect": "NVLink 5 (NVL72)",
        "interconnect_bw_gb_s": 1800,
        "max_gpus_per_node": 72,
        "is_rack_scale": True,
        "rack_gpu_count": 72,
        "rack_fabric_bw_tb_s": 130,
        "fp8_tflops": 5000,
        "fp4_tflops": 20000,
        "release_date": "2025-Q2",
    },
    "GB300 NVL72": {
        "generation": "Blackwell Ultra",
        "memory_gb": 288,
        "memory_type": "HBM3e",
        "memory_bandwidth_tbps": 8.0,
        "supports_fp4": True,
        "interconnect_type": "NVLink 5+",
        "cooling_requirement": "DLC",
        "supported_workloads": ["inference", "training", "fine-tuning"],
        "tdp_watts": 1400,
        # Per-GPU equivalent: rack pricing $6.0-6.5M / 72 GPUs ≈ $83-90k.
        "msrp_usd": 75000,
        "cooling_type": "liquid",
        "intra_node_interconnect": "NVLink 5+ (NVL72)",
        "interconnect_bw_gb_s": 2000,
        "max_gpus_per_node": 72,
        "is_rack_scale": True,
        "rack_gpu_count": 72,
        "rack_fabric_bw_tb_s": 200,
        "fp8_tflops": 8000,
        "fp4_tflops": 25000,
        "release_date": "2026-H2",
    },
    "RTX PRO 6000 BSE": {
        # Spec-equivalent fields (not in parsed HTML — built via _build_gpu_from_extra)
        "vendor": "NVIDIA",
        "form_factor": "PCIe",
        "hbm_capacity_gb": 96,        # GDDR7 — same field reused
        "hbm_type": "GDDR7",
        "mem_bandwidth_tb_s": 1.6,
        "fp64_tflops": None,
        "is_estimated": False,
        # Manual / extras
        "generation": "Blackwell",
        "memory_gb": 96,
        "memory_type": "GDDR7",
        "memory_bandwidth_tbps": 1.6,
        "supports_fp4": True,
        "interconnect_type": "PCIe",
        "cooling_requirement": "Air",
        "supported_workloads": ["inference"],  # Inference ONLY
        "tdp_watts": 600,
        "msrp_usd": 8500,
        "cooling_type": "air",
        "intra_node_interconnect": "PCIe Gen 5 x16",
        "interconnect_bw_gb_s": 32,  # PCIe Gen 5 x16 ~32 GB/s
        "max_gpus_per_node": 8,
        "is_rack_scale": False,
        "bf16_tflops": 480,  # Estimated from Blackwell die + GDDR7 config
        "fp8_tflops": 960,  # ~2x BF16 via 5th-gen Tensor Cores
        "fp4_tflops": 6600,  # Akamai benchmark-derived
        "release_date": "2025-Q1",
    },
    "MI300X": {
        "generation": "Instinct MI300",
        "memory_gb": 192,
        "memory_type": "HBM3",
        "memory_bandwidth_tbps": 3.2,
        "supports_fp4": False,
        "interconnect_type": "IF v3",
        "cooling_requirement": "Any",
        "supported_workloads": ["inference", "training", "fine-tuning"],
        "tdp_watts": 750,
        "msrp_usd": 22000,
        "cooling_type": "air",
        "intra_node_interconnect": "Infinity Fabric v3",
        "interconnect_bw_gb_s": 896,
        "max_gpus_per_node": 8,
        "is_rack_scale": False,
        "fp8_tflops": None,  # Partial FP8 support
        "release_date": "2024-Q1",
    },
    "MI350X": {
        "generation": "Instinct MI350",
        "memory_gb": 256,
        "memory_type": "HBM3e",
        "memory_bandwidth_tbps": 6.0,
        "supports_fp4": False,
        "interconnect_type": "IF v4",
        "cooling_requirement": "Any",
        "supported_workloads": ["inference", "training", "fine-tuning"],
        "tdp_watts": 750,
        "msrp_usd": 28000,
        "cooling_type": "air",
        "intra_node_interconnect": "Infinity Fabric v4",
        "interconnect_bw_gb_s": 1500,
        "max_gpus_per_node": 8,
        "is_rack_scale": False,
        "fp8_tflops": 3600,
        "release_date": "2025-H2",
    },
    "MI355X": {
        "generation": "Instinct MI355",
        "memory_gb": 288,
        "memory_type": "HBM3e",
        "memory_bandwidth_tbps": 6.4,
        "supports_fp4": False,
        "interconnect_type": "IF v4",
        "cooling_requirement": "Any",
        "supported_workloads": ["inference", "training", "fine-tuning"],
        "tdp_watts": 750,
        # UBS: AMD MI350-series ~$25k post-67% price hike; MI355X scaled slightly higher.
        "msrp_usd": 26000,
        "cooling_type": "air",
        "intra_node_interconnect": "Infinity Fabric v4",
        "interconnect_bw_gb_s": 1600,
        "max_gpus_per_node": 8,
        "is_rack_scale": False,
        "fp8_tflops": 4000,
        "release_date": "2026-Q1",
    },
}

NETWORKING_DATA = [
    {"name": "NVLink 4 (H200)", "type": "NVLink4", "vendor": "NVIDIA", "generation": "Hopper", "bandwidth_gb_s": 900, "latency_us": 0.5, "is_inter_node": 0},
    {"name": "NVLink 5 (Blackwell)", "type": "NVLink5", "vendor": "NVIDIA", "generation": "Blackwell", "bandwidth_gb_s": 1800, "latency_us": 0.3, "is_inter_node": 0},
    {"name": "NVL72 Fabric (GB200)", "type": "NVL72", "vendor": "NVIDIA", "generation": "Blackwell", "bandwidth_gb_s": 130000, "latency_us": 0.2, "is_inter_node": 0, "notes": "Rack-scale unified fabric, 130TB/s aggregate"},
    {"name": "NVL72 Fabric (GB300)", "type": "NVL72", "vendor": "NVIDIA", "generation": "Blackwell+", "bandwidth_gb_s": 200000, "latency_us": 0.2, "is_inter_node": 0, "notes": "Rack-scale unified fabric, ~200TB/s aggregate (est.)"},
    {"name": "Infinity Fabric v3 (MI300X)", "type": "IF_v3", "vendor": "AMD", "generation": "MI300", "bandwidth_gb_s": 896, "latency_us": 0.8, "is_inter_node": 0},
    {"name": "Infinity Fabric v4 (MI350X/MI355X)", "type": "IF_v4", "vendor": "AMD", "generation": "MI350", "bandwidth_gb_s": 1500, "latency_us": 0.6, "is_inter_node": 0},
    {"name": "InfiniBand NDR 400G", "type": "IB_NDR", "vendor": "NVIDIA", "generation": "NDR", "bandwidth_gb_s": 50, "latency_us": 1.3, "is_inter_node": 1, "notes": "400Gb/s per port, standard backend network"},
    {"name": "InfiniBand XDR 800G", "type": "IB_XDR", "vendor": "NVIDIA", "generation": "XDR", "bandwidth_gb_s": 100, "latency_us": 1.0, "is_inter_node": 1, "notes": "800Gb/s per port, next-gen backend network"},
    {"name": "RoCEv2 400G", "type": "RoCEv2", "vendor": "Generic", "generation": "400G", "bandwidth_gb_s": 50, "latency_us": 2.0, "is_inter_node": 1, "notes": "RDMA over Converged Ethernet"},
    {"name": "Ultra Ethernet 800G", "type": "UEC", "vendor": "Generic", "generation": "800G", "bandwidth_gb_s": 100, "latency_us": 1.5, "is_inter_node": 1, "notes": "Ultra Ethernet Consortium standard"},
]

SOFTWARE_STACK_DATA = [
    {"gpu_vendor": "NVIDIA", "stack_name": "CUDA + TensorRT-LLM", "maturity_score": 9, "framework_support": "PyTorch, TensorFlow, JAX", "fp8_support_level": "full", "notes": "Mature, industry-standard. Full FP8 Transformer Engine on Blackwell."},
    {"gpu_vendor": "NVIDIA", "stack_name": "CUDA + Megatron-LM", "maturity_score": 8, "framework_support": "PyTorch", "fp8_support_level": "full", "notes": "NVIDIA's training framework for large-scale LLMs."},
    {"gpu_vendor": "NVIDIA", "stack_name": "CUDA + vLLM", "maturity_score": 8, "framework_support": "PyTorch", "fp8_support_level": "full", "notes": "Open-source, widely adopted for LLM serving."},
    {"gpu_vendor": "AMD", "stack_name": "ROCm + vLLM", "maturity_score": 6, "framework_support": "PyTorch", "fp8_support_level": "partial", "notes": "Rapidly improving. MI300X support mature; MI350X/MI355X FP8 expected."},
    {"gpu_vendor": "AMD", "stack_name": "ROCm + HIP", "maturity_score": 5, "framework_support": "PyTorch, TensorFlow", "fp8_support_level": "partial", "notes": "CUDA translation layer. Growing ecosystem but higher skills dependency."},
    {"gpu_vendor": "AMD", "stack_name": "ROCm + ONNX Runtime", "maturity_score": 6, "framework_support": "PyTorch, ONNX", "fp8_support_level": "partial", "notes": "Good for classical ML inference, improving for LLM workloads."},
]

AVAILABILITY_DATA = {
    "H100 SXM5": {"lead_time_weeks": 4, "supply_status": "available"},
    "H200 SXM": {"lead_time_weeks": 8, "supply_status": "available"},
    "B200 HGX": {"lead_time_weeks": 16, "supply_status": "constrained"},
    "B300 HGX": {"lead_time_weeks": 40, "supply_status": "announced"},
    "GB200 NVL72": {"lead_time_weeks": 24, "supply_status": "constrained"},
    "GB300 NVL72": {"lead_time_weeks": 52, "supply_status": "announced"},
    "RTX PRO 6000 BSE": {"lead_time_weeks": 8, "supply_status": "available"},
    "MI300X": {"lead_time_weeks": 6, "supply_status": "available"},
    "MI350X": {"lead_time_weeks": 20, "supply_status": "announced"},
    "MI355X": {"lead_time_weeks": 36, "supply_status": "announced"},
}


def _build_gpu_from_extra(name: str, extra: dict, verdict_text: str = "") -> GPU:
    """Build a GPU row from GPU_EXTRA_DATA only — used for GPUs that aren't in
    the parsed HTML benchmark file (currently H100 SXM5 and RTX PRO 6000 BSE).

    The extras dict must carry the spec-equivalent fields normally provided by
    the HTML parser: vendor, form_factor, hbm_capacity_gb, hbm_type,
    mem_bandwidth_tb_s, bf16_tflops, fp64_tflops, is_estimated.
    """
    return GPU(
        name=name,
        vendor=extra["vendor"],
        generation=extra.get("generation", "Unknown"),
        form_factor=extra.get("form_factor"),
        hbm_capacity_gb=extra.get("hbm_capacity_gb"),
        hbm_type=extra.get("hbm_type"),
        mem_bandwidth_tb_s=extra.get("mem_bandwidth_tb_s"),
        memory_gb=extra.get("memory_gb"),
        memory_type=extra.get("memory_type"),
        memory_bandwidth_tbps=extra.get("memory_bandwidth_tbps"),
        bf16_tflops=extra.get("bf16_tflops"),
        fp64_tflops=extra.get("fp64_tflops"),
        fp8_tflops=extra.get("fp8_tflops"),
        fp4_tflops=extra.get("fp4_tflops"),
        supports_fp4=extra.get("supports_fp4"),
        tdp_watts=extra.get("tdp_watts"),
        cooling_type=extra.get("cooling_type", "air"),
        intra_node_interconnect=extra.get("intra_node_interconnect"),
        interconnect_bw_gb_s=extra.get("interconnect_bw_gb_s"),
        interconnect_type=extra.get("interconnect_type"),
        cooling_requirement=extra.get("cooling_requirement"),
        supported_workloads=extra.get("supported_workloads"),
        max_gpus_per_node=extra.get("max_gpus_per_node", 8),
        is_rack_scale=extra.get("is_rack_scale", False),
        rack_gpu_count=extra.get("rack_gpu_count"),
        rack_fabric_bw_tb_s=extra.get("rack_fabric_bw_tb_s"),
        msrp_usd=extra.get("msrp_usd"),
        is_estimated=extra.get("is_estimated", False),
        release_date=extra.get("release_date"),
        verdict=verdict_text,
    )


def seed_gpus(db: Session, parsed_data: dict) -> dict[str, GPU]:
    """Seed GPUs from parsed HTML specs + manual extra data. Returns name→GPU mapping.

    Two paths:
      1. HTML-driven — for each GPU column in the benchmark HTML, merge the
         parsed spec with GPU_EXTRA_DATA.
      2. Extra-only — GPUs in GPU_EXTRA_DATA that the HTML doesn't carry
         (H100 SXM5, RTX PRO 6000 BSE) are built from the extras dict alone.
         This brings the test seed in line with neon_update.sql / production.
    """
    gpu_map = {}
    gpu_specs = parsed_data["gpu_specs"]
    verdicts = {v.gpu_name: v for v in parsed_data["verdicts"]}

    for spec in gpu_specs:
        if spec.name in EXCLUDED_GPUS:
            continue
        extra = GPU_EXTRA_DATA.get(spec.name, {})
        verdict = verdicts.get(spec.name)

        # Merge verdict texts
        verdict_text = ""
        if verdict:
            parts = []
            if verdict.verdict_text:
                parts.append(verdict.verdict_text)
            if verdict.strengths:
                parts.append("Strengths: " + "; ".join(verdict.strengths))
            verdict_text = " | ".join(parts)

        gpu = GPU(
            name=spec.name,
            vendor=spec.vendor,
            generation=extra.get("generation", "Unknown"),
            form_factor=spec.form_factor,
            hbm_capacity_gb=spec.hbm_capacity_gb,
            hbm_type=spec.hbm_type,
            mem_bandwidth_tb_s=spec.mem_bandwidth_tb_s,
            # New memory fields
            memory_gb=extra.get("memory_gb"),
            memory_type=extra.get("memory_type"),
            memory_bandwidth_tbps=extra.get("memory_bandwidth_tbps"),
            bf16_tflops=spec.bf16_tflops,
            fp64_tflops=spec.fp64_tflops,
            fp8_tflops=extra.get("fp8_tflops"),
            fp4_tflops=extra.get("fp4_tflops"),
            supports_fp4=extra.get("supports_fp4"),
            tdp_watts=extra.get("tdp_watts"),
            cooling_type=extra.get("cooling_type", "air"),
            intra_node_interconnect=extra.get("intra_node_interconnect", spec.interconnect),
            interconnect_bw_gb_s=extra.get("interconnect_bw_gb_s", spec.interconnect_bw_gb_s),
            # New interconnect and cooling fields
            interconnect_type=extra.get("interconnect_type"),
            cooling_requirement=extra.get("cooling_requirement"),
            supported_workloads=extra.get("supported_workloads"),
            max_gpus_per_node=extra.get("max_gpus_per_node", 8),
            is_rack_scale=extra.get("is_rack_scale", False),
            rack_gpu_count=extra.get("rack_gpu_count"),
            rack_fabric_bw_tb_s=extra.get("rack_fabric_bw_tb_s"),
            msrp_usd=extra.get("msrp_usd"),
            is_estimated=spec.is_estimated,
            release_date=extra.get("release_date"),
            verdict=verdict_text,
        )

        db.add(gpu)
        db.flush()
        gpu_map[spec.name] = gpu

    # Seed extras that aren't represented in the HTML (require "vendor" as a
    # marker that the entry has spec-equivalent fields filled in).
    for name, extra in GPU_EXTRA_DATA.items():
        if name in EXCLUDED_GPUS or name in gpu_map or "vendor" not in extra:
            continue
        gpu = _build_gpu_from_extra(name, extra)
        db.add(gpu)
        db.flush()
        gpu_map[name] = gpu

    return gpu_map


def seed_benchmarks(db: Session, parsed_data: dict, gpu_map: dict[str, GPU]):
    """Seed benchmark scores from parsed HTML."""
    column_order = parsed_data["gpu_column_order"]

    for bench_row in parsed_data["benchmarks"]:
        for score in bench_row.scores:
            if score.gpu_index >= len(column_order):
                continue

            gpu_name = column_order[score.gpu_index]
            if gpu_name in EXCLUDED_GPUS:
                continue
            gpu = gpu_map.get(gpu_name)
            if not gpu:
                continue

            benchmark = Benchmark(
                gpu_id=gpu.id,
                benchmark_name=bench_row.name,
                workload_category=bench_row.category,
                workload_description=bench_row.workload_description,
                rating=score.rating,
                bar_pct=score.bar_pct,
                metric_value=score.metric_value,
                metric_numeric=score.metric_numeric,
                metric_unit=score.metric_unit,
            )
            db.add(benchmark)


def seed_networking(db: Session):
    """Seed networking options."""
    for data in NETWORKING_DATA:
        net = Networking(**data)
        db.add(net)


def seed_software_stacks(db: Session):
    """Seed software stack data."""
    for data in SOFTWARE_STACK_DATA:
        stack = SoftwareStack(**data)
        db.add(stack)


def seed_availability(db: Session, gpu_map: dict[str, GPU]):
    """Seed availability data."""
    for gpu_name, data in AVAILABILITY_DATA.items():
        gpu = gpu_map.get(gpu_name)
        if not gpu:
            continue
        avail = Availability(gpu_id=gpu.id, **data)
        db.add(avail)


def seed_price_history(db: Session, gpu_map: dict[str, GPU]):
    """Seed historical GPU pricing data (quarterly estimates)."""
    from datetime import date

    # Historical pricing: (date, price_usd, source)
    # Prices reflect launch MSRP → market adjustments over time
    PRICE_DATA: dict[str, list[tuple[str, float, str]]] = {
        "H100 SXM5": [
            ("2024-01-01", 28000, "msrp"),
            ("2024-04-01", 26000, "market"),
            ("2024-07-01", 25000, "market"),
            ("2024-10-01", 24000, "market"),
            ("2025-01-01", 23000, "market"),
            ("2025-04-01", 22000, "market"),
        ],
        "H200 SXM": [
            ("2024-01-01", 32000, "msrp"),
            ("2024-04-01", 30000, "market"),
            ("2024-07-01", 29000, "market"),
            ("2024-10-01", 28000, "market"),
            ("2025-01-01", 27000, "market"),
            ("2025-04-01", 25000, "market"),
        ],
        "B200 HGX": [
            ("2024-10-01", 42000, "msrp"),
            ("2025-01-01", 41000, "market"),
            ("2025-04-01", 40000, "market"),
        ],
        "B300 HGX": [
            ("2025-01-01", 50000, "estimate"),
            ("2025-04-01", 50000, "estimate"),
        ],
        "GB200 NVL72": [
            ("2024-10-01", 2100000, "msrp"),
            ("2025-01-01", 2000000, "market"),
            ("2025-04-01", 1950000, "market"),
        ],
        "GB300 NVL72": [
            ("2025-01-01", 2500000, "estimate"),
            ("2025-04-01", 2500000, "estimate"),
        ],
        "RTX PRO 6000 BSE": [
            ("2025-01-01", 9000, "msrp"),
            ("2025-04-01", 8500, "market"),
        ],
        "MI300X": [
            ("2024-01-01", 15000, "msrp"),
            ("2024-04-01", 14500, "market"),
            ("2024-07-01", 13500, "market"),
            ("2024-10-01", 12500, "market"),
            ("2025-01-01", 11000, "market"),
            ("2025-04-01", 10000, "market"),
        ],
        "MI350X": [
            ("2025-01-01", 18000, "estimate"),
            ("2025-04-01", 18000, "estimate"),
        ],
        "MI355X": [
            ("2025-04-01", 22000, "estimate"),
        ],
    }

    count = 0
    for gpu_name, prices in PRICE_DATA.items():
        gpu = gpu_map.get(gpu_name)
        if not gpu:
            continue
        for date_str, price, source in prices:
            y, m, d = date_str.split("-")
            db.add(PriceHistory(
                gpu_id=gpu.id,
                date=date(int(y), int(m), int(d)),
                price_usd=price,
                source=source,
            ))
            count += 1
    print(f"  Seeded {count} price history records")


def run_seed():
    """Main seed function — drops and recreates all tables, then seeds."""
    print("Parsing HTML benchmark file...")
    parsed_data = parse_html_file(settings.BENCHMARK_HTML_PATH)
    print(f"  Found {len(parsed_data['gpu_specs'])} GPUs, {len(parsed_data['benchmarks'])} benchmarks, {len(parsed_data['verdicts'])} verdicts")

    print("Dropping and recreating tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        print("Seeding GPUs...")
        gpu_map = seed_gpus(db, parsed_data)
        print(f"  Seeded {len(gpu_map)} GPUs")

        print("Seeding benchmarks...")
        seed_benchmarks(db, parsed_data, gpu_map)

        print("Seeding networking...")
        seed_networking(db)

        print("Seeding software stacks...")
        seed_software_stacks(db)

        print("Seeding availability...")
        seed_availability(db, gpu_map)

        print("Seeding price history...")
        seed_price_history(db, gpu_map)

        db.commit()
        print("Seed complete!")

        # Summary
        print(f"\n--- Database Summary ---")
        print(f"  GPUs: {db.query(GPU).count()}")
        print(f"  Benchmarks: {db.query(Benchmark).count()}")
        print(f"  Networking: {db.query(Networking).count()}")
        print(f"  Software Stacks: {db.query(SoftwareStack).count()}")
        print(f"  Availability: {db.query(Availability).count()}")
        print(f"  Price History: {db.query(PriceHistory).count()}")

    except Exception as e:
        db.rollback()
        print(f"Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
