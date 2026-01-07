#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Task isolation system: provides per-task file system copies and MCP configs.
"""

import os
import shutil
import uuid
import json
from typing import Dict, Optional, Tuple
from pathlib import Path


class TaskIsolationManager:
    """Manages per-process isolated directories and MCP configs."""

    def __init__(self, base_cache_dir: Optional[str] = None):
        """
        Initialize task isolation manager.

        Args:
            base_cache_dir: Base cache directory, defaults to .cache/task_isolation
        """
        if base_cache_dir is None:
            base_cache_dir = os.path.join(os.getcwd(), ".cache", "task_isolation")

        self.base_cache_dir = base_cache_dir
        self.backup_dir = os.path.join(os.getcwd(), "annotated_data_backup")

        # Ensure directories exist
        os.makedirs(self.base_cache_dir, exist_ok=True)
        if not os.path.exists(self.backup_dir):
            raise FileNotFoundError(f"Backup directory not found: {self.backup_dir}")

    def create_process_isolation_dir(self, task_id: str = None) -> Tuple[str, str, str]:
        """
        Create an isolation directory for the current process.

        Args:
            task_id: Optional task id for logging only.

        Returns:
            Tuple[process_id, task directory path, annotated_data path]
        """
        # Generate unique process id
        import uuid
        process_id = f"process_{uuid.uuid4().hex[:12]}"

        # Create dedicated directory
        task_dir = os.path.join(self.base_cache_dir, process_id)
        annotated_data_dir = os.path.join(task_dir, "annotated_data")

        # Remove if exists
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir)

        # Create directories
        os.makedirs(annotated_data_dir, exist_ok=True)

        # Copy file system from backup
        if os.path.exists(self.backup_dir):
            shutil.copytree(self.backup_dir, annotated_data_dir, dirs_exist_ok=True)
        else:
            # If backup missing, create empty structure
            os.makedirs(annotated_data_dir, exist_ok=True)

        return process_id, task_dir, annotated_data_dir

    def cleanup_process_isolation_dir(self, process_id: str) -> None:
        """
        Remove isolation directory for a process.

        Args:
            process_id: Process id
        """
        task_dir = os.path.join(self.base_cache_dir, process_id)
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir)

    def cleanup_all_isolation_dirs(self) -> None:
        """Remove all isolation directories."""
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
        Generate per-process MCP config with paths rewritten.

        Args:
            base_config: Base MCP configuration
            task_annotated_data_path: Annotated data path for the task
            process_id: Process id

        Returns:
            Tuple[per-process MCP config, config file path]
        """
        # Deep copy the base config
        import copy
        task_config = copy.deepcopy(base_config)

        # Replace file system paths in args
        for server_name, server_config in task_config.items():
            if isinstance(server_config, dict) and "args" in server_config:
                args = server_config["args"]
                # Find/replace ./annotated_data or absolute paths
                new_args = []
                for arg in args:
                    if isinstance(arg, str):
                        # Replace relative paths
                        if "./annotated_data" in arg or "/annotated_data" in arg:
                            # Preserve argument structure, replace only the path part
                            if arg == "./annotated_data":
                                new_args.append(task_annotated_data_path)
                            elif "annotated_data" in arg and not arg.startswith("./"):
                                # Absolute path or other annotated_data-containing path
                                new_args.append(task_annotated_data_path)
                            else:
                                # Subdirectory cases (e.g., ./annotated_data/files)
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

        # Save per-process config to disk
        config_file_path = os.path.join(
            self.base_cache_dir,
            process_id,
            f"mcp_config_{process_id}.json"
        )

        # Ensure directory exists
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
        Get isolated MCP config (functional interface).

        Args:
            base_config: Base MCP config
            server_name_filter: Optional server name filter

        Returns:
            Tuple[per-process config, annotated_data path, process id]
        """
        # Create isolation dir
        process_id, task_dir, annotated_data_dir = self.create_process_isolation_dir()

        # Generate per-process config
        isolated_config, config_path = self.generate_mcp_config_for_process(
            base_config,
            annotated_data_dir,
            process_id
        )

        # If a filter is provided, only return that server config
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
    Quick helper to create per-process MCP config.

    Args:
        base_mcp_configs: Base MCP configs
        backup_path: Backup path, defaults to ./annotated_data_backup

    Returns:
        Tuple[per-process MCP config, annotated_data path, process id]
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
    Clean up isolation resources for a specific process.

    Args:
        process_id: Process ID
    """
    manager = TaskIsolationManager()
    manager.cleanup_process_isolation_dir(process_id)


def cleanup_all_isolation() -> None:
    """Clean up isolation resources for all tasks."""
    manager = TaskIsolationManager()
    manager.cleanup_all_isolation_dirs()


# Basic test harness
if __name__ == "__main__":
    import sys

    # Test creating process isolation directories
    manager = TaskIsolationManager()

    # Create a sample MCP config
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

    # Create isolated config
    isolated_config, annotated_data_path, process_id = manager.get_isolated_mcp_config_for_process(
        test_config
    )

    print(f"Process ID: {process_id}")
    print(f"Isolation dir: {manager.base_cache_dir}/{process_id}")
    print(f"annotated_data path: {annotated_data_path}")
    print(f"MCP config file: {manager.base_cache_dir}/{process_id}/mcp_config_{process_id}.json")
    print("\nGenerated MCP config:")
    print(json.dumps(isolated_config, indent=2, ensure_ascii=False))

    # Validate path rewriting
    for server_name, server_config in isolated_config.items():
        if "args" in server_config:
            print(f"\n{server_name} args: {server_config['args']}")
            for arg in server_config["args"]:
                if "annotated_data" in str(arg):
                    print(f"✓ Path isolated: {arg}")

    # Call multiple times to ensure IDs differ
    print("\n\nTest multiple isolation calls:")
    for i in range(3):
        _, _, process_id_test = manager.get_isolated_mcp_config_for_process(test_config)
        print(f"  Call {i+1} - process ID: {process_id_test}")

    # Clean up test resources
    print("\nCleaning up test resources...")
    # manager.cleanup_process_isolation_dir(process_id)
    print("Test complete!")
