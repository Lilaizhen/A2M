#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
临时路径管理器
用于为每个任务创建独立的临时操作空间
"""

import os
import tempfile
import shutil
import re
import threading
from typing import Dict

class TempPathManager:
    """临时路径管理器"""
    
    def __init__(self, source_dir: str = "./annotated_data"):
        self.source_dir = os.path.abspath(source_dir)
        self.temp_root = tempfile.gettempdir()
        self.temp_dirs: Dict[str, str] = {}  # task_id -> temp_dir
        self.path_mappings: Dict[str, Dict[str, str]] = {}  # task_id -> {original_path: temp_path}
        self._lock = threading.Lock()
        
    def create_temp_copy(self, task_id: str) -> str:
        """
        为指定任务创建临时副本目录
        返回临时目录路径
        """
        with self._lock:
            # 生成唯一的临时目录名称
            temp_dir_name = f"mcp_bench_{task_id}_{os.getpid()}"
            temp_dir = os.path.join(self.temp_root, temp_dir_name)
            
            # 如果临时目录已存在，先删除
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            
            # 创建临时目录
            os.makedirs(temp_dir, exist_ok=True)
            
            # 在临时目录中创建annotated_data子目录并复制源目录内容
            if os.path.exists(self.source_dir):
                temp_annotated_data_dir = os.path.join(temp_dir, "annotated_data")
                shutil.copytree(self.source_dir, temp_annotated_data_dir)
            
            # 记录临时目录
            self.temp_dirs[task_id] = temp_dir
            
            # 创建路径映射
            self.path_mappings[task_id] = {}
            self._build_path_mapping(task_id, self.source_dir, os.path.join(temp_dir, "annotated_data"))
            
            return temp_dir
    
    def _build_path_mapping(self, task_id: str, original_dir: str, temp_dir: str):
        """
        构建原始路径到临时路径的映射
        """
        for root, dirs, files in os.walk(original_dir):
            # 计算相对路径
            rel_path = os.path.relpath(root, original_dir)
            if rel_path == ".":
                rel_path = ""
            
            # 为每个文件建立映射
            for file_name in files:
                original_file_path = os.path.join(root, file_name)
                if rel_path:
                    temp_file_path = os.path.join(temp_dir, rel_path, file_name)
                else:
                    temp_file_path = os.path.join(temp_dir, file_name)
                self.path_mappings[task_id][original_file_path] = temp_file_path
    
    def get_temp_path_mapping(self, task_id: str, original_path: str) -> str:
        """
        获取原始路径对应的临时路径
        """
        with self._lock:
            if task_id in self.path_mappings and original_path in self.path_mappings[task_id]:
                return self.path_mappings[task_id][original_path]
            return original_path  # 如果没有映射，返回原始路径
    
    def cleanup_temp_dir(self, task_id: str):
        """
        清理指定任务的临时目录
        """
        with self._lock:
            if task_id in self.temp_dirs:
                temp_dir = self.temp_dirs[task_id]
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                del self.temp_dirs[task_id]
            
            if task_id in self.path_mappings:
                del self.path_mappings[task_id]
    
    def cleanup_all(self):
        """
        清理所有临时目录
        """
        with self._lock:
            for task_id in list(self.temp_dirs.keys()):
                self.cleanup_temp_dir(task_id)

# 全局临时路径管理器实例
_temp_path_manager = TempPathManager()

def convert_relative_paths_with_temp_mapping(text: str, task_id: str) -> str:
    """
    在文本中查找相对路径和绝对路径并转换为临时路径映射
    """
    if not text or not isinstance(text, str):
        return text
    
    # 获取当前工作目录，用于匹配绝对路径
    cwd = os.getcwd()
    annotated_data_path = os.path.join(cwd, "annotated_data")
    
    # 匹配相对路径模式 (./ 或 ../ 开头的路径) 和绝对路径模式
    # 相对路径模式
    relative_pattern = r'(["\']?)(\.{1,2}/annotated_data[^\s"\']*)["\']?'
    # 绝对路径模式
    absolute_pattern = r'(["\']?)(' + re.escape(annotated_data_path) + r'[^\s"\']*)["\']?'
    
    def replace_relative_path(match):
        quote = match.group(1)
        path = match.group(2)
        
        try:
            # 获取临时目录
            temp_dir = _temp_path_manager.temp_dirs.get(task_id)
            if temp_dir:
                # 将路径转换为临时目录中的路径
                if path.startswith('./'):
                    rel_path = path[2:]  # 去掉 "./"
                else:  # path.startswith('../')
                    rel_path = path[3:]  # 去掉 "../"
                
                temp_path = os.path.join(temp_dir, rel_path)
                return f'{quote}{temp_path}{quote}'
        except Exception:
            # 如果转换失败，保持原路径
            return match.group(0)
        
        return match.group(0)
    
    def replace_absolute_path(match):
        quote = match.group(1)
        path = match.group(2)
        
        try:
            # 获取临时目录
            temp_dir = _temp_path_manager.temp_dirs.get(task_id)
            if temp_dir:
                # 计算相对路径部分
                rel_path = os.path.relpath(path, cwd)
                temp_path = os.path.join(temp_dir, rel_path)
                return f'{quote}{temp_path}{quote}'
        except Exception:
            # 如果转换失败，保持原路径
            return match.group(0)
        
        return match.group(0)
    
    # 先处理绝对路径，再处理相对路径
    result = re.sub(absolute_pattern, replace_absolute_path, text)
    result = re.sub(relative_pattern, replace_relative_path, result)
    return result

def create_task_temp_dir(task_id: str) -> str:
    """
    为任务创建临时目录
    """
    return _temp_path_manager.create_temp_copy(task_id)

def cleanup_task_temp_dir(task_id: str):
    """
    清理任务临时目录
    """
    _temp_path_manager.cleanup_temp_dir(task_id)

def cleanup_all_temp_dirs():
    """
    清理所有临时目录
    """
    _temp_path_manager.cleanup_all()

def get_temp_path_for_task(task_id: str, original_path: str) -> str:
    """
    获取任务的临时路径
    """
    return _temp_path_manager.get_temp_path_mapping(task_id, original_path)