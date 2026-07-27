# SPDX-License-Identifier: GPL-3.0-or-later
"""羽衣 — 簡易アニメーション用 N パネル。"""

from __future__ import annotations

import os
import tomllib

import bpy
from bpy.app.handlers import persistent
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import Collection, Object, Operator, Panel, PropertyGroup

from .simulation import (
    HAGOROMO_BAKED_ROLE,
    HAGOROMO_ROLE,
    HAGOROMO_SIMULATION_ROLE,
    INTERNAL_SUBSTEPS,
    SimulationRunner,
    bake_output_collection,
    detect_yohsai_inputs,
    ready_output_for_source,
)


_active_runner: SimulationRunner | None = None
_active_operator = None

_PERFORMANCE_PRESETS = {
    "FAST": (2.0, 0.75, 10),
    "STANDARD": (1.0, 1.0, 20),
    "QUALITY": (0.5, 0.5, 30),
}


def _version() -> str:
    try:
        path = os.path.join(os.path.dirname(__file__), "blender_manifest.toml")
        with open(path, "rb") as handle:
            return str(tomllib.load(handle).get("version", "?"))
    except Exception:
        return "?"


def _mesh_poll(_properties, obj: Object) -> bool:
    return obj is not None and obj.type == "MESH"


def _clothes_poll(_properties, collection: Collection) -> bool:
    return collection is not None and collection.get("yohsai_role") == "clothes"


def _apply_performance_preset(properties, _context) -> None:
    values = _PERFORMANCE_PRESETS.get(properties.performance_preset)
    if values is None:
        return
    properties.preset_updating = True
    try:
        properties.maximum_step_cm = values[0]
        properties.contact_clearance_cm = values[1]
        properties.solver_iterations = values[2]
    finally:
        properties.preset_updating = False


def _mark_custom_preset(properties, _context) -> None:
    if not properties.preset_updating and properties.performance_preset != "CUSTOM":
        properties.performance_preset = "CUSTOM"


class HAGOROMO_PG_settings(PropertyGroup):
    source_collection: PointerProperty(
        name="Yohsai 服",
        description="初期状態として使う、Yohsai で完成した服コレクション",
        type=Collection,
        poll=_clothes_poll,
    )
    body_object: PointerProperty(
        name="ボディ",
        description="衝突に使うアーマチュア変形メッシュ",
        type=Object,
        poll=_mesh_poll,
    )
    start_frame: IntProperty(
        name="開始フレーム",
        description="キャッシュする最初の服フレーム",
        default=1,
    )
    end_frame: IntProperty(
        name="終了フレーム",
        description="キャッシュする最後の服フレーム",
        default=250,
    )
    performance_preset: EnumProperty(
        name="パフォーマンス",
        description="速度と品質の起点。値を直接いじるとカスタムになります",
        items=(
            ("FAST", "高速", "ボディ分割とソルバ反復を減らして素早く確認"),
            ("STANDARD", "標準", "プレビュー向けのバランス設定"),
            ("QUALITY", "高品質", "ボディ分割を細かくし収束を強める"),
            ("CUSTOM", "カスタム", "手動で編集した値を使う"),
        ),
        default="STANDARD",
        update=_apply_performance_preset,
    )
    maximum_step_cm: FloatProperty(
        name="最大ボディステップ (cm)",
        description="1回の重力計算あたりに許すボディ頂点の最大移動量",
        default=1.0,
        min=0.01,
        soft_max=10.0,
        precision=3,
        update=_mark_custom_preset,
    )
    contact_clearance_cm: FloatProperty(
        name="接触クリアランス (cm)",
        description="接触で保つボディ表面との距離。大きいほど貫通は減るが服が浮く",
        default=1.0,
        min=0.05,
        max=4.0,
        soft_max=1.0,
        precision=3,
        update=_mark_custom_preset,
    )
    solver_iterations: IntProperty(
        name="ソルバ反復回数",
        description="内部サブステップごとの材料・ボディ接触の収束回数",
        default=20,
        min=1,
        max=128,
        soft_max=40,
        update=_mark_custom_preset,
    )
    status: StringProperty(name="状態", default="準備完了")
    progress: FloatProperty(name="進捗", default=0.0, min=0.0, max=1.0, subtype="FACTOR")
    range_initialized: BoolProperty(default=False, options={"HIDDEN"})
    preset_updating: BoolProperty(default=False, options={"HIDDEN", "SKIP_SAVE"})


def _initialize_scene(scene: bpy.types.Scene) -> None:
    if not hasattr(scene, "hagoromo"):
        return
    props = scene.hagoromo
    if not props.range_initialized:
        props.start_frame = int(scene.frame_start)
        props.end_frame = int(scene.frame_end)
        props.range_initialized = True
    collection, body = detect_yohsai_inputs(scene)
    if props.source_collection is None and collection is not None:
        props.source_collection = collection
    if props.body_object is None and body is not None:
        props.body_object = body


