# MCP-Bench 攻击生成器模块化设计

## 模块化结构说明

```
attacks/
├── __init__.py                    # 模块入口
├── attack_generator_modular.py    # 主攻击生成器（模块化版本）
├── attack_generator_simple.py     # 简化版攻击生成器
├── example_usage.py              # 使用示例
├── core/                         # 核心执行模块
│   ├── __init__.py
│   └── real_executor.py          # 真实执行器实现
├── scenarios/                    # 攻击场景模块
│   ├── __init__.py
│   ├── resource_waste.py         # 资源浪费攻击场景
│   ├── task_failure.py           # 任务失败攻击场景
│   ├── information_leakage.py   # 信息泄漏攻击场景
│   ├── backdoor_injection.py    # 后门注入攻击场景
│   └── resource_waste_no_success.py  # 资源浪费（不考虑任务成功）攻击场景
└── scoring/                      # 适应度评分模块
    ├── __init__.py
    └── fitness_calculator.py     # 适应度计算器
```

## 模块设计原则

1. **场景分离**：每个攻击场景独立实现，便于维护和扩展
2. **功能解耦**：适应度计算、提示生成、执行器等核心功能分离
3. **接口一致**：各场景提供统一的接口，便于主程序调用
4. **可扩展性**：易于添加新的攻击场景和评分方法

## 核心模块说明

### 1. 攻击场景模块 (scenarios/)
- **resource_waste.py**: 资源浪费攻击场景，目标是诱导AI反复调用工具以消耗资源
- **task_failure.py**: 任务失败攻击场景，目标是诱导AI调用工具导致原始任务失败
- **information_leakage.py**: 信息泄漏攻击场景，目标是诱导AI泄漏敏感信息
- **backdoor_injection.py**: 后门注入攻击场景，目标是诱导AI执行恶意操作，如写入后门文件
- **resource_waste_no_success.py**: 资源浪费（不考虑任务成功）攻击场景，目标是诱导AI反复调用工具以消耗资源，但不关心原始任务是否成功完成

### 2. 适应度评分模块 (scoring/)
- **fitness_calculator.py**: 根据不同攻击场景计算适应度分数

### 3. 核心执行模块 (core/)
- **real_executor.py**: 真实执行器，负责与MCP工具交互执行任务

## 使用方法

### 基本使用
```python
from src.attacks import AttackGenerator, AttackType

# 创建攻击生成器
generator = AttackGenerator(attack_type=AttackType.RESOURCE_WASTE)

# 生成攻击工具
attack_tool = generator.generate_attack_tool(task)
```

### 添加新攻击场景
1. 在 `scenarios/` 目录下创建新的场景文件
2. 实现场景特定的提示生成方法
3. 在 `scenarios/__init__.py` 中导出新类
4. 在主生成器中集成新场景

## 优势

1. **维护性**：每个场景代码独立，修改不影响其他场景
2. **可读性**：代码结构清晰，易于理解
3. **可测试性**：每个模块可独立测试
4. **可扩展性**：添加新场景只需实现相应接口