"""
GeometricScene Constraint Builders - Python Pipeline Functions

每个函数都是纯函数：
  输入：wl 表达式 (points, parameters)
  输出：wl 表达式 (constraints)

调用方：Agents (bench-runner, problem-constraint-designer)

用法:
  from core import BuildOrientation, BuildAngleMin, ...

  constraints = []
  constraints.append(BuildOrientation(points_wl, base_edge_wl))
  constraints.append(BuildAngleMin(points_wl, 10))

  scene = session.evaluate(
    Global.AssembleScene(points_wl, base_hyp_wl, wl.List(*constraints))
  )
"""

from wolframclient.language import wl, wlexpr, Global
from wolframclient.language.expression import WLSymbol


def BuildOrientation(points: wl.List, base_edge: wl.List):
    """
    构建朝向约束 (Horizontal, Rightward, Counterclockwise, Distinct)

    Args:
        points: wl.List of point symbols
        base_edge: wl.List of 2 point symbols for base edge

    Returns:
        Wolfram expression (GeometricAssertion list)
    """
    return Global.BuildOrientation(points, base_edge)


def BuildAngleMin(points: wl.List, min_deg: float):
    """
    构建角度下界约束

    Args:
        points: wl.List of point symbols
        min_deg: minimum angle in degrees

    Returns:
        Wolfram expression (PlanarAngle constraints)
    """
    return Global.BuildAngleMin(points, min_deg)


def BuildSideRatio(points: wl.List, min_ratio: float):
    """
    构建边长比约束 (MinSide/MaxSide > min_ratio)

    Args:
        points: wl.List of 3 point symbols
        min_ratio: minimum ratio value

    Returns:
        Wolfram expression (side ratio inequality)
    """
    return Global.BuildSideRatio(points, min_ratio)


def BuildHeightBase(points: wl.List, base_edge: wl.List, min_ratio: float):
    """
    构建高度/底边比约束

    Args:
        points: wl.List of 3 point symbols
        base_edge: wl.List of 2 point symbols for base edge
        min_ratio: minimum height/base ratio

    Returns:
        Wolfram expression (height/base inequality)
    """
    return Global.BuildHeightBase(points, base_edge, min_ratio)


def BuildHeightPerimeter(points: wl.List, min_ratio: float):
    """
    构建高度/周长比约束

    Args:
        points: wl.List of 3 point symbols
        min_ratio: minimum height/perimeter ratio

    Returns:
        Wolfram expression (height/perimeter inequality)
    """
    return Global.BuildHeightPerimeter(points, min_ratio)


def AssembleConstraints(points: wl.List, base_edge: wl.List, shape_configs: list):
    """
    根据配置组装所有约束

    Args:
        points: wl.List of point symbols
        base_edge: wl.List of 2 point symbols
        shape_configs: list of constraint configs from YAML

    Returns:
        List of Wolfram expressions
    """
    constraints = []

    for shape in shape_configs:
        constraint_type = shape["type"]

        if constraint_type == "angle_min":
            constraints.append(BuildAngleMin(points, shape["min_deg"]))

        elif constraint_type == "side_ratio":
            constraints.append(BuildSideRatio(points, shape["min_ratio"]))

        elif constraint_type == "height_base":
            constraints.append(BuildHeightBase(points, base_edge, shape["min_ratio"]))

        elif constraint_type == "height_perimeter":
            constraints.append(BuildHeightPerimeter(points, shape["min_ratio"]))

        else:
            raise ValueError(f"Unknown constraint type: {constraint_type}")

    return constraints


# ============ 定性约束构建函数 ============


def BuildHorizontalLine(edge: wl.List):
    """
    构建水平线约束

    Args:
        edge: wl.List of 2 point symbols

    Returns:
        Wolfram expression (GeometricAssertion)
    """
    return Global.BuildHorizontalLine(edge)


def BuildClockwise(points: wl.List):
    """
    构建顺时针约束

    Args:
        points: wl.List of point symbols (polygon vertices)

    Returns:
        Wolfram expression (GeometricAssertion)
    """
    return Global.BuildClockwise(points)


def BuildCounterclockwise(points: wl.List):
    """
    构建逆时针约束

    Args:
        points: wl.List of point symbols (polygon vertices)

    Returns:
        Wolfram expression (GeometricAssertion)
    """
    return Global.BuildCounterclockwise(points)


def BuildPointInPolygon(point, poly_points: wl.List):
    """
    构建点在多边形内的约束

    Args:
        point: single point symbol
        poly_points: wl.List of polygon vertices

    Returns:
        Wolfram expression (Element constraint)
    """
    return Global.BuildPointInPolygon(point, poly_points)


