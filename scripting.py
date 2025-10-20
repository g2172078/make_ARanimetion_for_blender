import bpy
import math

# 0. 初期設定（既存のオブジェクトを全て削除）
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# --- ステップ1：シーンの準備 ---

# 1. 箱を作成（通常の向きで配置）
box_dims = (3, 2, 1.5)  # 箱の寸法（幅、奥行き、高さ）
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, box_dims[2] / 2))
box = bpy.context.active_object
box.name = "Box"
box.scale = (box_dims[0], box_dims[1], box_dims[2])
bpy.ops.object.transform_apply(scale=True)

# 2. 包装紙（平面）を作成（45度回転させる）
paper_size = 8
# 包装紙を箱の底面の高さ（Z=0）に配置、少し左と手前に移動
paper_offset_x = -1.0  # 左に移動する量
paper_offset_y = -1.0  # 手前に移動する量
bpy.ops.mesh.primitive_plane_add(size=paper_size, location=(paper_offset_x, paper_offset_y, 0))
paper = bpy.context.active_object
paper.name = "WrappingPaper"
paper.rotation_euler[2] = math.radians(45)  # Z軸で45度回転（斜め配置）

# 細かく曲げられるように、メッシュを細分化
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=60)
bpy.ops.object.mode_set(mode='OBJECT')


# --- ステップ2：骨格（アーマチュア）の作成 ---

# 1. アーマチュアオブジェクトを作成
bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
armature = bpy.context.active_object
armature.name = "WrappingArmature"

# 最初のボーンを削除
bpy.ops.armature.select_all(action='SELECT')
bpy.ops.armature.delete()

# 商品の辺と包装紙の角の位置を計算
half_width = box_dims[0] / 2
half_depth = box_dims[1] / 2

# 包装紙が45度回転しているので、手前の角は (0, -paper_size/2, 0) の位置にある
paper_corner_y = -paper_size / 2
box_height = box_dims[2]

# === 手前の面：商品の手前の辺（底面）から上面までの折り目 ===
bone_front_bottom = armature.data.edit_bones.new("FoldBone_Front_Bottom")
bone_front_bottom.head = (0, -half_depth, 0)           # ボーンの根本：商品の手前の辺の中心（底面）
bone_front_bottom.tail = (0, -half_depth, box_height)  # ボーンの先端：商品の手前の辺の上面

# 商品の上面から包装紙の先端までの折り目（親子関係を設定）
bone_front_top = armature.data.edit_bones.new("FoldBone_Front_Top")
bone_front_top.head = (0, -half_depth, box_height)          # ボーンの根本：商品の上面の手前の辺
# ボーンの先端を奥方向（Y軸の正方向）に伸ばす
bone_front_top.tail = (0, -half_depth + (paper_corner_y + half_depth), box_height)
bone_front_top.parent = bone_front_bottom  # bone_front_bottomの子にする

# === 左側の面：垂直に立ち上げるボーン ===
# 包装紙の左端の位置を計算（45度回転を考慮）
paper_left_edge = -paper_size/2 + paper_offset_x

bone_left_side = armature.data.edit_bones.new("FoldBone_Left_Side")
bone_left_side.head = (-half_width, -half_depth, 0)  # ボーンの根本：商品の手前左下の角（底面）
bone_left_side.tail = (paper_left_edge, -half_depth, 0)  # ボーンの先端：左側の包装紙の端

# === 手前側面の三角形織り込み用ボーン ===
# 左側の包装紙が垂直に立ち上がった時、手前側面に飛び出る三角形部分を内側（谷折り）に折り込むためのボーン
# 谷折りで内側に押し込むため、ボーンは垂直（Z軸方向）に伸ばす
bone_left_front_triangle = armature.data.edit_bones.new("FoldBone_Left_Front_Triangle")
bone_left_front_triangle.head = (-half_width, -half_depth, 0)  # ボーンの根本：商品の手前左下の角（底面）
# 垂直に上方向に伸ばす（立ち上がった後の高さまで）
bone_left_front_triangle.tail = (-half_width, -half_depth, box_height)  # 商品の手前左上の角（上面）
bone_left_front_triangle.parent = bone_left_side  # bone_left_sideの子にする

