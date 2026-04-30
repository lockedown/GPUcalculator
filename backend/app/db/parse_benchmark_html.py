"""Parse Finance GPU Benchmark Matrix HTML into structured data for DB seeding."""

import re
from pathlib import Path
from dataclasses import dataclass, field

from bs4 import BeautifulSoup


@dataclass
class GPUSpec:
    name: str
    vendor: str
    hbm_capacity_gb: float = 0
    hbm_type: str = ""
    mem_bandwidth_tb_s: float = 0
    bf16_tflops: float = 0
    fp64_tflops: float = 0
    is_estimated: bool = False
    interconnect: str = ""
    interconnect_bw_gb_s: float = 0
    form_factor: str = "SXM"


@dataclass
class BenchmarkScore:
    gpu_index: int  # Column index in the table (0-based among GPU columns)
    rating: str = ""
    bar_pct: float = 0
    metric_value: str = ""
    metric_numeric: float | None = None
    metric_unit: str = ""


@dataclass
class BenchmarkRow:
    name: str
    category: str
    workload_description: str = ""
    metric_description: str = ""
    scores: list[BenchmarkScore] = field(default_factory=list)


@dataclass
class GPUVerdict:
    gpu_name: str
    verdict_text: str = ""
    spec_text: str = ""
    strengths: list[str] = field(default_factory=list)


# Map HTML-parsed GPU names to canonical names used in seed.py / calibration / DB.
# B100 still maps to its canonical form so it can be filtered via EXCLUDED_GPUS.
HTML_TO_CANONICAL: dict[str, str] = {
    "H200 SXM5": "H200 SXM",
    "B100 SXM": "B100 HGX",
    "B200 SXM": "B200 HGX",
    "B300 SXM": "B300 HGX",
}

# GPU column order in the HTML table (canonical names).
# B100 is parsed but skipped at seed time — see EXCLUDED_GPUS.
GPU_COLUMN_ORDER = [
    "H200 SXM",
    "B100 HGX",
    "B200 HGX",
    "B300 HGX",
    "GB200 NVL72",
    "GB300 NVL72",
    "MI300X",
    "MI350X",
    "MI355X",
]

# GPUs intentionally excluded from the platform (parsed from HTML but not seeded).
EXCLUDED_GPUS: set[str] = {"B100 HGX"}

RATING_CLASS_MAP = {
    "r-baseline": "Baseline",
    "r-limited": "Limited",
    "r-capable": "Capable",
    "r-strong": "Strong",
    "r-best": "Best",
    "r-amd": "Capable",
    "r-amd2": "Strong",
    "r-amd3": "Strong",
}


def parse_numeric(text: str) -> tuple[float | None, str]:
    """Extract numeric value and unit from metric text like '~45K tok/s' or '67 TFLOPS'."""
    if not text:
        return None, ""

    cleaned = text.strip()
    cleaned = cleaned.replace("est.", "").replace("Ref.", "").strip()
    cleaned = re.sub(r"^~", "", cleaned)

    # Handle multiplier format like "~1.5× H200"
    mult_match = re.match(r"([\d.]+)×", cleaned)
    if mult_match:
        return float(mult_match.group(1)), "multiplier"

    # Handle "No FP8" or "N/A" type values
    if re.match(r"^(No |N/A|FP8 partial)", cleaned):
        return None, ""

    # Handle NVLink/fabric formats like "NVL4: 900 GB/s"
    fabric_match = re.match(r"(?:NVL\d+|IF v\d+):\s*([\d.]+)\s*(TB/s|GB/s)", cleaned)
    if fabric_match:
        val = float(fabric_match.group(1))
        unit = fabric_match.group(2)
        return val, unit

    # Standard numeric extraction
    num_match = re.match(r"([\d.]+)\s*(K|M|PF|G)?\s*(.*)", cleaned)
    if num_match:
        val = float(num_match.group(1))
        multiplier = num_match.group(2) or ""
        unit = num_match.group(3).strip()

        if multiplier == "K":
            val *= 1000
        elif multiplier == "M":
            val *= 1_000_000
        elif multiplier == "G":
            val *= 1_000_000_000
        elif multiplier == "PF":
            val *= 1000  # PetaFLOPS → TeraFLOPS
            unit = "TFLOPS" if not unit else unit

        # Clean up unit
        unit = unit.strip(" ·()")
        if not unit:
            # Try to infer from context
            if "tok" in text.lower():
                unit = "tok/s"
            elif "TFLOPS" in text or "GFLOPS" in text:
                unit = "TFLOPS"
            elif "TB/s" in text:
                unit = "TB/s"
            elif "GB/s" in text:
                unit = "GB/s"
            elif "ops/s" in text.lower():
                unit = "ops/s"

        return val, unit

    return None, ""


