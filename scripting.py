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

# ボーン1：商品の手前の辺（底面）から上面までの折り目
bone1 = armature.data.edit_bones.new("FoldBone_Bottom")
bone1.head = (0, -half_depth, 0)           # ボーンの根本：商品の手前の辺の中心（底面）
bone1.tail = (0, -half_depth, box_height)  # ボーンの先端：商品の手前の辺の上面

# ボーン2：商品の上面から包装紙の先端までの折り目（親子関係を設定）
bone2 = armature.data.edit_bones.new("FoldBone_Top")
bone2.head = (0, -half_depth, box_height)          # ボーンの根本：商品の上面の手前の辺
# ボーンの先端を奥方向（Y軸の正方向）に伸ばす
bone2.tail = (0, -half_depth + (paper_corner_y + half_depth), box_height)
bone2.parent = bone1  # bone1の子にする（bone1が回転するとbone2も一緒に回転する）

bpy.ops.object.mode_set(mode='OBJECT')

# 2. 包装紙をアーマチュアの子にする（ウェイトなし）
paper.select_set(True)
armature.select_set(True)
bpy.context.view_layer.objects.active = armature
bpy.ops.object.parent_set(type='ARMATURE')

# 3. 頂点グループを手動で設定（商品の底面の包装紙は動かさない）
bpy.ops.object.select_all(action='DESELECT')
paper.select_set(True)
bpy.context.view_layer.objects.active = paper

# 頂点グループを作成
vertex_group_bottom = paper.vertex_groups.new(name="FoldBone_Bottom")
vertex_group_top = paper.vertex_groups.new(name="FoldBone_Top")

# 包装紙の頂点にウェイトを設定
for v in paper.data.vertices:
    # ワールド座標を取得（45度回転を考慮）
    world_co = paper.matrix_world @ v.co

    # 商品の底面の範囲を定義
    inside_box = (abs(world_co.x) <= half_width and abs(world_co.y) <= half_depth)

    # 折り目より手前側（Y < -half_depth）の頂点にウェイトを設定
    if world_co.y < -half_depth and not inside_box:
        # 底面の折り目からの距離
        distance_from_bottom = abs(world_co.y + half_depth)

        # 立ち上がった後の上面の折り目の位置（底面から box_height の距離）
        # 上面の折り目より手前側は FoldBone_Top に、それ以外は FoldBone_Bottom に
        if distance_from_bottom > box_height:
            # 上面より先の部分：FoldBone_Topの影響を主に受ける
            # 上面の折り目からの距離を計算
            distance_from_top_fold = distance_from_bottom - box_height
            max_distance = abs(paper_corner_y + half_depth) - box_height

            # 折り目に近い部分はBottomの影響も少し受けるが、先端に行くほど受けない
            # Bottomウェイト: 折り目=1.0 → 先端=0.0
            weight_bottom = max(0.0, 1.0 - (distance_from_top_fold / max_distance))
            vertex_group_bottom.add([v.index], weight_bottom, 'REPLACE')

            # Topウェイト: 常に1.0（上面の折り曲げを確実に反映）
            vertex_group_top.add([v.index], 1.0, 'REPLACE')
        else:
            # 底面から上面までの部分：FoldBone_Bottom のみ
            weight = min(1.0, distance_from_bottom / 0.5)
            vertex_group_bottom.add([v.index], weight, 'REPLACE')
            # FoldBone_Top の影響は受けない（ウェイト0）
            vertex_group_top.add([v.index], 0.0, 'REPLACE')


# --- ステップ3：アニメーションの設定（斜め包み） ---

# アニメーションのフレーム範囲を設定
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = 120

# アーマチュアを選択してポーズモードに切り替え
bpy.ops.object.select_all(action='DESELECT')
armature.select_set(True)
bpy.context.view_layer.objects.active = armature
bpy.ops.object.mode_set(mode='POSE')

# 2つのボーンを取得
pbone_bottom = armature.pose.bones["FoldBone_Bottom"]
pbone_top = armature.pose.bones["FoldBone_Top"]
pbone_bottom.rotation_mode = 'XYZ'
pbone_top.rotation_mode = 'XYZ'

# フレーム1: 初期位置（平らな状態）
bpy.context.scene.frame_set(1)
pbone_bottom.rotation_euler = (0, 0, 0)
pbone_top.rotation_euler = (0, 0, 0)
pbone_bottom.keyframe_insert(data_path="rotation_euler", frame=1)
pbone_top.keyframe_insert(data_path="rotation_euler", frame=1)

# フレーム60: 第1段階 - 90度上空に立ち上げる（商品の手前の面に沿って垂直にする）
bpy.context.scene.frame_set(60)
pbone_bottom.rotation_euler[0] = math.radians(-90)  # X軸で-90度回転（上方向に立ち上げる）
pbone_top.rotation_euler = (0, 0, 0)  # まだ折らない
pbone_bottom.keyframe_insert(data_path="rotation_euler", frame=60)
pbone_top.keyframe_insert(data_path="rotation_euler", frame=60)

# フレーム120: 第2段階 - 商品の上面の高さで90度折り曲げて覆いかぶせる
bpy.context.scene.frame_set(120)
pbone_bottom.rotation_euler[0] = math.radians(-90)  # 第1段階の状態を維持
# bone2はbone1の子なので、bone1の-90度回転に対して、さらに+90度回転して合計0度にする
# これにより、包装紙が水平になる（商品の上面に平行）
pbone_top.rotation_euler[0] = math.radians(90)      # 上面で+90度折り曲げる（合計0度で水平）
pbone_top.rotation_euler[1] = 0  # Y軸回転なし
pbone_top.rotation_euler[2] = 0  # Z軸回転なし
pbone_bottom.keyframe_insert(data_path="rotation_euler", frame=120)
pbone_top.keyframe_insert(data_path="rotation_euler", frame=120)

# オブジェクトモードに戻る
bpy.ops.object.mode_set(mode='OBJECT')

# カメラとライトを追加（見やすくするため）
bpy.ops.object.camera_add(location=(10, -10, 8))
camera = bpy.context.active_object
camera.rotation_euler = (math.radians(60), 0, math.radians(45))
bpy.context.scene.camera = camera

bpy.ops.object.light_add(type='SUN', location=(5, 5, 10))

print("斜め包みアニメーションの作成が完了しました。")