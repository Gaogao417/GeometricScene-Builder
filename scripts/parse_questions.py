#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Parse Wolfram Language question files and generate problems.jsonl.

Usage:
    python scripts/parse_questions.py

Input:  question_test.txt
Output: data/problems.jsonl
"""

from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path
from typing import Any

from pypinyin import Style, pinyin

# Fix Windows console encoding for Chinese characters
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Wolfram keywords to exclude from point extraction
WOLFRAM_KEYWORDS = {
    "Triangle",
    "Polygon",
    "Line",
    "Circle",
    "Region",
    "Element",
    "GeometricAssertion",
    "EuclideanDistance",
    "PlanarAngle",
    "PolygonAngle",
    "Convex",
    "Clockwise",
    "Regular",
    "Perpendicular",
    "Parallel",
    "Concurrent",
    "Midpoint",
}


def chinese_to_pinyin_id(text: str) -> str:
    """Convert Chinese text to lowercase pinyin with underscores.

    Example: "倍长中线" -> "bei_chang_zhong_xian"
    """
    py_list = pinyin(text, style=Style.NORMAL)
    return "_".join([py[0] for py in py_list])


def extract_points(expressions: list[str]) -> list[str]:
    """Extract single uppercase letters as point names.

    Excludes Wolfram keywords.
    """
    all_text = " ".join(expressions)
    # Match single uppercase letters not part of a word
    pattern = r"(?<![a-zA-Z])[A-Z](?![a-zA-Z])"
    matches = re.findall(pattern, all_text)
    # Filter out keywords and deduplicate while preserving order
    points = []
    seen = set()
    for m in matches:
        if m not in WOLFRAM_KEYWORDS and m not in seen:
            points.append(m)
            seen.add(m)
    return points


def extract_polygons(expressions: list[str]) -> list[dict[str, Any]]:
    """Extract polygon definitions from expressions.

    Matches:
    - Triangle[{A, B, C}]
    - Triangle@{A, B, C}
    - Polygon[{A, B, C, D}]
    - Polygon@{A, B, C, D}

    Returns deduplicated polygons (same points + source = duplicate).
    """
    polygons = []
    seen = set()
    all_text = " ".join(expressions)

    # Pattern for Triangle[{A, B, C}] or Triangle@{A, B, C}
    triangle_pattern = r"Triangle\s*[@\[]\s*\{([^}]+)\}"
    for match in re.finditer(triangle_pattern, all_text):
        points_str = match.group(1)
        points = tuple(p.strip() for p in points_str.split(","))
        if len(points) >= 3:
            key = (points, "Triangle")
            if key not in seen:
                seen.add(key)
                polygons.append({"points": list(points), "source": "Triangle"})

    # Pattern for Polygon[{A, B, C, D}] or Polygon@{A, B, C, D}
    polygon_pattern = r"Polygon\s*[@\[]\s*\{([^}]+)\}"
    for match in re.finditer(polygon_pattern, all_text):
        points_str = match.group(1)
        points = tuple(p.strip() for p in points_str.split(","))
        if len(points) >= 3:
            key = (points, "Polygon")
            if key not in seen:
                seen.add(key)
                polygons.append({"points": list(points), "source": "Polygon"})

    return polygons


def parse_question_block(block: str) -> dict[str, Any] | None:
    """Parse a single question block.

    Format:
        q["题目名称", 编号] = <| ... |>;

    Returns dict with name, number, propositions, description, error_conclusions.
    """
    # Match the header: q["name", number] =
    header_pattern = r'q\s*\[\s*"([^"]+)"\s*,\s*(\d+)\s*\]\s*='
    header_match = re.search(header_pattern, block)
    if not header_match:
        return None

    name = header_match.group(1)
    number = int(header_match.group(2))

    # Extract content between <| and |>
    # Find <| and then count brackets to find matching |>
    start_idx = block.find("<|")
    if start_idx == -1:
        return None

    # Find matching |> using bracket counting
    depth = 0
    end_idx = -1
    i = start_idx
    while i < len(block):
        if block[i : i + 2] == "<|":
            depth += 1
            i += 2
        elif block[i : i + 2] == "|>":
            depth -= 1
            if depth == 0:
                end_idx = i + 2
                break
            i += 2
        else:
            i += 1

    if end_idx == -1:
        return None

    content = block[start_idx:end_idx]

    # Parse fields
    propositions = parse_list_field(content, "Propositions")
    description = parse_list_field(content, "Description")
    error_conclusions = parse_list_field(content, "ErrorConclusions")

    return {
        "name": name,
        "number": number,
        "propositions": propositions,
        "description": description,
        "error_conclusions": error_conclusions,
    }


def parse_list_field(content: str, field_name: str) -> list[Any]:
    """Parse a list field from the content.

    Handles nested braces and returns a list of strings or integers.
    """
    # Find field: "FieldName" -> { ... }
    pattern = rf'"{field_name}"\s*->\s*'
    match = re.search(pattern, content)
    if not match:
        return []

    start_idx = match.end()
    # Check if it starts with {
    rest = content[start_idx:].lstrip()
    if not rest.startswith("{"):
        return []

    # Find matching } using bracket counting
    brace_start = start_idx + (len(content[start_idx:]) - len(rest))
    depth = 0
    end_idx = -1
    i = brace_start
    while i < len(content):
        if content[i] == "{":
            depth += 1
        elif content[i] == "}":
            depth -= 1
            if depth == 0:
                end_idx = i + 1
                break
        i += 1

    if end_idx == -1:
        return []

    list_content = content[brace_start:end_idx]

    # Parse items from the list
    return parse_list_items(list_content)


def parse_list_items(list_content: str) -> list[Any]:
    """Parse individual items from a Wolfram list.

    Items are separated by commas, but we need to handle nested structures:
    - Braces: { }
    - Brackets: [ ]
    - Parentheses: ( )
    - String literals: "..."
    - Special symbols: \[Element], etc.
    """
    # Remove outer braces
    inner = list_content.strip()
    if inner.startswith("{") and inner.endswith("}"):
        inner = inner[1:-1].strip()

    if not inner:
        return []

    items = []
    current_item = ""
    brace_depth = 0  # {}
    bracket_depth = 0  # []
    paren_depth = 0  # ()

    i = 0
    while i < len(inner):
        char = inner[i]

        # Handle escape sequences like \[Element]
        if char == "\\" and i + 1 < len(inner):
            # Check for \[...] pattern (Wolfram special character)
            if inner[i + 1] == "[":
                # Find matching ]
                j = i + 2
                while j < len(inner) and inner[j] != "]":
                    j += 1
                if j < len(inner):
                    # Include the whole \[...] sequence
                    current_item += inner[i : j + 1]
                    i = j + 1
                    continue
            else:
                # Other escape sequence, include as-is
                current_item += char
                i += 1
                continue

        if char == "{":
            brace_depth += 1
            current_item += char
        elif char == "}":
            brace_depth -= 1
            current_item += char
        elif char == "[":
            bracket_depth += 1
            current_item += char
        elif char == "]":
            bracket_depth -= 1
            current_item += char
        elif char == "(":
            paren_depth += 1
            current_item += char
        elif char == ")":
            paren_depth -= 1
            current_item += char
        elif (
            char == "," and brace_depth == 0 and bracket_depth == 0 and paren_depth == 0
        ):
            # Item separator at top level
            item = current_item.strip()
            if item:
                items.append(item)
            current_item = ""
        elif char == '"':
            # Handle string literal
            current_item += char
            i += 1
            while i < len(inner) and inner[i] != '"':
                if inner[i] == "\\" and i + 1 < len(inner):
                    current_item += inner[i : i + 2]
                    i += 2
                else:
                    current_item += inner[i]
                    i += 1
            if i < len(inner):
                current_item += inner[i]  # closing quote
        else:
            current_item += char

        i += 1

    # Don't forget the last item
    item = current_item.strip()
    if item:
        items.append(item)

    # Convert numeric items to integers for ErrorConclusions
    result = []
    for item in items:
        if item.isdigit():
            result.append(int(item))
        else:
            result.append(item)

    return result


def split_into_blocks(content: str) -> list[str]:
    """Split the file content into individual question blocks.

    Each block ends with |>;
    """
    blocks = []
    current_block = ""
    depth = 0
    in_block = False

    lines = content.split("\n")
    for line in lines:
        # Skip empty lines at the start of a new block
        if not in_block and not line.strip():
            continue

        # Check for block start: q["...",
        if re.match(r'\s*q\s*\[\s*"', line):
            in_block = True
            current_block = line + "\n"
            # Check for <| to start tracking depth
            if "<|" in line:
                depth += line.count("<|") - line.count("|>")
            continue

        if in_block:
            current_block += line + "\n"
            # Track <| and |> depth
            depth += line.count("<|") - line.count("|>")

            # Block ends when depth returns to 0 and we have |>;
            if depth <= 0 and "|>" in line:
                blocks.append(current_block)
                current_block = ""
                in_block = False
                depth = 0

    return blocks


def generate_problems(question: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate problem records from a parsed question.

    For each valid proposition (not in error_conclusions), create a problem
    with that proposition as the conclusion and others as hypotheses.
    """
    problems = []

    name = question["name"]
    number = question["number"]
    propositions = question["propositions"]
    description = question["description"]
    error_conclusions = set(question.get("error_conclusions", []))

    # Generate pinyin ID prefix
    pinyin_prefix = chinese_to_pinyin_id(name)

    # Get all expressions for point extraction
    all_expressions = description + propositions
    points = extract_points(all_expressions)
    polygons = extract_polygons(all_expressions)

    # For each valid proposition, create a problem
    for idx, prop in enumerate(propositions, start=1):
        if idx in error_conclusions:
            continue

        # This proposition is the conclusion
        conclusion = prop

        # Other propositions become additional hypotheses
        extra_hypotheses = [p for i, p in enumerate(propositions, start=1) if i != idx]

        # Combine description and extra hypotheses
        base_hypotheses = list(description) + extra_hypotheses

        # Create problem ID
        problem_id = f"{pinyin_prefix}_{number}_c{idx}"

        # Create problem record
        problem = {
            "id": problem_id,
            "text": f"{name} #{number} 结论{idx}",
            "points": points,
            "base_hypotheses_wl": base_hypotheses,
            "conclusion_wl": conclusion,
            "qualitative_objects": {"polygons": polygons} if polygons else {},
            "meta": {"source": name, "number": number, "conclusion_idx": idx},
        }

        problems.append(problem)

    return problems


def main() -> None:
    """Main entry point."""
    input_file = PROJECT_ROOT / "question_test.txt"
    output_file = PROJECT_ROOT / "data" / "problems.jsonl"

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Read input file
    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        return

    content = input_file.read_text(encoding="utf-8")

    # Split into blocks
    blocks = split_into_blocks(content)
    print(f"Found {len(blocks)} question blocks")

    # Parse each block and generate problems
    all_problems = []
    for block in blocks:
        question = parse_question_block(block)
        if question:
            problems = generate_problems(question)
            all_problems.extend(problems)
            print(
                f"  Parsed '{question['name']}' #{question['number']}: "
                f"{len(problems)} problems"
            )

    # Write output
    with output_file.open("w", encoding="utf-8") as f:
        for problem in all_problems:
            f.write(json.dumps(problem, ensure_ascii=False) + "\n")

    print(f"\nGenerated {len(all_problems)} problems to {output_file}")


if __name__ == "__main__":
    main()