bpy.ops.object.mode_set(mode='OBJECT')

# 2. 包装紙に頂点グループを手動で設定
bpy.ops.object.select_all(action='DESELECT')
paper.select_set(True)
bpy.context.view_layer.objects.active = paper

# 頂点グループを作成
vertex_group_front_bottom = paper.vertex_groups.new(name="FoldBone_Front_Bottom")
vertex_group_front_top = paper.vertex_groups.new(name="FoldBone_Front_Top")
vertex_group_left_side = paper.vertex_groups.new(name="FoldBone_Left_Side")
vertex_group_left_front_triangle = paper.vertex_groups.new(name="FoldBone_Left_Front_Triangle")

# 包装紙の頂点にウェイトを設定
for v in paper.data.vertices:
    # ワールド座標を取得（45度回転を考慮）
    world_co = paper.matrix_world @ v.co

    # 商品の底面の範囲を定義
    inside_box = (abs(world_co.x) <= half_width and abs(world_co.y) <= half_depth)

    # 底面の包装紙は動かさない（すべてのボーンの影響をゼロに）
    if inside_box:
        vertex_group_front_bottom.add([v.index], 0.0, 'REPLACE')
        vertex_group_front_top.add([v.index], 0.0, 'REPLACE')
        vertex_group_left_side.add([v.index], 0.0, 'REPLACE')
        vertex_group_left_front_triangle.add([v.index], 0.0, 'REPLACE')
        continue

    # === 手前の面：折り目より手前側（Y < -half_depth）の頂点にウェイトを設定 ===
    if world_co.y < -half_depth:
        # 底面の折り目からの距離
        distance_from_bottom = abs(world_co.y + half_depth)

        # 立ち上がった後の上面の折り目の位置（底面から box_height の距離）
        # 上面の折り目より手前側は FoldBone_Front_Top に、それ以外は FoldBone_Front_Bottom に
        if distance_from_bottom > box_height:
            # 上面より先の部分：FoldBone_Front_Topの影響を主に受ける
            # 上面の折り目からの距離を計算
            distance_from_top_fold = distance_from_bottom - box_height
            max_distance = abs(paper_corner_y + half_depth) - box_height

            # 折り目に近い部分はBottomの影響も少し受けるが、先端に行くほど受けない
            # Bottomウェイト: 折り目=1.0 → 先端=0.0
            weight_bottom = max(0.0, 1.0 - (distance_from_top_fold / max_distance))
            vertex_group_front_bottom.add([v.index], weight_bottom, 'REPLACE')

            # Topウェイト: 常に1.0（上面の折り曲げを確実に反映）
            vertex_group_front_top.add([v.index], 1.0, 'REPLACE')

            # 手前の包装紙は左側ボーンの影響を受けない（曲がりを防ぐ）
            vertex_group_left_side.add([v.index], 0.0, 'REPLACE')
            vertex_group_left_front_triangle.add([v.index], 0.0, 'REPLACE')
        else:
            # 底面から上面までの部分：FoldBone_Front_Bottom のみ
            weight = min(1.0, distance_from_bottom / 0.5)
            vertex_group_front_bottom.add([v.index], weight, 'REPLACE')
            # FoldBone_Front_Top の影響は受けない（ウェイト0）
            vertex_group_front_top.add([v.index], 0.0, 'REPLACE')

            # 手前の包装紙は左側ボーンの影響を受けない（曲がりを防ぐ）
            vertex_group_left_side.add([v.index], 0.0, 'REPLACE')
            vertex_group_left_front_triangle.add([v.index], 0.0, 'REPLACE')

    # === 左側の面：手前の底辺より左側の頂点（包装紙の左下の角の領域） ===
    # 包装紙が45度回転しているので、対角線で判定
    # 手前の折り目（Y = -half_depth）より手前で、かつ左側にある領域
    elif world_co.x < -half_width:
        # 手前の底辺の折り目からの距離（X方向）
        distance_from_left = abs(world_co.x + half_width)

        # 手前からの距離（Y方向）
        distance_from_front = abs(world_co.y + half_depth)

        # グラデーションウェイト（折り目に近いほど強く）
        base_weight = min(1.0, distance_from_left / 0.5)

        # 左側の包装紙の基本ウェイト（垂直に立ち上げる）
        vertex_group_left_side.add([v.index], base_weight, 'REPLACE')

        # 手前側面の三角形織り込み領域の判定
        # 左側の包装紙が立ち上がった時、手前側面（Y < -half_depth）に飛び出る三角形部分
        # この部分は織り込みボーンの影響を受ける
        # 三角形の領域：商品の手前左角を中心に、左と手前に広がる領域
        # 対角線より手前側（X + Y が負の大きな値）が三角形領域
        diagonal_distance = (world_co.x + half_width) + (world_co.y + half_depth)

        # 対角線より手前側で、かつ距離が近い部分が三角形織り込みの影響を受ける
        if diagonal_distance < 0 and distance_from_front < abs(paper_left_edge + half_width):
            # 三角形の影響の強さ（対角線からの距離と手前からの距離に応じて）
            triangle_influence = min(1.0, abs(diagonal_distance) / 1.0)
            vertex_group_left_front_triangle.add([v.index], triangle_influence * base_weight, 'REPLACE')
        else:
            vertex_group_left_front_triangle.add([v.index], 0.0, 'REPLACE')

        # 手前のボーンの影響は受けない
        vertex_group_front_bottom.add([v.index], 0.0, 'REPLACE')
        vertex_group_front_top.add([v.index], 0.0, 'REPLACE')

    # === その他の領域：どのボーンにも該当しない頂点 ===
    else:
        # どのボーンの影響も受けない（ウェイト0）
        vertex_group_front_bottom.add([v.index], 0.0, 'REPLACE')
        vertex_group_front_top.add([v.index], 0.0, 'REPLACE')
        vertex_group_left_side.add([v.index], 0.0, 'REPLACE')
        vertex_group_left_front_triangle.add([v.index], 0.0, 'REPLACE')

