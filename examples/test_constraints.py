#!/usr/bin/env python3
"""
快速测试新约束构建器的功能
"""
import sys
from pathlib import Path

# 添加 scripts 目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from wolframclient.evaluation import WolframLanguageSession
from wolframclient.language import wl, wlexpr, Global
from wolframclient.language.expression import WLSymbol
from constraints import build_orientation, build_angle_min, build_side_ratio, build_height_base, build_height_perimeter

def test_constraints():
    """测试所有约束构建器"""
    wl_kernel = "D:/Program Files/Wolfram Research/Wolfram/14.3/wolfram.exe"
    print("初始化 Wolfram 会话...")
    session = WolframLanguageSession(wl_kernel)
    
    try:
        # 加载 scene_builders.wl
        print("加载 scene_builders.wl...")
        wl_dir = Path(__file__).parent.parent / "wl"
        session.evaluate(wlexpr(f'Get["{wl_dir}/scene_builders.wl"]'))
        
        # 测试点
        points = wl.List(WLSymbol("A"), WLSymbol("B"), WLSymbol("C"))
        base_edge = wl.List(WLSymbol("B"), WLSymbol("C"))
        
        print("\n✅ 测试 1: build_orientation")
        constraints = build_orientation(points, base_edge)
        print(f"   生成 {len(constraints)} 个约束")
        result = session.evaluate(wlexpr(f"Length[{constraints[0]}]"))
        print(f"   Wolfram 验证：约束列表长度 = {result}")
        
        print("\n✅ 测试 2: build_angle_min (10°)")
        constraints = build_angle_min(points, 10)
        print(f"   生成 {len(constraints)} 个约束")
        result = session.evaluate(wlexpr(f"Length[{constraints[0]}]"))
        print(f"   Wolfram 验证：约束列表长度 = {result}")
        
        print("\n✅ 测试 3: build_side_ratio (0.3)")
        constraints = build_side_ratio(points, 0.3)
        print(f"   生成 {len(constraints)} 个约束")
        result = session.evaluate(constraints[0])
        print(f"   Wolfram 验证：约束 = {result}")
        
        print("\n✅ 测试 4: build_height_base (0.2)")
        constraints = build_height_base(points, base_edge, 0.2)
        print(f"   生成 {len(constraints)} 个约束")
        result = session.evaluate(constraints[0])
        print(f"   Wolfram 验证：约束 = {result}")
        
        print("\n✅ 测试 5: build_height_perimeter (0.08)")
        constraints = build_height_perimeter(points, 0.08)
        print(f"   生成 {len(constraints)} 个约束")
        result = session.evaluate(constraints[0])
        print(f"   Wolfram 验证：约束 = {result}")
        
        print("\n✅ 测试 6: 组合所有约束")
        all_constraints = []
        all_constraints.extend(build_orientation(points, base_edge))
        all_constraints.extend(build_angle_min(points, 10))
        all_constraints.extend(build_side_ratio(points, 0.3))
        all_constraints.extend(build_height_base(points, base_edge, 0.2))
        
        print(f"   总约束数 = {len(all_constraints)}")
        
        # 测试 AssembleScene
        base_hyp = wl.List(wlexpr("EuclideanDistance[A, B] == EuclideanDistance[A, C]"))
        scene = session.evaluate(
            Global.AssembleScene(points, base_hyp, wl.List(*all_constraints))
        )
        print(f"   成功组装 GeometricScene")
        print(f"   场景头 = {type(scene)}")
        
        print("\n✅ 所有测试通过！")
        
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.terminate()

if __name__ == "__main__":
    test_constraints()
