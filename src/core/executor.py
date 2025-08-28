import asyncio
import json
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 定义执行器类
class TaskExecutor:
    """统一的任务执行器"""
    
    def __init__(self):
        """初始化执行器"""
        pass
    
    async def execute_task(self, task_info: Dict[str, Any], attack_tool_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        异步执行单个任务
        
        Args:
            task_info: 任务信息
            attack_tool_info: 恶意工具信息（可选）
            
        Returns:
            执行结果
        """
        # 这里应该实现具体的任务执行逻辑
        # 为简化起见，我们先返回一个占位结果
        return {
            "task_id": task_info["id"],
            "status": "executed",
            "result": "Task execution logic needs to be implemented"
        }
    
    def execute_task_sync(self, task_info: Dict[str, Any], attack_tool_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        同步执行单个任务
        
        Args:
            task_info: 任务信息
            attack_tool_info: 恶意工具信息（可选）
            
        Returns:
            执行结果
        """
        return asyncio.run(self.execute_task(task_info, attack_tool_info))


# 创建全局执行器实例
executor = TaskExecutor()


# 便捷函数
def execute_task_sync(task_info: Dict[str, Any], attack_tool_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    同步执行单个任务的便捷函数
    
    Args:
        task_info: 任务信息
        attack_tool_info: 恶意工具信息（可选）
        
    Returns:
        执行结果
    """
    return executor.execute_task_sync(task_info, attack_tool_info)


def execute_tasks_sync(tasks: List[Dict[str, Any]], attack_tool_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    同步执行多个任务的便捷函数
    
    Args:
        tasks: 任务列表
        attack_tool_info: 恶意工具信息（可选）
        
    Returns:
        汇总结果
    """
    results = []
    for task in tasks:
        result = executor.execute_task_sync(task, attack_tool_info)
        results.append(result)
    
    return {
        "run_timestamp": datetime.now().isoformat(),
        "tasks": results
    }