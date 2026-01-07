#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Attack scenario module initialization.
"""

from .resource_waste import ResourceWasteScenario
from .task_failure import TaskFailureScenario
from .information_leakage import InformationLeakageScenario
from .backdoor_injection import BackdoorInjectionScenario
from .resource_waste_no_success import ResourceWasteNoSuccessScenario

__all__ = ['ResourceWasteScenario', 'TaskFailureScenario', 'InformationLeakageScenario', 'BackdoorInjectionScenario', 'ResourceWasteNoSuccessScenario']
