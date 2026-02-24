#!/usr/bin/env python3
"""
Quick verification script to check if all components are ready
"""
import sys
from pathlib import Path

def check_file(path: Path, description: str) -> bool:
    """Check if file exists and is valid."""
    if not path.exists():
        print(f"[FAIL] {description}: {path} NOT FOUND")
        return False

    print(f"[OK] {description}: {path}")
    return True

def main():
    print("=== Geo Benchmark Setup Verification ===")
    print()

    # Check directories
    print("Directories:")
    check_file(Path("data"), "data/")
    check_file(Path("configs"), "configs/")
    check_file(Path("wl"), "wl/")
    check_file(Path("scripts"), "scripts/")
    check_file(Path("app"), "app/")

    # Check data files
    print()
    print("Data files:")
    check_file(Path("data/problems.jsonl"), "problems.jsonl")
    check_file(Path("configs/sweep.yaml"), "sweep.yaml")

    # Check Wolfram files
    print()
    print("Wolfram modules:")
    check_file(Path("wl/scene_builders.wl"), "scene_builders.wl")
    check_file(Path("wl/bench_core.wl"), "bench_core.wl")

    # Check Python scripts
    print()
    print("Python scripts:")
    check_file(Path("scripts/bench.py"), "bench.py")
    check_file(Path("scripts/report.py"), "report.py")
    check_file(Path("scripts/analyze.py"), "analyze.py")
    check_file(Path("requirements.txt"), "requirements.txt")

    # Check Streamlit app
    print()
    print("Streamlit app:")
    check_file(Path("app/rate_streamlit.py"), "rate_streamlit.py")

    # Check documentation
    print()
    print("Documentation:")
    check_file(Path("README.md"), "README.md")

    # Check Python imports
    print()
    print("Python package checks:")
    try:
        import yaml
        print("[OK] pyyaml installed")
    except ImportError:
        print("[FAIL] pyyaml NOT installed")

    try:
        import plotly
        import pandas
        print("[OK] plotly and pandas installed")
    except ImportError as e:
        print(f"[FAIL] plotly/pandas NOT installed: {e}")

    try:
        import streamlit
        print("[OK] streamlit installed")
    except ImportError:
        print("[FAIL] streamlit NOT installed")

    try:
        import PIL
        print("[OK] PIL/Pillow installed")
    except ImportError:
        print("[FAIL] PIL/Pillow NOT installed")

    try:
        from wolframclient.evaluation import WolframLanguageSession
        print("[OK] wolframclient installed")
    except ImportError:
        print("[FAIL] wolframclient NOT installed")

    print()
    print("=== Verification Complete ===")
    print()
    print("Next steps:")
    print("1. Install Python packages: pip install -r requirements.txt")
    print("2. Ensure Wolfram Engine is running")
    print("3. Run test: python scripts/bench.py --config configs/sweep.yaml --problems data/problems.jsonl")

if __name__ == "__main__":
    main()
