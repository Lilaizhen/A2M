# A2M

A LangGraph/LangChain–based benchmark that runs multi-tool MCP agents on curated tasks, with optional adversarial tools to stress-test safety and robustness.

## Quick Start
- Requirements: Python 3.10+ and access to the internet for model/MCP calls.
- Install deps (recommend venv):
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  ```
- Env vars: set `OPENAI_API_KEY`; optionally `OPENAI_API_BASE` (defaults to `https://apis.iflow.cn/v1`).

## Running the Benchmark
Run tasks with optional attack tools:
```bash
python main.py --dataset all --attack \
  --attack-dataset ./datasets/test_prompts.json \
  --attack-scenario resource_waste
```
- `--dataset`: `all` (default) | `test` | `filter`
- `--attack`: enable the malicious `mytool` MCP server
- `--attack-dataset`: JSON list of attack tools mapped to task IDs
- `--attack-scenario`: `resource_waste` | `task_failure` | `information_leakage` | `backdoor_injection` | `resource_waste_no_success`
- Outputs land in `results/<timestamp>_<model>_<dataset>/run.log` and `results.json`

## Attack Tool Generation
- Modular generator (genetic-style evolution): `src/attacks/attack_generator_modular.py`
  ```bash
  python src/attacks/attack_generator_modular.py --input datasets/test_prompts.json --attack-type resource_waste
  ```
- Simple one-pass generator: `src/attacks/attack_generator_simple.py`
  ```bash
  python src/attacks/attack_generator_simple.py --input datasets/test_prompts.json --output attack_tools.json
  ```
- Extract best-performing tools from result folders: `python extract_attack_tools.py --base-dir ./results_attack --output attack_tools_extracted.json`

## Repository Layout
- `main.py`: CLI entry; loads dataset, resets `annotated_data`, wires MCP servers, runs tasks.
- `main_module.py`: core run loop, retries, judging, result aggregation.
- `configs/`: MCP server mappings (`tool2mcp.json`, `live_mcp.json`), proxy, model aliases/defaults.
- `datasets/`: benchmark task lists.
- `annotated_data_backup/`: baseline data copied to `annotated_data/` before each task.
- `src/mcp_client/`: MCP client wrapper with timeouts/truncation.
- `src/evaluators/`: LLM judge for task completion.
- `src/attacks/`: attack scenarios, scoring, and generators.
- `scripts/`: helper scripts.

## Notes
- Network calls and MCP tool processes are required for full runs.