def BuildPointInTriangle(point, tri_points: wl.List):
    """
    构建点在三角形内的约束

    Args:
        point: single point symbol
        tri_points: wl.List of triangle vertices

    Returns:
        Wolfram expression (Element constraint)
    """
    return Global.BuildPointInTriangle(point, tri_points)


def AssembleQualitativeConstraints(
    qualitative_configs: list, qualitative_objects: dict, points_list: list
):
    """
    根据定性约束配置和几何对象组装定性约束

    Args:
        qualitative_configs: list of qualitative constraint configs from YAML
        qualitative_objects: dict from problem containing polygons, circles, angles
        points_list: list of all point symbols (strings)

    Returns:
        List of Wolfram expressions
    """
    constraints = []

    # Normalize to list
    if isinstance(qualitative_configs, dict):
        qualitative_configs = [qualitative_configs]

    for qual_config in qualitative_configs:
        qual_type = qual_config.get("type")
        source = qual_config.get("source")

        if qual_type == "horizontal":
            # 水平线约束只能施加在题干多边形的边上
            if source == "polygon_edge":
                polygons = qualitative_objects.get("polygons", [])
                if polygons:
                    idx = qual_config.get("index", 0)
                    if idx < len(polygons):
                        poly_points = polygons[idx]["points"]
                        edge_idx = qual_config.get("edge_index", 0)
                        n = len(poly_points)
                        # 选择多边形的第 edge_idx 条边
                        p1 = poly_points[edge_idx % n]
                        p2 = poly_points[(edge_idx + 1) % n]
                        edge_wl = wl.List(WLSymbol(p1), WLSymbol(p2))
                        constraints.append(BuildHorizontalLine(edge_wl))

        elif qual_type == "clockwise":
            # 顺时针约束只能加在题干给的多边形/圆/角上
            if source == "polygon":
                polygons = qualitative_objects.get("polygons", [])
                if polygons:
                    idx = qual_config.get("index", 0)
                    if idx < len(polygons):
                        poly_points = polygons[idx]["points"]
                        points_wl = wl.List(*[WLSymbol(p) for p in poly_points])
                        constraints.append(BuildClockwise(points_wl))

        elif qual_type == "counterclockwise":
            # 逆时针约束只能加在题干给的多边形/圆/角上
            if source == "polygon":
                polygons = qualitative_objects.get("polygons", [])
                if polygons:
                    idx = qual_config.get("index", 0)
                    if idx < len(polygons):
                        poly_points = polygons[idx]["points"]
                        points_wl = wl.List(*[WLSymbol(p) for p in poly_points])
                        constraints.append(BuildCounterclockwise(points_wl))

        elif qual_type == "region":
            # 区域约束只能施加在题干给的多边形/圆上
            if source == "polygon":
                polygons = qualitative_objects.get("polygons", [])
                if polygons:
                    poly_idx = qual_config.get("polygon_index", 0)
                    if poly_idx < len(polygons):
                        poly_points = polygons[poly_idx]["points"]
                        poly_points_wl = wl.List(*[WLSymbol(p) for p in poly_points])

                        # 选择要约束的点
                        point_spec = qual_config.get("point", "first_constructed")
                        point_symbol = _select_point_for_region(
                            point_spec, points_list, poly_points
                        )
                        if point_symbol:
                            constraints.append(
                                BuildPointInPolygon(point_symbol, poly_points_wl)
                            )

    return constraints


def _select_point_for_region(point_spec: str, all_points: list, poly_points: list):
    """
    选择要应用区域约束的点

    Args:
        point_spec: point specification string
        all_points: list of all point symbols
        poly_points: list of polygon vertex symbols

    Returns:
        WLSymbol or None
    """
    poly_set = set(poly_points)

    if point_spec == "first_constructed":
        # 找到第一个非多边形顶点的点（构造点）
        for p in all_points:
            if p not in poly_set:
                return WLSymbol(p)
    elif point_spec == "last_constructed":
        # 找到最后一个非多边形顶点的点
        for p in reversed(all_points):
            if p not in poly_set:
                return WLSymbol(p)
    elif point_spec.startswith("point_"):
        # 指定第N个点 (point_0, point_1, ...)
        idx = int(point_spec.split("_")[1])
        if 0 <= idx < len(all_points):
            return WLSymbol(all_points[idx])
    else:
        # 直接指定点名
        if point_spec in all_points:
            return WLSymbol(point_spec)

    return None