def parse_gpu_legend(soup: BeautifulSoup) -> list[GPUSpec]:
    """Extract GPU specs from the .gpu-chip legend elements."""
    specs = []
    chips = soup.select(".gpu-chip")

    for chip in chips:
        name_el = chip.select_one("span:not(.gpu-sub):not(.est-badge)")
        sub_el = chip.select_one(".gpu-sub")
        est_el = chip.select_one(".est-badge")

        if not name_el:
            continue

        raw_name = name_el.get_text(strip=True)
        name = HTML_TO_CANONICAL.get(raw_name, raw_name)
        sub_text = sub_el.get_text(strip=True) if sub_el else ""
        is_estimated = est_el is not None

        vendor = "AMD" if name.startswith("MI") else "NVIDIA"
        form_factor = "NVL72" if "NVL72" in name else ("HGX" if "HGX" in name else "SXM")

        spec = GPUSpec(
            name=name,
            vendor=vendor,
            is_estimated=is_estimated,
            form_factor=form_factor,
        )

        # Parse sub text: "141GB HBM3e · 4.8TB/s · 989 BF16 TFLOPS · 67 FP64"
        parts = [p.strip() for p in sub_text.split("·")]
        for part in parts:
            part = part.strip("~ ")

            # HBM capacity
            hbm_match = re.match(r"([\d.]+)\s*GB\s*(HBM\w*)?", part)
            if hbm_match:
                spec.hbm_capacity_gb = float(hbm_match.group(1))
                spec.hbm_type = hbm_match.group(2) or ""
                continue

            # Memory bandwidth
            bw_match = re.match(r"([\d.]+)\s*TB/s", part)
            if bw_match and "NVL72" not in part:
                spec.mem_bandwidth_tb_s = float(bw_match.group(1))
                continue

            # NVL72 fabric bandwidth
            nvl_match = re.match(r"NVL72\s+([\d.]+)\s*TB/s", part)
            if nvl_match:
                spec.interconnect = "NVL72"
                spec.interconnect_bw_gb_s = float(nvl_match.group(1)) * 1000
                continue

            # BF16 TFLOPS or PF
            bf16_match = re.match(r"([\d.]+)\s*(PF|TFLOPS)?\s*BF16", part)
            if bf16_match:
                val = float(bf16_match.group(1))
                unit = bf16_match.group(2) or ""
                if unit == "PF" or val < 10:  # PetaFLOPS
                    val *= 1000
                spec.bf16_tflops = val
                continue

            # FP64
            fp64_match = re.match(r"([\d.]+)\s*(?:TFLOPS\s+)?FP64", part)
            if fp64_match:
                spec.fp64_tflops = float(fp64_match.group(1))
                continue

            # Rack-level BF16
            rack_bf16 = re.match(r"([\d.]+)\s*PF\s*BF16\s*\(rack\)", part)
            if rack_bf16:
                spec.bf16_tflops = float(rack_bf16.group(1)) * 1000
                continue

        specs.append(spec)

    return specs


