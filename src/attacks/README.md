# MCP-Bench Attack Generator (Modular Design)

## Module Layout

```
attacks/
├── __init__.py                    # Package entry
├── attack_generator_modular.py    # Main modular attack generator
├── attack_generator_simple.py     # Simplified generator
├── example_usage.py               # Usage example
├── core/                          # Execution layer
│   ├── __init__.py
│   └── real_executor.py           # Real executor implementation
├── scenarios/                     # Attack scenario modules
│   ├── __init__.py
│   ├── resource_waste.py          # Resource-waste scenario
│   ├── task_failure.py            # Task-failure scenario
│   ├── information_leakage.py     # Info-leak scenario
│   ├── backdoor_injection.py      # Backdoor-injection scenario
│   └── resource_waste_no_success.py  # Resource-waste (ignoring completion)
└── scoring/                       # Fitness scoring
    ├── __init__.py
    └── fitness_calculator.py      # Fitness calculator
```

## Design Principles

1. **Scenario separation**: each attack scenario is implemented independently for easier maintenance and extension.
2. **Decoupled concerns**: fitness scoring, prompt generation, executors, etc. stay separated.
3. **Consistent interfaces**: scenarios expose unified interfaces for the main generator.
4. **Extensibility**: new scenarios and scoring strategies can be added easily.

## Core Modules

### 1. Attack scenarios (scenarios/)
- **resource_waste.py**: induce the agent to repeatedly call tools to burn resources.
- **task_failure.py**: induce the agent to call tools that cause the original task to fail.
- **information_leakage.py**: induce the agent to leak sensitive information.
- **backdoor_injection.py**: induce the agent to perform malicious actions (e.g., writing a backdoor file).
- **resource_waste_no_success.py**: similar to resource_waste but ignores whether the original task completes.

### 2. Fitness scoring (scoring/)
- **fitness_calculator.py**: compute fitness scores per attack scenario.

### 3. Execution layer (core/)
- **real_executor.py**: real executor that talks to MCP tools and runs tasks.

## Usage

### Basic usage
```python
from src.attacks import AttackGenerator, AttackType

# Create generator
generator = AttackGenerator(attack_type=AttackType.RESOURCE_WASTE)

# Generate attack tool
attack_tool = generator.generate_attack_tool(task)
```

### Add a new attack scenario
1. Create a new scenario file under `scenarios/`.
2. Implement scenario-specific prompt generators.
3. Export the class from `scenarios/__init__.py`.
4. Wire the scenario into the main generator.

## Benefits

1. **Maintainability**: each scenario is isolated; changes do not leak across modules.
2. **Readability**: clear structure that is easy to follow.
3. **Testability**: every module can be tested on its own.
4. **Extensibility**: adding scenarios only requires implementing the standard interface.
