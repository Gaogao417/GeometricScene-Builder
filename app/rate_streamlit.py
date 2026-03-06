#!/usr/bin/env python3
"""
Streamlit GUI for manual rating of GeometricScene outputs
Usage: streamlit run rate_streamlit.py -- --run_dir <output_directory>

Features:
- Keyboard shortcuts: 1-5 to rate, ← → to navigate
- Auto-save and auto-jump after rating
- Clear rating criteria
- Resume from checkpoint
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image


# Rating criteria
RATING_CRITERIA = {
    5: ("优秀", "图形清晰、比例协调、标注完整"),
    4: ("良好", "图形清晰，但有轻微变形/拥挤"),
    3: ("一般", "可用，但有明显问题"),
    2: ("较差", "图形混乱/重叠/难以辨认"),
    1: ("很差", "完全不可用/渲染失败"),
}


def load_results(run_dir: Path) -> Tuple[List[Dict], Dict]:
    """Load results from results.jsonl and create lookup by key."""
    results_path = run_dir / "results.jsonl"
    results = []
    results_lookup = {}

    with open(results_path, "r", encoding="utf-8") as f:
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
                "problem_id": row["problem_id"],
                "seed": row["seed"],
                "rating": int(row["rating"]),
                "comment": row.get("comment", ""),
                "rated_at": row.get("rated_at", ""),
            }

    return ratings


def save_ratings(run_dir: Path, ratings: Dict):
    """Save ratings to ratings.csv."""
    import pandas as pd

    if not ratings:
        return

    df = pd.DataFrame(list(ratings.values()))
    columns = ["problem_id", "seed", "rating", "comment"]
    if "rated_at" in df.columns:
        columns.append("rated_at")
    df = df[columns]
    ratings_path = run_dir / "ratings.csv"
    df.to_csv(ratings_path, index=False)


def find_next_unrated(
    rateable: List[Dict], ratings: Dict, current_idx: int
) -> Optional[int]:
    """Find the index of the next unrated case after current_idx."""
    for i in range(current_idx + 1, len(rateable)):
        key = f"{rateable[i]['problem_id']}_{rateable[i]['seed']}"
        if key not in ratings:
            return i
    # If no unrated after current, check from beginning
    for i in range(current_idx):
        key = f"{rateable[i]['problem_id']}_{rateable[i]['seed']}"
        if key not in ratings:
            return i
    return None


def inject_keyboard_listener():
    """Inject JavaScript to capture keyboard events and trigger button clicks.

    Note: components.html() doesn't return values, so we use JS to simulate
    button clicks directly. This works because Streamlit buttons have
    predictable labels that we can find and click.
    """
    js_code = """
    <script>
    (function() {
        // Avoid duplicate listeners
        if (window._ratingKbListener) return;
        window._ratingKbListener = true;
        
        // Find button by text content
        function findButton(text) {
            // Try to find in parent frames (Streamlit iframe structure)
            try {
                const parentDoc = window.parent.document;
                const buttons = parentDoc.querySelectorAll('button');
                for (const btn of buttons) {
                    if (btn.innerText.trim().startsWith(text)) return btn;
                }
            } catch(e) {
                // Cross-origin blocked, try local
            }
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {
                if (btn.innerText.trim().startsWith(text)) return btn;
            }
            return null;
        }
        
        document.addEventListener('keydown', function(e) {
            // Don't capture if user is typing in an input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
            
            // Rate with 1-5
            if (e.key >= '1' && e.key <= '5') {
                e.preventDefault();
                const labels = ['1 很差', '2 较差', '3 一般', '4 良好', '5 优秀'];
                const btn = findButton(labels[parseInt(e.key) - 1]);
                if (btn) {
                    btn.click();
                    btn.style.transform = 'scale(0.95)';
                    setTimeout(() => btn.style.transform = '', 100);
                }
            }
            // Navigate left (previous)
            if (e.key === 'ArrowLeft') {
                e.preventDefault();
                const btn = findButton('← 上一张');
                if (btn && !btn.disabled) btn.click();
            }
            // Navigate right (next)
            if (e.key === 'ArrowRight') {
                e.preventDefault();
                const btn = findButton('下一张 →');
                if (btn && !btn.disabled) btn.click();
            }
        });
    })();
    </script>
    """
    components.html(js_code, height=0)


def render_rating_criteria():
    """Render the collapsible rating criteria section."""
    with st.expander("📊 评分标准", expanded=False):
        criteria_html = """
        <style>
        .rating-table {width: 100%; border-collapse: collapse;}
        .rating-table td {padding: 8px 12px; border-bottom: 1px solid #eee;}
        .rating-score {font-weight: bold; font-size: 1.2em; width: 60px;}
        .rating-level {font-weight: bold; width: 80px;}
        .rating-desc {color: #555;}
        .rating-row:hover {background-color: #f5f5f5;}
        </style>
        <table class="rating-table">
        """
        for score in [5, 4, 3, 2, 1]:
            level, desc = RATING_CRITERIA[score]
            stars = "⭐" * score
            criteria_html += f"""
            <tr class="rating-row">
                <td class="rating-score">{score}{stars}</td>
                <td class="rating-level">{level}</td>
                <td class="rating-desc">{desc}</td>
            </tr>
            """
        criteria_html += "</table>"
        st.markdown(criteria_html, unsafe_allow_html=True)


def render_rating_buttons(
    current_rating: Optional[int], key_prefix: str = ""
) -> Optional[int]:
    """Render rating buttons and return selected rating."""
    cols = st.columns(5)
    selected = None

    for i, (rating, (level, _)) in enumerate(RATING_CRITERIA.items()):
        with cols[5 - i - 1]:  # Reverse order: 5,4,3,2,1
            is_selected = rating == current_rating
            btn_label = f"{rating} {level}"

            # Custom styling for selected button
            if is_selected:
                st.markdown(
                    f"""
                <style>
                div[data-testid="stButton"] > button[key="{key_prefix}rating_{rating}"] {{
                    background-color: #4CAF50 !important;
                    color: white !important;
                    border: 2px solid #388E3C !important;
                }}
                </style>
                """,
                    unsafe_allow_html=True,
                )

            if st.button(
                btn_label,
                key=f"{key_prefix}rating_{rating}",
                type="primary" if is_selected else "secondary",
                use_container_width=True,
            ):
                selected = rating

    return selected


def render_navigation(current_idx: int, total_count: int) -> Optional[str]:
    """Render navigation buttons. Returns 'prev' or 'next' if clicked."""
    nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
    action = None

    with nav_col1:
        if st.button(
            "← 上一张",
            disabled=current_idx == 0,
            use_container_width=True,
            key="nav_prev",
        ):
            action = "prev"

    with nav_col2:
        st.markdown(
            f"""
        <div style="text-align: center; padding-top: 8px; font-size: 1.1em;">
            <b>Case {current_idx + 1} / {total_count}</b>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with nav_col3:
        if st.button(
            "下一张 →",
            disabled=current_idx == total_count - 1,
            use_container_width=True,
            key="nav_next",
        ):
            action = "next"

    return action


def apply_custom_styles():
    """Apply custom CSS styles for better UI."""
    st.markdown(
        """
    <style>
    /* Hide Streamlit header and footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Better button styling */
    .stButton > button {
        height: 50px;
        font-size: 16px;
        font-weight: 500;
        border-radius: 8px;
        transition: all 0.2s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }
    
    /* Rating buttons specific */
    .stButton > button[data-testid*="rating"] {
        min-width: 100px;
    }
    
    /* Progress bar styling */
    .stProgress > div > div > div {
        background-color: #4CAF50;
    }
    
    /* Keyboard hint styling */
    kbd {
        background-color: #f0f0f0;
        border: 1px solid #ccc;
        border-radius: 4px;
        padding: 2px 6px;
        font-family: monospace;
        font-size: 14px;
    }
    
    /* Toast message styling */
    .stToast {
        background-color: #4CAF50 !important;
        color: white !important;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )


def handle_rating_action(
    rating_value: int,
    case: Dict,
    key: str,
    ratings: Dict,
    run_dir: Path,
    rateable: List[Dict],
) -> bool:
    """Handle rating action. Returns True if should navigate to next."""
    # Save rating
    ratings[key] = {
        "problem_id": case["problem_id"],
        "seed": case["seed"],
        "rating": rating_value,
        "comment": ratings.get(key, {}).get("comment", ""),
        "rated_at": datetime.now().isoformat(),
    }
    save_ratings(run_dir, ratings)

    # Find next unrated
    next_idx = find_next_unrated(rateable, ratings, st.session_state.current_idx)

    level, _ = RATING_CRITERIA[rating_value]

    if next_idx is not None:
        st.session_state.current_idx = next_idx
        st.toast(f"✅ 已保存 {rating_value}⭐ ({level}) → 跳转下一张", icon="✅")
        return True
    else:
        st.toast(f"🎉 已保存 {rating_value}⭐ ({level}) — 全部评分完成！", icon="🎉")
        return False


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Streamlit rating UI")
    parser.add_argument("--run_dir", required=True, help="Run directory path")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)

    if not run_dir.exists():
        st.error(f"Run directory not found: {run_dir}")
        sys.exit(1)

    # Streamlit app configuration
    st.set_page_config(
        page_title="GeometricScene Rating",
        page_icon="🎨",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    # Apply custom styles
    apply_custom_styles()

    # Initialize session state
    if "current_idx" not in st.session_state:
        st.session_state.current_idx = 0

    # Load data
    results, results_lookup = load_results(run_dir)
    ratings = load_ratings(run_dir)

    # Filter to successful cases with images only
    rateable = [
        r
        for r in results
        if r.get("success")
        and r.get("image_path")
        and (run_dir / r["image_path"]).exists()
    ]

    if not rateable:
        st.warning("No rateable cases found (no successful cases with images)")
        return

    # Find first un-rated case if starting fresh
    if "initialized" not in st.session_state:
        st.session_state.initialized = True
        for i, r in enumerate(rateable):
            key = f"{r['problem_id']}_{r['seed']}"
            if key not in ratings:
                st.session_state.current_idx = i
                break

    # Progress tracking
    rated_count = sum(
        1 for r in rateable if f"{r['problem_id']}_{r['seed']}" in ratings
    )
    total_count = len(rateable)
    progress_pct = rated_count / total_count * 100 if total_count > 0 else 0

    # === HEADER ===
    header_col1, header_col2 = st.columns([1, 2])

    with header_col1:
        render_rating_criteria()

    with header_col2:
        st.markdown(
            f"""
        <div style="text-align: right; padding-top: 10px;">
            <h2 style="margin: 0;">Progress: {rated_count}/{total_count}</h2>
            <p style="color: #666; margin: 5px 0;">{progress_pct:.1f}% 完成</p>
        </div>
        """,
            unsafe_allow_html=True,
        )
        st.progress(progress_pct / 100)

    # Inject keyboard listener (JS triggers button clicks directly)
    inject_keyboard_listener()

    st.divider()

    # === MAIN IMAGE ===
    case = rateable[st.session_state.current_idx]
    key = f"{case['problem_id']}_{case['seed']}"
    existing_rating = ratings.get(key, {})

    # Display image
    img_path = run_dir / case["image_path"]
    try:
        img = Image.open(img_path)
        # Calculate display size - use full width but maintain aspect ratio
        st.image(img, use_column_width=True)
    except Exception as e:
        st.error(f"Failed to load image: {e}")
        return

    st.divider()

    # === METADATA ===
    meta_col1, meta_col2, meta_col3, meta_col4 = st.columns(4)
    with meta_col1:
        st.markdown(f"**Problem:** `{case['problem_id']}`")
    with meta_col2:
        st.markdown(f"**Recipe:** `{case.get('recipe_name', 'N/A')}`")
    with meta_col3:
        st.markdown(f"**Seed:** `{case['seed']}`")
    with meta_col4:
        st.markdown(f"**Time:** `{case.get('solve_time_s', 'N/A')}s`")

    st.divider()

    # === RATING SECTION ===
    current_rating = existing_rating.get("rating")

    # Rating buttons (keyboard events trigger these via JS)
    st.markdown("### 选择评分")
    selected_rating = render_rating_buttons(current_rating)

    if selected_rating:
        handle_rating_action(selected_rating, case, key, ratings, run_dir, rateable)
        st.rerun()

    # === NAVIGATION ===
    nav_action = render_navigation(st.session_state.current_idx, total_count)

    if nav_action == "prev" and st.session_state.current_idx > 0:
        st.session_state.current_idx -= 1
        st.rerun()
    elif nav_action == "next" and st.session_state.current_idx < len(rateable) - 1:
        st.session_state.current_idx += 1
        st.rerun()

    # === KEYBOARD HINT ===
    st.markdown(
        """
    <div style="text-align: center; padding: 15px; color: #666; font-size: 14px; 
                background-color: #f9f9f9; border-radius: 8px; margin-top: 10px;">
        💡 <b>快捷键</b>：按 <kbd>1</kbd>-<kbd>5</kbd> 快速打分，<kbd>←</kbd> <kbd>→</kbd> 切换图片
    </div>
    """,
        unsafe_allow_html=True,
    )

    # === COMMENT SECTION (Optional) ===
    with st.expander("💬 添加评论（可选）"):
        current_comment = existing_rating.get("comment", "")
        comment = st.text_area(
            "评论", value=current_comment, height=80, key="comment_input"
        )

        if st.button("保存评论", key="save_comment"):
            if key in ratings:
                ratings[key]["comment"] = comment
                ratings[key]["rated_at"] = datetime.now().isoformat()
            else:
                ratings[key] = {
                    "problem_id": case["problem_id"],
                    "seed": case["seed"],
                    "rating": existing_rating.get("rating", 3),
                    "comment": comment,
                    "rated_at": datetime.now().isoformat(),
                }
            save_ratings(run_dir, ratings)
            st.toast("✅ 评论已保存")
            st.rerun()

    # Footer
    st.markdown(
        f"<small style='color: #999;'>Run directory: {run_dir}</small>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
