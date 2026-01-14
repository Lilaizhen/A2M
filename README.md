# A2M

A LangGraph/LangChain–based benchmark that runs multi-tool MCP agents on curated tasks, with optional adversarial tools to stress-test safety and robustness.

## Quick Start
- Requirements: Python 3.10+ and access to the internet for model/MCP calls.
- Install deps (conda):
  ```bash
  conda create -n a2m python=3.10
  conda activate a2m
  pip install -r requirements.txt
  ```
- Env vars: set `OPENAI_API_KEY`; optionally `OPENAI_API_BASE`.

## Running the Benchmark
Run tasks with optional attack tools:
```bash
python main.py --dataset all --attack \
  --attack-dataset results_attack/resource_waste.json \
  --attack-scenario resource_waste
```

## Attack Tool Generation
```bash
python src/attacks/attack_generator_modular_backup.py --output results_attack/resource_waste.json --iterations 10 --output-dir results_attack/resource_waste --execution-model glm-4.6 --generation-model glm-4.6 --mutation-model glm-4.6 --candidate-count 20 --use-strategy-tags --attack-type resource_waste --use-execution-trace --no-require-task-success --top-k 10
```

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