# 3. 包装紙をアーマチュアの子にする（Armature Deform with Empty Groups）
paper.select_set(True)
armature.select_set(True)
bpy.context.view_layer.objects.active = armature
bpy.ops.object.parent_set(type='ARMATURE')

# アーマチュアモディファイアの設定を確認・調整
for modifier in paper.modifiers:
    if modifier.type == 'ARMATURE':
        modifier.use_vertex_groups = True
        modifier.use_deform_preserve_volume = False


# --- ステップ3：アニメーションの設定（斜め包み） ---

# アニメーションのフレーム範囲を設定
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = 150

# アーマチュアを選択してポーズモードに切り替え
bpy.ops.object.select_all(action='DESELECT')
armature.select_set(True)
bpy.context.view_layer.objects.active = armature
bpy.ops.object.mode_set(mode='POSE')

# ボーンを取得
pbone_front_bottom = armature.pose.bones["FoldBone_Front_Bottom"]
pbone_front_top = armature.pose.bones["FoldBone_Front_Top"]
pbone_left_side = armature.pose.bones["FoldBone_Left_Side"]
pbone_left_front_triangle = armature.pose.bones["FoldBone_Left_Front_Triangle"]

pbone_front_bottom.rotation_mode = 'XYZ'
pbone_front_top.rotation_mode = 'XYZ'
pbone_left_side.rotation_mode = 'XYZ'
pbone_left_front_triangle.rotation_mode = 'XYZ'

# フレーム1: 初期位置（平らな状態）
bpy.context.scene.frame_set(1)
pbone_front_bottom.rotation_euler = (0, 0, 0)
pbone_front_top.rotation_euler = (0, 0, 0)
pbone_left_side.rotation_euler = (0, 0, 0)
pbone_left_front_triangle.rotation_euler = (0, 0, 0)
pbone_front_bottom.keyframe_insert(data_path="rotation_euler", frame=1)
pbone_front_top.keyframe_insert(data_path="rotation_euler", frame=1)
pbone_left_side.keyframe_insert(data_path="rotation_euler", frame=1)
pbone_left_front_triangle.keyframe_insert(data_path="rotation_euler", frame=1)

