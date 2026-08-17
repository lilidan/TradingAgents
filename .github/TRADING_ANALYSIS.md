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

This workflow is manual-only by design. Add a schedule only after confirming the expected
LLM cost and desired ticker list.
