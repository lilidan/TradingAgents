# Trading analysis workflow

The **Trading analysis** workflow runs TradingAgents non-interactively and uploads the
generated Markdown reports, JSON state logs, decision memory, and checkpoints as a
14-day GitHub Actions artifact.

## One-time setup

Add one of these repository secrets under **Settings → Secrets and variables → Actions**:

- `DEEPSEEK_API_KEY`
- `OPENROUTER_API_KEY`

Never put an API key in a workflow input, repository variable, source file, issue, or log.

## Run an analysis

Open **Actions → Trading analysis → Run workflow** and choose the inputs. DeepSeek can
leave both model fields blank; the workflow then uses `deepseek-v4-flash` for both roles.
OpenRouter requires explicit provider model IDs in both model fields.

The default depth is one debate round and one risk round to limit token cost. Increasing
either value increases LLM usage. The analysis step stops after 165 minutes, leaving up
to 15 minutes for artifact upload before the job-level timeout.

The manual workflow remains available for ad-hoc research.

## Sentiment dashboard

The **Sentiment dashboard** workflow runs the complete watchlist every two days, with at
most two tickers analyzed concurrently. Its watchlist is:

`NVDA, AMD, MU, SNDK, SKHY, MSFT, GOOG, TSM, LITE, NBIS, SPCX`

The schedule is evaluated at 06:20 Asia/Shanghai and is anchored to 2026-08-18. A manual
dispatch always runs immediately, regardless of the two-day cadence.

Each run stores a compact 370-day history on the `dashboard-data` branch. The static site
sorts tickers by the magnitude of sentiment-score change and treats technical analysis and
the portfolio rating as secondary detail.

Cloudflare Pages uses its Git integration rather than an API token. Configure the Pages
project once with production branch `dashboard-data`, no build command, and output directory
`site-dist`. Subsequent `dashboard-data` pushes publish automatically, so no Cloudflare
credential is stored in GitHub.