def parse_benchmarks(soup: BeautifulSoup) -> list[BenchmarkRow]:
    """Extract benchmark data from the table rows."""
    rows = []
    current_category = ""

    tbody = soup.select_one("tbody")
    if not tbody:
        return rows

    for tr in tbody.find_all("tr"):
        # Section header
        if "section-header" in tr.get("class", []):
            header_text = tr.get_text(strip=True).lower()
            if "quantitative" in header_text:
                current_category = "quant"
            elif "risk" in header_text:
                current_category = "risk"
            elif "inference" in header_text or "ai" in header_text:
                current_category = "inference"
            elif "hpc" in header_text:
                current_category = "hpc"
            elif "trading" in header_text:
                current_category = "trading"
            elif "tokenization" in header_text or "tokenisation" in header_text:
                current_category = "tokenization"
            continue

        # Data row
        cat = tr.get("data-cat", "")
        if not cat:
            continue

        tds = tr.find_all("td")
        if len(tds) < 4:
            continue

        # First 3 columns: benchmark name, workload desc, metric
        name_td = tds[0]
        bench_name = name_td.get_text(strip=True)
        # Remove tag text
        tag = name_td.select_one(".tag")
        if tag:
            tag_text = tag.get_text(strip=True)
            bench_name = bench_name.replace(tag_text, "").strip()

        workload_desc = tds[1].get_text(strip=True) if len(tds) > 1 else ""
        metric_desc = tds[2].get_text(strip=True) if len(tds) > 2 else ""

        benchmark = BenchmarkRow(
            name=bench_name,
            category=cat,
            workload_description=workload_desc,
            metric_description=metric_desc,
        )

        # Score cells (columns 3 onwards)
        score_tds = [td for td in tds if "score-cell" in " ".join(td.get("class", []))]

        for i, score_td in enumerate(score_tds):
            score = BenchmarkScore(gpu_index=i)

            # Rating
            rating_el = score_td.select_one(".rating")
            if rating_el:
                rating_text = rating_el.get_text(strip=True)
                # Map to standard ratings
                classes = rating_el.get("class", [])
                for cls in classes:
                    if cls in RATING_CLASS_MAP:
                        # Use the text from the element for more accuracy
                        break
                score.rating = rating_text

            # Bar percentage
            fill_el = score_td.select_one(".score-fill")
            if fill_el:
                style = fill_el.get("style", "")
                width_match = re.search(r"width:\s*([\d.]+)%", style)
                if width_match:
                    score.bar_pct = float(width_match.group(1))

            # Metric value
            sub_el = score_td.select_one(".score-sub")
            if sub_el:
                score.metric_value = sub_el.get_text(strip=True)
                score.metric_numeric, score.metric_unit = parse_numeric(score.metric_value)

            benchmark.scores.append(score)

        rows.append(benchmark)

    return rows


def parse_verdicts(soup: BeautifulSoup) -> list[GPUVerdict]:
    """Extract verdict cards."""
    verdicts = []

    for card in soup.select(".summary-card"):
        label_el = card.select_one(".card-gpu-label")
        spec_el = card.select_one(".card-spec")
        verdict_el = card.select_one(".card-verdict")
        strength_els = card.select(".card-strengths li")

        if not label_el:
            continue

        raw_vname = label_el.get_text(strip=True)
        v = GPUVerdict(
            gpu_name=HTML_TO_CANONICAL.get(raw_vname, raw_vname),
            spec_text=spec_el.get_text(strip=True) if spec_el else "",
            verdict_text=verdict_el.get_text(strip=True) if verdict_el else "",
            strengths=[li.get_text(strip=True) for li in strength_els],
        )
        verdicts.append(v)

    return verdicts


def parse_html_file(html_path: str | Path) -> dict:
    """
    Parse the full HTML file and return structured data.

    Returns:
        {
            "gpu_specs": [GPUSpec, ...],
            "benchmarks": [BenchmarkRow, ...],
            "verdicts": [GPUVerdict, ...],
            "gpu_column_order": [str, ...],
        }
    """
    path = Path(html_path)
    html_content = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_content, "lxml")

    gpu_specs = parse_gpu_legend(soup)
    benchmarks = parse_benchmarks(soup)
    verdicts = parse_verdicts(soup)

    return {
        "gpu_specs": gpu_specs,
        "benchmarks": benchmarks,
        "verdicts": verdicts,
        "gpu_column_order": GPU_COLUMN_ORDER,
    }


if __name__ == "__main__":
    import json
    from app.config import settings

    data = parse_html_file(settings.BENCHMARK_HTML_PATH)

    print(f"Parsed {len(data['gpu_specs'])} GPUs:")
    for spec in data["gpu_specs"]:
        print(f"  {spec.name}: {spec.hbm_capacity_gb}GB, {spec.mem_bandwidth_tb_s}TB/s, {spec.bf16_tflops} BF16 TFLOPS")

    print(f"\nParsed {len(data['benchmarks'])} benchmarks:")
    for b in data["benchmarks"]:
        print(f"  [{b.category}] {b.name}: {len(b.scores)} GPU scores")

    print(f"\nParsed {len(data['verdicts'])} verdicts:")
    for v in data["verdicts"]:
        print(f"  {v.gpu_name}: {v.verdict_text[:80]}...")
