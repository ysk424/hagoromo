# SPDX-License-Identifier: GPL-3.0-or-later
"""羽衣 — Yohsai 完成服向けの簡易 GPU 布アニメーション。"""

from __future__ import annotations

from . import ui


def register():
    ui.register()


def unregister():
    ui.unregister()