# === 工程1：手前の紙を立ち上げて上面にかぶせる（フレーム1-90） ===
# 左側のボーンは最初は動かない
bpy.context.scene.frame_set(90)
pbone_left_side.rotation_euler = (0, 0, 0)
pbone_left_front_triangle.rotation_euler = (0, 0, 0)
pbone_left_side.keyframe_insert(data_path="rotation_euler", frame=90)
pbone_left_front_triangle.keyframe_insert(data_path="rotation_euler", frame=90)

# フレーム60: 第1段階 - 90度上空に立ち上げる（商品の手前の面に沿って垂直にする）
bpy.context.scene.frame_set(60)
pbone_front_bottom.rotation_euler[0] = math.radians(-90)  # X軸で-90度回転（上方向に立ち上げる）
pbone_front_top.rotation_euler = (0, 0, 0)  # まだ折らない
pbone_front_bottom.keyframe_insert(data_path="rotation_euler", frame=60)
pbone_front_top.keyframe_insert(data_path="rotation_euler", frame=60)

# フレーム90: 第2段階 - 商品の上面の高さで90度折り曲げて覆いかぶせる
bpy.context.scene.frame_set(90)
pbone_front_bottom.rotation_euler[0] = math.radians(-90)  # 第1段階の状態を維持
# bone2はbone1の子なので、bone1の-90度回転に対して、さらに+90度回転して合計0度にする
# これにより、包装紙が水平になる（商品の上面に平行）
pbone_front_top.rotation_euler[0] = math.radians(90)      # 上面で+90度折り曲げる（合計0度で水平）
pbone_front_top.rotation_euler[1] = 0  # Y軸回転なし
pbone_front_top.rotation_euler[2] = 0  # Z軸回転なし
pbone_front_bottom.keyframe_insert(data_path="rotation_euler", frame=90)
pbone_front_top.keyframe_insert(data_path="rotation_euler", frame=90)

# === 工程2：左側の紙を内側に織り込みながら（谷折り）垂直に立ち上げる（フレーム90-150） ===
# フレーム100: 三角形の織り込み開始（立ち上げより先に内側に押し込み始める）
bpy.context.scene.frame_set(100)
pbone_left_side.rotation_euler[0] = math.radians(30)  # 少しだけ立ち上げ開始
# 谷折りで内側（奥方向 = Y軸正方向）に押し込む
pbone_left_front_triangle.rotation_euler[1] = math.radians(45)  # Y軸で45度回転（内側に押し込み開始）
pbone_left_side.keyframe_insert(data_path="rotation_euler", frame=100)
pbone_left_front_triangle.keyframe_insert(data_path="rotation_euler", frame=100)

# フレーム125: 織り込みと立ち上げを同時進行
bpy.context.scene.frame_set(125)
pbone_left_side.rotation_euler[0] = math.radians(60)  # 立ち上げ途中
pbone_left_front_triangle.rotation_euler[1] = math.radians(70)  # さらに内側に押し込む
pbone_left_side.keyframe_insert(data_path="rotation_euler", frame=125)
pbone_left_front_triangle.keyframe_insert(data_path="rotation_euler", frame=125)

# フレーム150: 左側完全に垂直、三角形完全に織り込み完了
bpy.context.scene.frame_set(150)
pbone_left_side.rotation_euler[0] = math.radians(90)  # X軸で90度回転（完全に垂直）
# 谷折りで完全に内側（商品の側面に沿う）に押し込む
pbone_left_front_triangle.rotation_euler[1] = math.radians(90)  # Y軸で90度回転（完全に内側に押し込む）
pbone_left_side.keyframe_insert(data_path="rotation_euler", frame=150)
pbone_left_front_triangle.keyframe_insert(data_path="rotation_euler", frame=150)

# オブジェクトモードに戻る
bpy.ops.object.mode_set(mode='OBJECT')

# カメラとライトを追加（見やすくするため）
bpy.ops.object.camera_add(location=(10, -10, 8))
camera = bpy.context.active_object
camera.rotation_euler = (math.radians(60), 0, math.radians(45))
bpy.context.scene.camera = camera

bpy.ops.object.light_add(type='SUN', location=(5, 5, 10))

print("斜め包みアニメーション（手前→上面、左側→垂直立ち上げ）の作成が完了しました。")
