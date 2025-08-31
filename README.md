# MCP-Bench

MCP-Bench 是一个基于 Model Context Protocol (MCP) 的测试框架，用于评估和测试各种 MCP 工具和服务的性能与功能。

## 项目概述

本项目使用 LangChain 和 LangGraph 构建了一个测试平台，可以加载多种 MCP 工具并执行测试任务。通过定义测试数据集，可以自动化地评估 MCP 工具在不同场景下的表现。MCP-Bench 支持正常测试模式和攻击测试模式，可以用于评估 MCP 工具的安全性和鲁棒性。

## 主要特性

- 支持多种 MCP 工具的集成测试
- 可配置的测试任务和数据集
- 基于 LangChain 和 LangGraph 的智能代理执行
- 支持多种工具类型（Python、Node.js、NPX 等）
- 支持攻击模式测试，用于安全评估
- 结果文件夹命名包含模型名称和数据集类型标记
- 串行工具调用，确保执行顺序和结果准确性
- 详细的执行轨迹记录和结果分析

## 项目结构

```
MCP-Bench/
├── configs/                    # MCP 配置文件
│   ├── live_mcp.json           # 标准 MCP 工具配置
│   └── tool2mcp.json           # 工具到MCP映射配置
├── datasets/                   # 测试数据集
│   ├── test_prompts.json       # 测试提示和任务
│   ├── all_annotations.json    # 完整数据集
│   └── all_annotations_filter.json # 过滤后数据集
├── tools/                      # 自定义 MCP 工具实现
│   └── myTool.py               # 动态工具服务器
├── src/                        # 核心源代码
│   ├── core/                   # 核心执行器
│   ├── evaluators/             # 任务评估器
│   ├── agents/                 # 代理工具
│   ├── mcp_client/             # MCP 客户端
│   ├── data_loaders/           # 数据加载器
│   └── utils/                  # 工具函数
├── results/                    # 测试结果
├── main_module.py              # 主模块
├── main.py                     # 程序入口
├── attack_generator.py         # 攻击工具生成器
├── requirements.txt            # Python 依赖
└── README.md                   # 项目说明文档
```

## 安装依赖

### Python 依赖

```bash
pip install -r requirements.txt
```

### 环境变量配置

在运行项目之前，需要设置以下环境变量：

```bash
export OPENAI_API_KEY="your_openai_api_key"
export OPENAI_API_BASE="https://apis.iflow.cn/v1"  # 可选，默认值
```

或者创建 `.env` 文件来存储这些变量：

```bash
OPENAI_API_KEY=your_actual_api_key_here
OPENAI_API_BASE=https://your_api_base_url_here  # 可选，默认值
```

## 使用方法

### 基本测试运行

```bash
# 使用默认配置运行测试
python main.py

# 指定数据集类型
python main.py --dataset test
python main.py --dataset filter
python main.py --dataset all

# 指定模型
python main.py --model "qwen-7b"
python main.py --model "deepseek-ai/DeepSeek-V3"

# 结合使用
python main.py --dataset test --model "qwen-7b"
```

### 攻击模式测试

```bash
# 启用攻击模式
python main.py --attack

# 结合攻击数据集
python main.py --attack --attack-dataset /path/to/attack_dataset.json

# 攻击模式结合其他参数
python main.py --attack --dataset test --model "qwen-7b"
```

### 生成攻击数据集

```bash
# 生成攻击数据集
python attack_generator.py

# 指定输入和输出文件
python attack_generator.py --input datasets/test_prompts.json --output attack_dataset.json

# 使用模拟执行器
python attack_generator.py --use-simulated-executor
```

## 命令行参数说明

### main.py 参数

- `--dataset {all,test,filter}`: 选择数据集类型
  - `all`: 使用完整数据集 (默认)
  - `test`: 使用测试数据集
  - `filter`: 使用过滤后数据集
- `--attack`: 启用攻击模式 (mytool MCP server)
- `--attack-dataset ATTACK_DATASET`: 指定攻击数据集路径
- `--model MODEL`: 指定使用的模型名称 (默认: glm-4.5)

### attack_generator.py 参数

- `--input INPUT, -i INPUT`: 输入任务数据集路径 (默认: datasets/test_prompts.json)
- `--output OUTPUT, -o OUTPUT`: 输出攻击工具数据集路径 (默认: 11111.json)
- `--use-simulated-executor`: 使用模拟执行器而不是真实执行器

## 输出结果

每次运行都会在 `results/` 目录下创建一个带有时间戳、模型名称和数据集类型标记的文件夹，包含以下文件：

- `run.log`: 运行日志
- `results.json`: 详细的测试结果和统计信息

结果文件夹命名格式：
```
results/YYYY-MM-DD_HH-MM-SS_{model_name}_{dataset_type}
```

例如：
```
results/2025-08-31_14-30-25_glm-4.5_test
results/2025-08-31_15-45-10_qwen-7b_all
```

## 支持的 MCP 工具

项目支持超过100种 MCP 工具，包括但不限于：

- **Web内容获取**: fetch, puppeteer, playwright
- **文件操作**: filesystem, pdf-reader, text-editor
- **数据处理**: excel, word-document-server
- **代码工具**: git, maven-deps-server
- **金融工具**: yahoo-finance, kospi-kosdaq, asset-price
- **娱乐**: bilibili, youtube-transcript, chess
- **生活服务**: 12306-mcp, trends-hub
- **系统工具**: time, calculator, memory

## 开发指南

### 添加新的 MCP 工具

1. 在 `configs/live_mcp.json` 中添加工具配置
2. 实现相应的工具服务
3. 在测试数据集中添加相应的测试任务

### 添加新的测试任务

编辑 `datasets/test_prompts.json` 文件，添加新的测试任务对象。

## 故障排除

### 常见问题

1. **API密钥问题**: 确保设置了正确的 OPENAI_API_KEY 环境变量
2. **依赖安装问题**: 确保所有依赖都已正确安装
3. **MCP工具加载失败**: 检查 MCP 工具配置和环境依赖

### 清理缓存

```bash
# 清理 Python 缓存
rm -rf __pycache__
rm -rf src/__pycache__
rm -rf src/*/__pycache__
```

## 贡献

欢迎提交 Issue 和 Pull Request 来改进这个项目。

## 许可证

[待定]