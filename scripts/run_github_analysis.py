"""Non-interactive TradingAgents entry point for GitHub Actions.

The upstream CLI is intentionally interactive.  This wrapper exposes the small
set of inputs needed by an unattended workflow, validates them before any paid
LLM call is made, and writes a report tree plus a compact run manifest.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime
from pathlib import Path

from cli.models import AssetType
from cli.utils import detect_asset_type, filter_analysts_for_asset_type, normalize_ticker_symbol
from tradingagents.dataflows.utils import safe_ticker_component
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.llm_clients.api_key_env import get_api_key_env

ANALYSTS = ("market", "social", "news", "fundamentals")
DEEPSEEK_DEFAULT_MODEL = "deepseek-v4-flash"


def _positive_rounds(value: str) -> int:
    rounds = int(value)
    if not 1 <= rounds <= 3:
        raise argparse.ArgumentTypeError("rounds must be between 1 and 3")
    return rounds


def _analysis_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc


def _analysts(value: str) -> list[str]:
    selected = [item.strip().lower() for item in value.split(",") if item.strip()]
    invalid = sorted(set(selected) - set(ANALYSTS))
    if invalid:
        raise argparse.ArgumentTypeError(f"unsupported analysts: {', '.join(invalid)}")
    if not selected:
        raise argparse.ArgumentTypeError("at least one analyst is required")
    return selected


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run TradingAgents without interactive prompts")
    parser.add_argument("--ticker", default="AAPL", help="Yahoo Finance ticker, e.g. AAPL or 0700.HK")
    parser.add_argument("--date", type=_analysis_date, default=date.today().isoformat())
    parser.add_argument("--provider", choices=("deepseek", "openrouter"), default="deepseek")
    parser.add_argument("--quick-model", default="")
    parser.add_argument("--deep-model", default="")
    parser.add_argument("--analysts", type=_analysts, default=list(ANALYSTS))
    parser.add_argument("--debate-rounds", type=_positive_rounds, default=1)
    parser.add_argument("--risk-rounds", type=_positive_rounds, default=1)
    parser.add_argument("--output-language", default="Chinese")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/reports"))
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs without calling APIs")
    return parser.parse_args(argv)


def resolve_models(provider: str, quick_model: str, deep_model: str) -> tuple[str, str]:
    quick_model = quick_model.strip()
    deep_model = deep_model.strip()
    if provider == "deepseek":
        return quick_model or DEEPSEEK_DEFAULT_MODEL, deep_model or DEEPSEEK_DEFAULT_MODEL
    if not quick_model or not deep_model:
        raise ValueError(
            "OpenRouter requires both --quick-model and --deep-model using OpenRouter model IDs"
        )
    return quick_model, deep_model


def require_api_key(provider: str) -> str:
    env_name = get_api_key_env(provider)
    if not env_name or not os.environ.get(env_name):
        raise RuntimeError(
            f"Missing {env_name or 'provider API key'}. Add it as a GitHub Actions repository secret."
        )
    return env_name


def _write_summary(report_file: Path, decision: str, manifest: dict) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    summary = (
        f"## TradingAgents: {manifest['ticker']}\n\n"
        f"- Date: `{manifest['analysis_date']}`\n"
        f"- Provider: `{manifest['provider']}`\n"
        f"- Models: `{manifest['quick_model']}` / `{manifest['deep_model']}`\n"
        f"- Report artifact: `{report_file}`\n\n"
        "### Decision\n\n"
        f"```text\n{decision}\n```\n"
    )
    with open(summary_path, "a", encoding="utf-8") as stream:
        stream.write(summary)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ticker = normalize_ticker_symbol(args.ticker)
    if not ticker:
        raise ValueError("ticker must not be empty")

    asset_type = detect_asset_type(ticker)
    selected = filter_analysts_for_asset_type(args.analysts, asset_type)
    selected_analysts = [
        analyst.value if hasattr(analyst, "value") else analyst for analyst in selected
    ]
    quick_model, deep_model = resolve_models(args.provider, args.quick_model, args.deep_model)

    run_name = f"{safe_ticker_component(ticker)}_{args.date}"
    report_dir = args.output_dir / run_name
    manifest = {
        "ticker": ticker,
        "analysis_date": args.date,
        "asset_type": asset_type.value if isinstance(asset_type, AssetType) else str(asset_type),
        "provider": args.provider,
        "quick_model": quick_model,
        "deep_model": deep_model,
        "analysts": selected_analysts,
        "debate_rounds": args.debate_rounds,
        "risk_rounds": args.risk_rounds,
        "output_language": args.output_language,
    }

    if args.dry_run:
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
        return 0

    require_api_key(args.provider)
    config = DEFAULT_CONFIG.copy()
    config.update(
        {
            "llm_provider": args.provider,
            "quick_think_llm": quick_model,
            "deep_think_llm": deep_model,
            "max_debate_rounds": args.debate_rounds,
            "max_risk_discuss_rounds": args.risk_rounds,
            "output_language": args.output_language,
            "checkpoint_enabled": True,
        }
    )

    graph = TradingAgentsGraph(selected_analysts, debug=False, config=config)
    final_state, decision = graph.propagate(ticker, args.date, asset_type=manifest["asset_type"])
    report_file = graph.save_reports(final_state, ticker, save_path=report_dir)

    manifest["decision"] = decision
    manifest["report_file"] = str(report_file)
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "run.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    _write_summary(report_file, decision, manifest)
    print(f"Analysis complete: {report_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
