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


def AssembleConstraints(
    points: wl.List,
    base_edge: wl.List,
    shape_configs: list
):
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
