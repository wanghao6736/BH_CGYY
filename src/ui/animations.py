from __future__ import annotations

from PySide6.QtCore import (QEasingCurve, QParallelAnimationGroup,
                            QPropertyAnimation, QVariantAnimation)
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget


def _ensure_opacity_effect(widget: QWidget) -> QGraphicsOpacityEffect:
    effect = widget.graphicsEffect()
    if isinstance(effect, QGraphicsOpacityEffect):
        return effect
    opacity = QGraphicsOpacityEffect(widget)
    opacity.setOpacity(1.0)
    widget.setGraphicsEffect(opacity)
    return opacity


def build_expand_animation(widget: QWidget, *, expand: bool, duration_ms: int = 180) -> QParallelAnimationGroup:
    start_height = widget.sizeHint().height() if expand else widget.maximumHeight() or widget.sizeHint().height()
    end_height = widget.sizeHint().height() if expand else 0
    widget.setMaximumHeight(max(0, start_height))

    height_anim = QPropertyAnimation(widget, b"maximumHeight")
    height_anim.setDuration(duration_ms)
    height_anim.setStartValue(start_height)
    height_anim.setEndValue(end_height)
    height_anim.setEasingCurve(QEasingCurve.OutCubic)

    opacity = _ensure_opacity_effect(widget)
    fade_anim = QPropertyAnimation(opacity, b"opacity")
    fade_anim.setDuration(duration_ms)
    fade_anim.setStartValue(0.0 if expand else 1.0)
    fade_anim.setEndValue(1.0 if expand else 0.0)
    fade_anim.setEasingCurve(QEasingCurve.InOutCubic)

    group = QParallelAnimationGroup(widget)
    group.addAnimation(height_anim)
    group.addAnimation(fade_anim)
    return group


def fade_in(widget: QWidget, *, duration_ms: int = 160) -> QPropertyAnimation:
    opacity = _ensure_opacity_effect(widget)
    animation = QPropertyAnimation(opacity, b"opacity")
    animation.setDuration(duration_ms)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.OutCubic)
    return animation


def flash_success(widget: QWidget, *, duration_ms: int = 240) -> QVariantAnimation:
    animation = QVariantAnimation(widget)
    animation.setDuration(duration_ms)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    return animation


def pulse_badge(widget: QWidget, *, duration_ms: int = 620) -> QPropertyAnimation:
    opacity = _ensure_opacity_effect(widget)
    animation = QPropertyAnimation(opacity, b"opacity")
    animation.setDuration(duration_ms)
    animation.setStartValue(1.0)
    animation.setEndValue(0.55)
    animation.setEasingCurve(QEasingCurve.InOutCubic)
    animation.setLoopCount(-1)
    return animation
