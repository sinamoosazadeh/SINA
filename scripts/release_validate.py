#!/usr/bin/env python3
"""Deterministic local gate battery. Non-zero exit if mandatory tests fail."""
import subprocess
import sys

r = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=".")
sys.exit(r.returncode)