def _initialize_scenes_after_register():
    """Initialize Scene settings after Blender releases registration restrictions."""
    if not hasattr(bpy.types.Scene, "hagoromo"):
        return None
    try:
        scenes = bpy.data.scenes
    except AttributeError:
        # Extension registration temporarily replaces bpy.data with
        # _RestrictData. Retry once the normal Blender context is restored.
        return 0.1
    for scene in scenes:
        _initialize_scene(scene)
    return None


@persistent
def _load_post(_unused) -> None:
    global _active_runner, _active_operator
    if _active_runner is not None and _active_runner.runtime is not None:
        _active_runner.runtime.close()
    _active_runner = None
    _active_operator = None
    _initialize_scenes_after_register()


class HAGOROMO_OT_detect_inputs(Operator):
    bl_idname = "hagoromo.detect_inputs"
    bl_label = "Yohsai 入力を検出"
    bl_description = "シーン内の完成済み Yohsai 服とボディを自動検出して設定する"

    def execute(self, context):
        collection, body = detect_yohsai_inputs(context.scene)
        if collection is None or body is None:
            self.report({"ERROR"}, "完成済みの Yohsai 服とボディの両方を見つけられませんでした。")
            return {"CANCELLED"}
        props = context.scene.hagoromo
        props.source_collection = collection
        props.body_object = body
        props.status = f"検出: {collection.name} と {body.name}"
        return {"FINISHED"}


