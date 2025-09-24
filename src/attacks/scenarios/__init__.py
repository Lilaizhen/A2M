#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
攻击场景模块初始化文件
"""

from .resource_waste import ResourceWasteScenario
from .task_failure import TaskFailureScenario
from .inappropriate_output import InappropriateOutputScenario

__all__ = ['ResourceWasteScenario', 'TaskFailureScenario', 'InappropriateOutputScenario']