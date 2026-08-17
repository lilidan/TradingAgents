import pytest

from scripts.run_github_analysis import parse_args, resolve_models


@pytest.mark.unit
def test_deepseek_uses_cost_conscious_defaults():
    assert resolve_models("deepseek", "", "") == (
        "deepseek-v4-flash",
        "deepseek-v4-flash",
    )


@pytest.mark.unit
def test_openrouter_requires_explicit_models():
    with pytest.raises(ValueError, match="requires both"):
        resolve_models("openrouter", "", "")


@pytest.mark.unit
def test_batch_arguments_validate_without_api_key():
    args = parse_args(
        [
            "--ticker",
            "0700.HK",
            "--date",
            "2026-08-15",
            "--analysts",
            "market,news",
            "--dry-run",
        ]
    )
    assert args.ticker == "0700.HK"
    assert args.date == "2026-08-15"
    assert args.analysts == ["market", "news"]


@pytest.mark.unit
def test_rounds_are_capped_to_control_cost():
    with pytest.raises(SystemExit):
        parse_args(["--debate-rounds", "4"])
