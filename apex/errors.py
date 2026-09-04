from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ErrorCategory(str, Enum):
    CONFIGURATION = "CONFIGURATION"
    VALIDATION = "VALIDATION"
    AUTHENTICATION = "AUTHENTICATION"
    AUTHORIZATION = "AUTHORIZATION"
    NETWORK = "NETWORK"
    PROVIDER = "PROVIDER"
    DATA = "DATA"
    PIT = "PIT"
    SCHEMA = "SCHEMA"
    PERSISTENCE = "PERSISTENCE"
    STATE_MACHINE = "STATE_MACHINE"
    CALCULATION = "CALCULATION"
    RESOURCE = "RESOURCE"
    TELEGRAM = "TELEGRAM"
    RECONCILIATION = "RECONCILIATION"
    SECURITY = "SECURITY"
    INTEGRITY = "INTEGRITY"
    UNKNOWN = "UNKNOWN"


@dataclass
class ApexError:
    category: ErrorCategory
    component: str
    severity: str
    correlation_id: str
    runtime: str
    description: str
    recovery_state: str
