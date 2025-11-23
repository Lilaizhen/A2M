#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务隔离系统
为每个任务提供独立的文件系统和MCP配置
"""

import os
import shutil
import uuid
import json
from typing import Dict, Optional, Tuple
from pathlib import Path


class TaskIsolationManager:
    """任务隔离管理器"""

    def __init__(self, base_cache_dir: Optional[str] = None):
        """
        初始化任务隔离管理器

        Args:
            base_cache_dir: 缓存基础目录，默认为 .cache/task_isolation
        """
        if base_cache_dir is None:
            base_cache_dir = os.path.join(os.getcwd(), ".cache", "task_isolation")

        self.base_cache_dir = base_cache_dir
        self.backup_dir = os.path.join(os.getcwd(), "annotated_data_backup")

        # 确保目录存在
        os.makedirs(self.base_cache_dir, exist_ok=True)
        if not os.path.exists(self.backup_dir):
            raise FileNotFoundError(f"备份目录不存在: {self.backup_dir}")

    def create_process_isolation_dir(self, task_id: str = None) -> Tuple[str, str, str]:
        """
        为进程创建隔离目录（进程级隔离）

        Args:
            task_id: 任务ID（可选，仅用于日志记录，不参与隔离目录命名）

        Returns:
            Tuple[进程ID, 隔离目录路径, 隔离的annotated_data路径]
        """
        # 生成进程唯一标识
        import uuid
        process_id = f"process_{uuid.uuid4().hex[:12]}"

        # 创建进程专属目录
        task_dir = os.path.join(self.base_cache_dir, process_id)
        annotated_data_dir = os.path.join(task_dir, "annotated_data")

        # 如果已经存在，先清理
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir)

        # 创建目录
        os.makedirs(annotated_data_dir, exist_ok=True)

        # 从备份复制文件系统
        if os.path.exists(self.backup_dir):
            shutil.copytree(self.backup_dir, annotated_data_dir, dirs_exist_ok=True)
        else:
            # 如果备份不存在，创建空的目录结构
            os.makedirs(annotated_data_dir, exist_ok=True)

        return process_id, task_dir, annotated_data_dir

    def cleanup_process_isolation_dir(self, process_id: str) -> None:
        """
        清理进程的隔离目录

        Args:
            process_id: 进程ID
        """
        task_dir = os.path.join(self.base_cache_dir, process_id)
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir)

    def cleanup_all_isolation_dirs(self) -> None:
        """清理所有隔离目录"""
        if os.path.exists(self.base_cache_dir):
            shutil.rmtree(self.base_cache_dir)
            os.makedirs(self.base_cache_dir, exist_ok=True)

    def generate_mcp_config_for_process(
        self,
        base_config: Dict,
        task_annotated_data_path: str,
        process_id: str
    ) -> Tuple[Dict, str]:
        """
        为指定进程生成专用的MCP配置文件

        Args:
            base_config: 基础MCP配置
            task_annotated_data_path: 任务的annotated_data路径
            process_id: 进程ID

        Returns:
            Tuple[进程专属MCP配置, 配置文件路径]
        """
        # 深拷贝基础配置
        import copy
        task_config = copy.deepcopy(base_config)

        # 替换所有配置文件系统路径
        for server_name, server_config in task_config.items():
            if isinstance(server_config, dict) and "args" in server_config:
                args = server_config["args"]
                # 查找并替换 ./annotated_data 或绝对路径
                new_args = []
                for arg in args:
                    if isinstance(arg, str):
                        # 替换相对路径
                        if "./annotated_data" in arg or "/annotated_data" in arg:
                            # 保留原始参数结构，只替换路径部分
                            if arg == "./annotated_data":
                                new_args.append(task_annotated_data_path)
                            elif "annotated_data" in arg and not arg.startswith("./"):
                                # 处理绝对路径或其他包含annotated_data的路径
                                new_args.append(task_annotated_data_path)
                            else:
                                # 带有子目录的情况（如 ./annotated_data/files）
                                rel_path = arg.split("annotated_data", 1)[1].lstrip("/")
                                if rel_path:
                                    new_args.append(os.path.join(task_annotated_data_path, rel_path))
                                else:
                                    new_args.append(task_annotated_data_path)
                        else:
                            new_args.append(arg)
                    else:
                        new_args.append(arg)
                server_config["args"] = new_args

        # 保存进程专属配置到文件
        config_file_path = os.path.join(
            self.base_cache_dir,
            process_id,
            f"mcp_config_{process_id}.json"
        )

        # 确保目录存在
        os.makedirs(os.path.dirname(config_file_path), exist_ok=True)

        with open(config_file_path, 'w', encoding='utf-8') as f:
            json.dump(task_config, f, indent=2, ensure_ascii=False)

        return task_config, config_file_path

    def get_isolated_mcp_config_for_process(
        self,
        base_config: Dict,
        server_name_filter: Optional[str] = None
    ) -> Tuple[Dict, str, str]:
        """
        为进程获取隔离的MCP配置（函数式接口）

        Args:
            base_config: 基础MCP配置
            server_name_filter: 可选的服务器名称过滤器

        Returns:
            Tuple[进程专属MCP配置, annotated_data路径, 进程ID]
        """
        # 创建隔离目录
        process_id, task_dir, annotated_data_dir = self.create_process_isolation_dir()

        # 生成进程专属配置
        isolated_config, config_path = self.generate_mcp_config_for_process(
            base_config,
            annotated_data_dir,
            process_id
        )

        # 如果有服务器名称过滤器，只返回指定的服务器配置
        if server_name_filter and server_name_filter in isolated_config:
            isolated_config = {
                server_name_filter: isolated_config[server_name_filter]
            }

        return isolated_config, annotated_data_dir, process_id


def create_process_mcp_config(
    base_mcp_configs: Dict,
    backup_path: str = None
) -> Tuple[Dict, str, str]:
    """
    快速创建进程的MCP配置（简化接口）

    Args:
        base_mcp_configs: 基础MCP配置字典
        backup_path: 备份路径，默认为./annotated_data_backup

    Returns:
        Tuple[进程专属MCP配置, annotated_data路径, 进程ID]
    """
    if backup_path is None:
        backup_path = os.path.join(os.getcwd(), "annotated_data_backup")

    manager = TaskIsolationManager()
    isolated_config, annotated_data_path, process_id = manager.get_isolated_mcp_config_for_process(
        base_mcp_configs
    )

    return isolated_config, annotated_data_path, process_id


def cleanup_isolation_for_process(process_id: str) -> None:
    """
    清理指定进程的隔离资源

    Args:
        process_id: 进程ID
    """
    manager = TaskIsolationManager()
    manager.cleanup_process_isolation_dir(process_id)


def cleanup_all_isolation() -> None:
    """清理所有任务隔离资源"""
    manager = TaskIsolationManager()
    manager.cleanup_all_isolation_dirs()


# 测试代码
if __name__ == "__main__":
    import sys

    # 测试创建进程隔离目录
    manager = TaskIsolationManager()

    # 创建模拟的MCP配置
    test_config = {
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "./annotated_data"]
        },
        "fetch": {
            "command": "uvx",
            "args": ["mcp-server-fetch"]
        }
    }

    # 创建隔离配置
    isolated_config, annotated_data_path, process_id = manager.get_isolated_mcp_config_for_process(
        test_config
    )

    print(f"进程ID: {process_id}")
    print(f"隔离目录: {manager.base_cache_dir}/{process_id}")
    print(f"annotated_data路径: {annotated_data_path}")
    print(f"MCP配置文件: {manager.base_cache_dir}/{process_id}/mcp_config_{process_id}.json")
    print("\n生成的MCP配置:")
    print(json.dumps(isolated_config, indent=2, ensure_ascii=False))

    # 验证路径替换是否正确
    for server_name, server_config in isolated_config.items():
        if "args" in server_config:
            print(f"\n{server_name} args: {server_config['args']}")
            for arg in server_config["args"]:
                if "annotated_data" in str(arg):
                    print(f"✓ 路径已隔离: {arg}")

    # 测试多次调用，验证每次的进程ID都不同
    print("\n\n测试多次调用进程隔离:")
    for i in range(3):
        _, _, process_id_test = manager.get_isolated_mcp_config_for_process(test_config)
        print(f"  第{i+1}次调用 - 进程ID: {process_id_test}")

    # 清理测试资源
    print("\n清理测试资源...")
    # manager.cleanup_process_isolation_dir(process_id)
    print("测试完成！")
