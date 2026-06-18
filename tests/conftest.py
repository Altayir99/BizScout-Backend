"""Conftest for pytest — ensures app package is importable."""
import sys
from pathlib import Path

# Add the backend root to sys.path so `from app.xxx` works
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
