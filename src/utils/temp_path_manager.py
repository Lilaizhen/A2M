#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Temporary path manager used to create isolated working copies per task.
"""

import os
import tempfile
import shutil
import re
import threading
from typing import Dict

class TempPathManager:
    """Manage per-task temporary directories and path mappings."""
    
    def __init__(self, source_dir: str = "./annotated_data"):
        self.source_dir = os.path.abspath(source_dir)
        self.temp_root = tempfile.gettempdir()
        self.temp_dirs: Dict[str, str] = {}  # task_id -> temp_dir
        self.path_mappings: Dict[str, Dict[str, str]] = {}  # task_id -> {original_path: temp_path}
        self._lock = threading.Lock()
        
    def create_temp_copy(self, task_id: str) -> str:
        """
        Create a temporary copy of the annotated_data tree for the task.
        Returns the path to the temp directory.
        """
        with self._lock:
            # Generate a unique temp directory name
            temp_dir_name = f"mcp_bench_{task_id}_{os.getpid()}"
            temp_dir = os.path.join(self.temp_root, temp_dir_name)
            
            # Remove existing temp dir if present
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            
            # Create temp directory
            os.makedirs(temp_dir, exist_ok=True)
            
            # Create annotated_data subdir and copy source content
            if os.path.exists(self.source_dir):
                temp_annotated_data_dir = os.path.join(temp_dir, "annotated_data")
                shutil.copytree(self.source_dir, temp_annotated_data_dir)
            
            # Record temp directory
            self.temp_dirs[task_id] = temp_dir
            
            # Build path mappings
            self.path_mappings[task_id] = {}
            self._build_path_mapping(task_id, self.source_dir, os.path.join(temp_dir, "annotated_data"))
            
            return temp_dir
    
    def _build_path_mapping(self, task_id: str, original_dir: str, temp_dir: str):
        """
        Build mapping from original paths to their counterparts in the temp copy.
        """
        for root, dirs, files in os.walk(original_dir):
            # Compute relative path
            rel_path = os.path.relpath(root, original_dir)
            if rel_path == ".":
                rel_path = ""
            
            # Map every file
            for file_name in files:
                original_file_path = os.path.join(root, file_name)
                if rel_path:
                    temp_file_path = os.path.join(temp_dir, rel_path, file_name)
                else:
                    temp_file_path = os.path.join(temp_dir, file_name)
                self.path_mappings[task_id][original_file_path] = temp_file_path
    
    def get_temp_path_mapping(self, task_id: str, original_path: str) -> str:
        """
        Get the temp path corresponding to an original path.
        """
        with self._lock:
            if task_id in self.path_mappings and original_path in self.path_mappings[task_id]:
                return self.path_mappings[task_id][original_path]
            return original_path  # Fallback to original path if no mapping exists
    
    def cleanup_temp_dir(self, task_id: str):
        """
        Remove the temp directory for the given task.
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
        Remove all tracked temp directories.
        """
        with self._lock:
            for task_id in list(self.temp_dirs.keys()):
                self.cleanup_temp_dir(task_id)

# Global temp path manager instance
_temp_path_manager = TempPathManager()

def convert_relative_paths_with_temp_mapping(text: str, task_id: str) -> str:
    """
    Replace relative/absolute annotated_data paths in text with temp paths.
    """
    if not text or not isinstance(text, str):
        return text
    
    # Use current working directory for absolute path matching
    cwd = os.getcwd()
    annotated_data_path = os.path.join(cwd, "annotated_data")
    
    # Match relative (./ or ../) and absolute paths
    # Relative pattern
    relative_pattern = r'(["\']?)(\.{1,2}/annotated_data[^\s"\']*)["\']?'
    # Absolute pattern
    absolute_pattern = r'(["\']?)(' + re.escape(annotated_data_path) + r'[^\s"\']*)["\']?'
    
    def replace_relative_path(match):
        quote = match.group(1)
        path = match.group(2)
        
        try:
            # Get temp directory
            temp_dir = _temp_path_manager.temp_dirs.get(task_id)
            if temp_dir:
                # Convert to the path inside the temp directory
                if path.startswith('./'):
                    rel_path = path[2:]  # Remove "./"
                else:  # path.startswith('../')
                    rel_path = path[3:]  # Remove "../"
                
                temp_path = os.path.join(temp_dir, rel_path)
                return f'{quote}{temp_path}{quote}'
        except Exception:
            # Keep original path on failure
            return match.group(0)
        
        return match.group(0)
    
    def replace_absolute_path(match):
        quote = match.group(1)
        path = match.group(2)
        
        try:
            # Get temp directory
            temp_dir = _temp_path_manager.temp_dirs.get(task_id)
            if temp_dir:
                # Compute relative portion
                rel_path = os.path.relpath(path, cwd)
                temp_path = os.path.join(temp_dir, rel_path)
                return f'{quote}{temp_path}{quote}'
        except Exception:
            # Keep original path on failure
            return match.group(0)
        
        return match.group(0)
    
    # Handle absolute paths first, then relative paths
    result = re.sub(absolute_pattern, replace_absolute_path, text)
    result = re.sub(relative_pattern, replace_relative_path, result)
    return result

def create_task_temp_dir(task_id: str) -> str:
    """
    Create a temporary directory for a task.
    """
    return _temp_path_manager.create_temp_copy(task_id)

def cleanup_task_temp_dir(task_id: str):
    """
    Clean up the task temporary directory.
    """
    _temp_path_manager.cleanup_temp_dir(task_id)

def cleanup_all_temp_dirs():
    """
    Clean up all temporary directories.
    """
    _temp_path_manager.cleanup_all()

def get_temp_path_for_task(task_id: str, original_path: str) -> str:
    """
    Get the mapped temp path for a specific task.
    """
    return _temp_path_manager.get_temp_path_mapping(task_id, original_path)
