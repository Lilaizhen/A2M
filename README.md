# MCP-Bench

MCP-Bench 是一个基于 Model Context Protocol (MCP) 的测试框架，用于评估和测试各种 MCP 工具和服务的性能与功能。

## 项目概述

本项目使用 LangChain 和 LangGraph 构建了一个测试平台，可以加载多种 MCP 工具并执行测试任务。通过定义测试数据集，可以自动化地评估 MCP 工具在不同场景下的表现。

## 主要特性

- 支持多种 MCP 工具的集成测试
- 可配置的测试任务和数据集
- 基于 LangChain 和 LangGraph 的智能代理执行
- 支持多种工具类型（Python、Node.js、NPX 等）

## 项目结构

```
├── configs/                    # MCP 配置文件
│   ├── mcp_config.json        # 标准 MCP 工具配置
│   └── attack_mcp_config.json # 特殊测试配置
├── datasets/                  # 测试数据集
│   └── test_prompts.json      # 测试提示和任务
├── tools/                     # 自定义 MCP 工具实现
├── mcp/                       # MCP 应用和服务
├── main.py                   # 主程序入口
└── requirements.txt          # Python 依赖
```

## 安装依赖

### Python 依赖

```bash
pip install -r requirements.txt
```

### Node.js 依赖

项目中的 MCP 服务器需要 Node.js 环境和包管理器（推荐使用 pnpm）：

```bash
# 安装 pnpm（如果尚未安装）
npm install -g pnpm

# 进入 mcp 目录
cd mcp

# 安装所有依赖
pnpm install
```

## 环境配置

在运行项目之前，需要设置以下环境变量：

```bash
export OPENAI_API_KEY="your_openai_api_key"
export OPENAI_API_BASE="https://api.siliconflow.cn/v1"  # 可选，默认值
```

或者创建 `.env` 文件来存储这些变量。

## MCP 服务器构建

项目包含多个 MCP 服务器，需要先构建它们：

### 构建所有 MCP 服务器

```bash
# 进入 mcp 目录
cd mcp

# 构建所有应用
pnpm build
```

### 单独构建特定服务器

```bash
# 进入特定应用目录
cd apps/bilibili-mcp-server

# 构建
pnpm build
```

或者使用 turbo 命令：

```bash
# 在 mcp 目录中
pnpm build --filter=@wangshunnn/bilibili-mcp-server
```

## 使用方法

### 运行测试

```bash
python main.py
```

程序将自动加载配置文件中定义的 MCP 工具，并执行测试数据集中的任务。

### 开发模式

如果需要开发 MCP 服务器，可以使用监视模式：

```bash
# 在 mcp 目录中
pnpm dev
```

## 支持的 MCP 工具

项目当前支持以下 MCP 工具：

- **location**: 获取当前位置信息
- **weather**: 获取指定位置的天气信息
- **filesystem**: 文件系统操作
- **bilibili**: Bilibili 内容搜索
- **airbnb**: Airbnb 房源搜索
- **fetch**: 网页内容获取
- **git**: Git 操作工具
- **memory**: 内存操作工具
- **sequential-thinking**: 顺序思维工具
- **time**: 时间相关操作

## 配置文件说明

### mcp_config.json

定义了标准 MCP 工具的配置，包括命令和参数。

### test_prompts.json

定义了测试任务，每个任务包含：
- `id`: 任务唯一标识
- `category`: 任务分类
- `description`: 任务描述
- `input`: 用户输入提示
- `expected_tools`: 期望使用的工具列表

## 开发指南

### 添加新的 MCP 工具

1. 在 `configs/mcp_config.json` 中添加工具配置
2. 实现相应的工具服务
3. 在测试数据集中添加相应的测试任务

### 添加新的测试任务

编辑 `datasets/test_prompts.json` 文件，添加新的测试任务对象。

## 故障排除

### 常见问题

1. **Node.js 版本问题**: 确保使用 Node.js 18+ 版本
2. **构建失败**: 确保所有依赖都已正确安装
3. **权限问题**: 在某些系统上可能需要调整文件权限

### 清理构建缓存

```bash
# 清理 turbo 缓存
cd mcp
rm -rf .turbo

# 清理 node_modules
rm -rf node_modules
rm -rf apps/*/node_modules

# 重新安装
pnpm install
```

## 贡献

欢迎提交 Issue 和 Pull Request 来改进这个项目。

## 许可证

[待定]