"""Archive TradingAgents runs and build the static sentiment-first dashboard."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

SENTIMENT_RE = re.compile(
    r"\*\*Overall Sentiment:\*\*\s*\*\*(?P<band>.+?)\*\*\s*"
    r"\(Score:\s*(?P<score>\d+(?:\.\d+)?)/10\)",
    re.IGNORECASE,
)
CONFIDENCE_RE = re.compile(r"\*\*Confidence:\*\*\s*(?P<confidence>\w+)", re.IGNORECASE)
MARKDOWN_RE = re.compile(r"[`*_>#|\[\]]")
CONFIDENCE_ZH = {"low": "低", "medium": "中", "high": "高"}

ARCHIVE_FILES = {
    "run.json": "run.json",
    "complete_report.md": "complete_report.md",
    "1_analysts/sentiment.md": "sentiment.md",
    "1_analysts/news.md": "news.md",
    "1_analysts/market.md": "market.md",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--incoming-root", type=Path, action="append", default=[])
    parser.add_argument("--archive-dir", type=Path, required=True)
    parser.add_argument("--assets-dir", type=Path, default=Path("dashboard"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--retention-days", type=int, default=370)
    parser.add_argument("--now", help="UTC timestamp override for deterministic tests")
    return parser.parse_args(argv)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def parse_sentiment(text: str) -> dict:
    sentiment = SENTIMENT_RE.search(text)
    confidence = CONFIDENCE_RE.search(text)
    return {
        "band": sentiment.group("band").strip() if sentiment else "",
        "score": float(sentiment.group("score")) if sentiment else None,
        "confidence": confidence.group("confidence").lower() if confidence else "",
    }


def _clean_markdown(text: str) -> str:
    text = re.sub(r"https?://\S+", "", text)
    text = MARKDOWN_RE.sub("", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -:：")


def extract_summary(text: str, limit: int = 260) -> str:
    """Prefer a conclusion section, then fall back to a substantive paragraph."""
    lines = text.splitlines()
    candidates: list[str] = []
    in_conclusion = False
    for line in lines:
        stripped = line.strip()
        if re.match(r"^#{1,4}\s+", stripped):
            title = re.sub(r"^#{1,4}\s+", "", stripped).lower()
            in_conclusion = any(word in title for word in ("结论", "总结", "conclusion", "summary"))
            continue
        cleaned = _clean_markdown(stripped)
        if in_conclusion and len(cleaned) >= 20:
            candidates.insert(0, cleaned)
            break
        if len(cleaned) >= 35 and not stripped.startswith("|"):
            candidates.append(cleaned)
    result = candidates[0] if candidates else ""
    return result if len(result) <= limit else result[: limit - 1].rstrip() + "…"


def change_label(delta: float | None) -> str:
    if delta is None:
        return "首次记录"
    if delta >= 0.8:
        return "显著升温"
    if delta >= 0.3:
        return "温和升温"
    if delta <= -0.8:
        return "显著降温"
    if delta <= -0.3:
        return "温和降温"
    return "基本稳定"


def archive_incoming(incoming_roots: list[Path], archive_dir: Path) -> int:
    count = 0
    for root in incoming_roots:
        if not root.exists():
            continue
        for manifest_path in root.rglob("run.json"):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                ticker = re.sub(r"[^A-Za-z0-9._-]", "_", str(manifest["ticker"]).upper())
                analysis_date = date.fromisoformat(str(manifest["analysis_date"])).isoformat()
            except (KeyError, ValueError, json.JSONDecodeError):
                continue
            destination = archive_dir / ticker / analysis_date
            destination.mkdir(parents=True, exist_ok=True)
            source_dir = manifest_path.parent
            for source_name, destination_name in ARCHIVE_FILES.items():
                source = source_dir / source_name
                if source.exists():
                    shutil.copy2(source, destination / destination_name)
            count += 1
    return count


def prune_archive(archive_dir: Path, cutoff: date) -> int:
    removed = 0
    if not archive_dir.exists():
        return removed
    for manifest_path in archive_dir.glob("*/*/run.json"):
        try:
            run_date = date.fromisoformat(manifest_path.parent.name)
        except ValueError:
            continue
        if run_date < cutoff:
            shutil.rmtree(manifest_path.parent)
            removed += 1
    return removed


def collect_runs(archive_dir: Path) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for manifest_path in archive_dir.glob("*/*/run.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            analysis_date = date.fromisoformat(str(manifest["analysis_date"])).isoformat()
        except (KeyError, ValueError, json.JSONDecodeError):
            continue
        report_dir = manifest_path.parent
        sentiment_text = _read(report_dir / "sentiment.md")
        sentiment = parse_sentiment(sentiment_text)
        grouped.setdefault(str(manifest["ticker"]).upper(), []).append(
            {
                "date": analysis_date,
                "asset_type": manifest.get("asset_type", ""),
                "rating": manifest.get("decision", ""),
                "sentiment": sentiment,
                "sentiment_text": sentiment_text,
                "news_text": _read(report_dir / "news.md"),
                "market_text": _read(report_dir / "market.md"),
                "report_dir": report_dir,
            }
        )
    for runs in grouped.values():
        runs.sort(key=lambda run: run["date"])
    return grouped


def build_payload(grouped: dict[str, list[dict]], generated_at: datetime) -> dict:
    symbols = []
    for ticker, runs in grouped.items():
        latest = runs[-1]
        current_score = latest["sentiment"]["score"]
        previous_score = runs[-2]["sentiment"]["score"] if len(runs) > 1 else None
        delta = None
        if current_score is not None and previous_score is not None:
            delta = round(current_score - previous_score, 1)
        confidence = latest["sentiment"]["confidence"]
        symbols.append(
            {
                "ticker": ticker,
                "asset_type": latest["asset_type"],
                "latest_date": latest["date"],
                "rating": latest["rating"],
                "sentiment": {
                    **latest["sentiment"],
                    "delta": delta,
                    "change_label": change_label(delta),
                    "confidence_zh": CONFIDENCE_ZH.get(confidence, confidence),
                    "summary": extract_summary(latest["sentiment_text"]),
                },
                "reports": {
                    "sentiment": latest["sentiment_text"],
                    "news": latest["news_text"],
                    "market": latest["market_text"],
                },
                "report_url": f"./reports/{ticker}/{latest['date']}/complete_report.md",
                "history": [
                    {
                        "date": run["date"],
                        "score": run["sentiment"]["score"],
                        "band": run["sentiment"]["band"],
                        "rating": run["rating"],
                    }
                    for run in reversed(runs)
                    if run["sentiment"]["score"] is not None
                ],
            }
        )
    symbols.sort(
        key=lambda item: (
            -(abs(item["sentiment"]["delta"]) if item["sentiment"]["delta"] is not None else -1),
            item["ticker"],
        )
    )
    beijing_time = generated_at.astimezone(timezone(timedelta(hours=8)))
    return {
        "generated_at": generated_at.isoformat(),
        "generated_at_display": (
            f"{beijing_time:%Y-%m-%d %H:%M}" + "（北京时间）"
        ),
        "symbols": symbols,
    }


def write_site(assets_dir: Path, output_dir: Path, archive_dir: Path, payload: dict) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(assets_dir, output_dir)
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "dashboard.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    reports_dir = output_dir / "reports"
    for item in payload["symbols"]:
        ticker = item["ticker"]
        for point in item["history"]:
            source = archive_dir / ticker / point["date"] / "complete_report.md"
            if source.exists():
                target_dir = reports_dir / ticker / point["date"]
                target_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target_dir / "complete_report.md")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = (
        datetime.fromisoformat(args.now.replace("Z", "+00:00"))
        if args.now
        else datetime.now(timezone.utc)
    )
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)
    args.archive_dir.mkdir(parents=True, exist_ok=True)
    archived = archive_incoming(args.incoming_root, args.archive_dir)
    cutoff = generated_at.date() - timedelta(days=args.retention_days)
    removed = prune_archive(args.archive_dir, cutoff)
    payload = build_payload(collect_runs(args.archive_dir), generated_at)
    write_site(args.assets_dir, args.output_dir, args.archive_dir, payload)
    print(
        f"Dashboard built: {len(payload['symbols'])} symbols, "
        f"{archived} incoming runs, {removed} expired runs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