class HAGOROMO_OT_simulate(Operator):
    bl_idname = "hagoromo.simulate"
    bl_label = "アニメーションをシミュレート"
    bl_description = "自動分割したボディ姿勢ごとに計算し、整数フレームを Shape Key にキャッシュする"
    bl_options = {"REGISTER", "UNDO"}

    _timer = None

    def _stop_timer(self, context) -> None:
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None

    def _clear_active(self) -> None:
        global _active_runner, _active_operator
        _active_runner = None
        _active_operator = None

    def _fail(self, context, message: str):
        global _active_runner
        if _active_runner is not None:
            _active_runner.cancel()
        self._stop_timer(context)
        self._clear_active()
        context.scene.hagoromo.status = f"失敗: {message[:220]}"
        context.scene.hagoromo.progress = 0.0
        self.report({"ERROR"}, message)
        return {"CANCELLED"}

    def execute(self, context):
        global _active_runner, _active_operator
        if _active_runner is not None:
            self.report({"WARNING"}, "羽衣のシミュレーションは既に実行中です。")
            return {"CANCELLED"}
        props = context.scene.hagoromo
        if props.source_collection is None or props.body_object is None:
            collection, body = detect_yohsai_inputs(context.scene)
            if props.source_collection is None:
                props.source_collection = collection
            if props.body_object is None:
                props.body_object = body
        try:
            runner = SimulationRunner(
                context,
                props.source_collection,
                props.body_object,
                props.start_frame,
                props.end_frame,
                props.maximum_step_cm,
                props.contact_clearance_cm,
                props.solver_iterations,
            )
        except Exception as exc:
            message = str(exc).strip() or type(exc).__name__
            props.status = f"失敗: {message[:220]}"
            self.report({"ERROR"}, message)
            return {"CANCELLED"}

        _active_runner = runner
        _active_operator = self
        props.status = runner.status
        props.progress = runner.progress
        if bpy.app.background:
            try:
                summary = runner.run_to_completion(context)
            except Exception as exc:
                return self._fail(context, str(exc).strip() or type(exc).__name__)
            props.status = summary
            props.progress = 1.0
            self._clear_active()
            self.report({"INFO"}, summary)
            return {"FINISHED"}

        self._timer = context.window_manager.event_timer_add(0.01, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        global _active_runner
        if event.type == "ESC":
            if _active_runner is not None:
                _active_runner.cancel()
            self._stop_timer(context)
            self._clear_active()
            context.scene.hagoromo.status = "キャンセルしました"
            context.scene.hagoromo.progress = 0.0
            return {"CANCELLED"}
        if event.type != "TIMER":
            return {"PASS_THROUGH"}
        runner = _active_runner
        if runner is None:
            return self._fail(context, "実行中の羽衣シミュレーションが見つかりません。")
        try:
            has_more = runner.advance_one(context)
            context.scene.hagoromo.status = runner.status
            context.scene.hagoromo.progress = runner.progress
            if has_more:
                return {"RUNNING_MODAL"}
            summary = runner.finish()
        except Exception as exc:
            return self._fail(context, str(exc).strip() or type(exc).__name__)
        self._stop_timer(context)
        self._clear_active()
        context.scene.hagoromo.status = summary
        context.scene.hagoromo.progress = 1.0
        self.report({"INFO"}, summary)
        return {"FINISHED"}

    def cancel(self, context):
        global _active_runner
        if _active_runner is not None:
            _active_runner.cancel()
        self._stop_timer(context)
        self._clear_active()


class HAGOROMO_OT_bake_result(Operator):
    bl_idname = "hagoromo.bake_result"
    bl_label = "羽衣結果をベイク"
    bl_description = "完成した Shape Key キャッシュを確定し、後のシミュレーションで置換されないようにする"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if _active_runner is not None or not hasattr(context.scene, "hagoromo"):
            return False
        return ready_output_for_source(context.scene.hagoromo.source_collection) is not None

    def execute(self, context):
        props = context.scene.hagoromo
        output = ready_output_for_source(props.source_collection)
        try:
            name = bake_output_collection(output)
        except Exception as exc:
            message = str(exc).strip() or type(exc).__name__
            props.status = f"ベイク失敗: {message[:220]}"
            self.report({"ERROR"}, message)
            return {"CANCELLED"}
        props.status = f"ベイク済み: {name}"
        self.report({"INFO"}, props.status)
        return {"FINISHED"}


class HAGOROMO_PT_main(Panel):
    bl_label = "羽衣"
    bl_idname = "HAGOROMO_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "羽衣"

    def draw(self, context):
        layout = self.layout
        props = context.scene.hagoromo
        layout.label(text=f"羽衣  v{_version()}")
        inputs = layout.column(align=True)
        inputs.enabled = _active_runner is None
        inputs.prop(props, "source_collection")
        inputs.prop(props, "body_object")
        inputs.operator(HAGOROMO_OT_detect_inputs.bl_idname, icon="EYEDROPPER")
        layout.separator(factor=0.5)
        settings = layout.column(align=True)
        settings.enabled = _active_runner is None
        settings.prop(props, "start_frame")
        settings.prop(props, "end_frame")
        settings.prop(props, "performance_preset")
        settings.prop(props, "maximum_step_cm")
        settings.prop(props, "contact_clearance_cm")
        settings.prop(props, "solver_iterations")
        settings.label(
            text=(
                f"ボディステップあたり: {INTERNAL_SUBSTEPS} × {props.solver_iterations} = "
                f"{INTERNAL_SUBSTEPS * props.solver_iterations} 接触パス"
            )
        )
        layout.separator(factor=0.5)
        row = layout.row()
        row.enabled = _active_runner is None
        row.scale_y = 1.4
        row.operator(HAGOROMO_OT_simulate.bl_idname, icon="PLAY")
        bake_row = layout.row()
        bake_row.enabled = (
            _active_runner is None
            and ready_output_for_source(props.source_collection) is not None
        )
        bake_row.operator(HAGOROMO_OT_bake_result.bl_idname, icon="REC")
        if _active_runner is not None:
            layout.label(text="Esc でキャンセル", icon="EVENT_ESC")
        layout.prop(props, "progress", text="")
        layout.label(text=props.status, icon="INFO")
        outputs = [
            collection
            for collection in bpy.data.collections
            if collection.get(HAGOROMO_ROLE) == HAGOROMO_SIMULATION_ROLE
            and bool(collection.get("hagoromo_cache_ready", False))
        ]
        if outputs:
            layout.label(text=f"キャッシュ: {outputs[-1].name}", icon="OUTLINER_COLLECTION")
        baked = [
            collection
            for collection in bpy.data.collections
            if collection.get(HAGOROMO_ROLE) == HAGOROMO_BAKED_ROLE
        ]
        if baked:
            layout.label(text=f"ベイク済み: {baked[-1].name}", icon="CHECKMARK")


_CLASSES = (
    HAGOROMO_PG_settings,
    HAGOROMO_OT_detect_inputs,
    HAGOROMO_OT_simulate,
    HAGOROMO_OT_bake_result,
    HAGOROMO_PT_main,
)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.hagoromo = PointerProperty(type=HAGOROMO_PG_settings)
    if _load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post)
    if not bpy.app.timers.is_registered(_initialize_scenes_after_register):
        bpy.app.timers.register(_initialize_scenes_after_register, first_interval=0.0)


def unregister() -> None:
    global _active_runner, _active_operator
    if _active_runner is not None:
        _active_runner.cancel()
    _active_runner = None
    _active_operator = None
    if bpy.app.timers.is_registered(_initialize_scenes_after_register):
        bpy.app.timers.unregister(_initialize_scenes_after_register)
    if _load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_post)
    if hasattr(bpy.types.Scene, "hagoromo"):
        del bpy.types.Scene.hagoromo
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
