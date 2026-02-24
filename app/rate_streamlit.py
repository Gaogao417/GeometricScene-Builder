#!/usr/bin/env python3
"""
Streamlit GUI for manual rating of GeometricScene outputs
Usage: streamlit run rate_streamlit.py -- --run_dir <output_directory>
"""
import json
import sys
from pathlib import Path
from typing import List, Dict, Tuple
import os

import streamlit as st
from PIL import Image


def load_results(run_dir: Path) -> Tuple[List[Dict], Dict]:
    """Load results from results.jsonl and create lookup by key."""
    results_path = run_dir / "results.jsonl"
    results = []
    results_lookup = {}

    with open(results_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                result = json.loads(line)
                results.append(result)
                key = f"{result['problem_id']}_{result['seed']}"
                results_lookup[key] = result

    return results, results_lookup


def load_ratings(run_dir: Path) -> Dict[str, Dict]:
    """Load existing ratings from ratings.csv."""
    ratings_path = run_dir / "ratings.csv"
    ratings = {}

    if ratings_path.exists():
        import pandas as pd
        df = pd.read_csv(ratings_path)
        for _, row in df.iterrows():
            key = f"{row['problem_id']}_{row['seed']}"
            ratings[key] = {
                'problem_id': row['problem_id'],
                'seed': row['seed'],
                'rating': row['rating'],
                'comment': row.get('comment', '')
            }

    return ratings


def save_ratings(run_dir: Path, ratings: Dict):
    """Save ratings to ratings.csv."""
    import pandas as pd

    if not ratings:
        return

    df = pd.DataFrame(list(ratings.values()))
    df = df[['problem_id', 'seed', 'rating', 'comment']]
    ratings_path = run_dir / "ratings.csv"
    df.to_csv(ratings_path, index=False)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Streamlit rating UI")
    parser.add_argument("--run_dir", required=True, help="Run directory path")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)

    if not run_dir.exists():
        st.error(f"Run directory not found: {run_dir}")
        sys.exit(1)

    # Streamlit app
    st.set_page_config(
        page_title="GeometricScene Rating",
        page_icon="🎨",
        layout="wide"
    )

    st.title("🎨 GeometricScene Rating")

    # Load data
    results, results_lookup = load_results(run_dir)
    ratings = load_ratings(run_dir)

    # Filter to successful cases with images only
    rateable = [
        r for r in results
        if r.get('success') and r.get('image_path') and (run_dir / r['image_path']).exists()
    ]

    if not rateable:
        st.warning("No rateable cases found (no successful cases with images)")
        return

    # Progress tracking
    rated_count = sum(1 for r in rateable if f"{r['problem_id']}_{r['seed']}" in ratings)
    total_count = len(rateable)

    st.info(f"Progress: {rated_count}/{total_count} rated ({rated_count/total_count*100:.1f}%)")

    # Get current index (saved in session state)
    if 'current_idx' not in st.session_state:
        # Find first un-rated case
        st.session_state.current_idx = 0
        for i, r in enumerate(rateable):
            key = f"{r['problem_id']}_{r['seed']}"
            if key not in ratings:
                st.session_state.current_idx = i
                break

    # Navigation controls
    col1, col2, col3 = st.columns([1, 3, 1])

    with col1:
        if st.button("⬅ Previous", disabled=st.session_state.current_idx == 0):
            st.session_state.current_idx = max(0, st.session_state.current_idx - 1)

    with col2:
        st.markdown(f"<h3 style='text-align: center; margin: 0;'>Case {st.session_state.current_idx + 1}/{total_count}</h3>", unsafe_allow_html=True)

    with col3:
        if st.button("Next ⬆", disabled=st.session_state.current_idx == len(rateable) - 1):
            st.session_state.current_idx = min(len(rateable) - 1, st.session_state.current_idx + 1)

    # Current case
    case = rateable[st.session_state.current_idx]
    key = f"{case['problem_id']}_{case['seed']}"
    existing_rating = ratings.get(key, {})

    # Display case info
    st.divider()

    col_left, col_right = st.columns([1, 2])

    with col_left:
        st.subheader("Case Info")

        st.markdown(f"""
        **Problem ID:** {case['problem_id']}

        **Recipe:** {case.get('recipe_name', 'N/A')}

        **Seed:** {case['seed']}

        **Solve Time:** {case.get('solve_time_s', 'N/A')}s
        """)

        if 'text' in results_lookup.get(key, {}):
            st.markdown(f"*Problem Text:*")
            st.info(results_lookup[key]['text'])

    with col_right:
        st.subheader("Image")

        # Display image
        img_path = run_dir / case['image_path']
        try:
            img = Image.open(img_path)
            st.image(img, use_column_width=True)
        except Exception as e:
            st.error(f"Failed to load image: {e}")

    # Rating section
    st.divider()
    st.subheader("Rate This Case")

    # Rating input
    current_rating = existing_rating.get('rating', None)
    rating = st.radio(
        "Rating",
        options=[1, 2, 3, 4, 5],
        index=int(current_rating) - 1 if current_rating else None,
        horizontal=True,
        format_func=lambda x: f"{x} ⭐" if x == 5 else f"{x}"
    )

    st.markdown("""
    <small>
    <b>Rating Guide:</b><br/>
    1 = Very Poor<br/>
    2 = Poor<br/>
    3 = Average<br/>
    4 = Good<br/>
    5 = Excellent
    </small>
    """, unsafe_allow_html=True)

    # Comment
    current_comment = existing_rating.get('comment', '')
    comment = st.text_area("Comments (optional)", value=current_comment, height=100)

    # Save button
    st.divider()
    col_save, col_skip = st.columns(2)

    with col_save:
        if st.button("💾 Save Rating", type="primary"):
            ratings[key] = {
                'problem_id': case['problem_id'],
                'seed': case['seed'],
                'rating': rating,
                'comment': comment
            }
            save_ratings(run_dir, ratings)
            st.success(f"Rating saved for {case['problem_id']} (seed {case['seed']})")
            st.rerun()

    with col_skip:
        if st.button("⏭ Skip"):
            st.session_state.current_idx = min(len(rateable) - 1, st.session_state.current_idx + 1)

    # Footer
    st.divider()
    st.markdown(f"<small>Run directory: {run_dir}</small>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
