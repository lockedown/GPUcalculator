"""Unit tests for the HTML benchmark parser."""

import pytest
from app.db.parse_benchmark_html import parse_html_file, parse_numeric
from app.config import settings


class TestParseNumeric:
    def test_plain_number(self):
        val, unit = parse_numeric("67 TFLOPS")
        assert val == pytest.approx(67.0)
        assert "TFLOPS" in unit

    def test_k_multiplier(self):
        val, unit = parse_numeric("~45K tok/s")
        assert val == pytest.approx(45000.0)

    def test_multiplier_format(self):
        val, unit = parse_numeric("~1.5× H200")
        assert val == pytest.approx(1.5)
        assert unit == "multiplier"

    def test_na_returns_none(self):
        val, unit = parse_numeric("N/A")
        assert val is None

    def test_approx_prefix(self):
        val, unit = parse_numeric("~18B ops/s")
        assert val == pytest.approx(18.0)

    def test_empty_string(self):
        val, unit = parse_numeric("")
        assert val is None


class TestParseHTMLFile:
    @pytest.fixture(scope="class")
    def parsed(self):
        return parse_html_file(settings.BENCHMARK_HTML_PATH)

    def test_extracts_9_gpus(self, parsed):
        assert len(parsed["gpu_specs"]) == 9

    def test_gpu_names(self, parsed):
        names = [s.name for s in parsed["gpu_specs"]]
        assert "H200 SXM5" in names
        assert "B200 SXM" in names
        assert "MI300X" in names
        assert "GB200 NVL72" in names

    def test_gpu_vendors(self, parsed):
        vendors = {s.vendor for s in parsed["gpu_specs"]}
        assert "NVIDIA" in vendors
        assert "AMD" in vendors

    def test_h200_specs(self, parsed):
        h200 = next(s for s in parsed["gpu_specs"] if s.name == "H200 SXM5")
        assert h200.hbm_capacity_gb == pytest.approx(141.0, rel=0.05)
        assert h200.mem_bandwidth_tb_s == pytest.approx(4.8, rel=0.05)
        assert h200.vendor == "NVIDIA"

    def test_mi300x_specs(self, parsed):
        mi = next(s for s in parsed["gpu_specs"] if s.name == "MI300X")
        assert mi.hbm_capacity_gb == pytest.approx(192.0, rel=0.05)
        assert mi.mem_bandwidth_tb_s == pytest.approx(5.3, rel=0.05)
        assert mi.vendor == "AMD"

    def test_estimated_gpus_flagged(self, parsed):
        est_names = [s.name for s in parsed["gpu_specs"] if s.is_estimated]
        assert "B300 SXM" in est_names or len(est_names) >= 2

    def test_benchmarks_extracted(self, parsed):
        assert len(parsed["benchmarks"]) >= 18  # At least 18 benchmark rows

    def test_benchmark_categories(self, parsed):
        cats = {b.category for b in parsed["benchmarks"]}
        assert "quant" in cats or "tokenization" in cats

    def test_benchmark_scores_per_row(self, parsed):
        for b in parsed["benchmarks"]:
            assert len(b.scores) > 0, f"Benchmark {b.name} has no scores"

    def test_verdicts_extracted(self, parsed):
        assert len(parsed["verdicts"]) > 0

    def test_column_order(self, parsed):
        assert len(parsed["gpu_column_order"]) == 9
        assert parsed["gpu_column_order"][0] == "H200 SXM5"
