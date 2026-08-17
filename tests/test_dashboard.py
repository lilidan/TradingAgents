import json
from pathlib import Path

import pytest

from scripts.build_dashboard import change_label, extract_summary, main, parse_sentiment


@pytest.mark.unit
def test_parse_structured_sentiment_header():
    parsed = parse_sentiment(
        "**Overall Sentiment:** **Mildly Bullish** (Score: 6.3/10)\n"
        "**Confidence:** Medium\n"
    )
    assert parsed == {"band": "Mildly Bullish", "score": 6.3, "confidence": "medium"}


@pytest.mark.unit
def test_change_labels_are_user_facing():
    assert change_label(1.2) == "显著升温"
    assert change_label(-0.4) == "温和降温"
    assert change_label(0.1) == "基本稳定"
    assert change_label(None) == "首次记录"


@pytest.mark.unit
def test_summary_prefers_conclusion():
    report = "# 报告\n\n这是一段很长的普通内容，用于解释各个来源的详细信息并且提供足够多的文字。\n\n## 六、结论\n\n综合三源，当前舆情轻微看多，但机构警示与零售亢奋之间的分歧正在扩大，需要关注后续变化。"
    assert extract_summary(report).startswith("综合三源")


def _write_run(root: Path, ticker: str, day: str, score: float) -> None:
    run_dir = root / f"{ticker}_{day}"
    analyst_dir = run_dir / "1_analysts"
    analyst_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "ticker": ticker,
                "analysis_date": day,
                "asset_type": "stock",
                "decision": "Overweight",
            }
        ),
        encoding="utf-8",
    )
    sentiment = (
        f"**Overall Sentiment:** **Mildly Bullish** (Score: {score}/10)\n"
        "**Confidence:** Medium\n\n"
        "## 结论\n\n综合新闻和社区讨论，当前市场关注度较高，但多空观点仍然存在明显分歧，需要继续观察。"
    )
    (analyst_dir / "sentiment.md").write_text(sentiment, encoding="utf-8")
    (analyst_dir / "news.md").write_text("NEWS", encoding="utf-8")
    (analyst_dir / "market.md").write_text("MARKET", encoding="utf-8")
    (run_dir / "complete_report.md").write_text("REPORT", encoding="utf-8")


@pytest.mark.unit
def test_build_dashboard_compares_latest_two_runs(tmp_path):
    incoming = tmp_path / "incoming"
    assets = tmp_path / "assets"
    archive = tmp_path / "archive"
    output = tmp_path / "dist"
    assets.mkdir()
    (assets / "index.html").write_text("ok", encoding="utf-8")
    _write_run(incoming, "NVDA", "2026-08-15", 5.1)
    _write_run(incoming, "NVDA", "2026-08-17", 6.3)

    assert main(
        [
            "--incoming-root",
            str(incoming),
            "--archive-dir",
            str(archive),
            "--assets-dir",
            str(assets),
            "--output-dir",
            str(output),
            "--now",
            "2026-08-17T08:00:00Z",
        ]
    ) == 0

    payload = json.loads((output / "data/dashboard.json").read_text(encoding="utf-8"))
    nvda = payload["symbols"][0]
    assert nvda["ticker"] == "NVDA"
    assert nvda["sentiment"]["delta"] == 1.2
    assert nvda["sentiment"]["change_label"] == "显著升温"
    assert len(nvda["history"]) == 2
    assert (output / "reports/NVDA/2026-08-17/complete_report.md").exists()
