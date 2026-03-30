from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QListWidget, QVBoxLayout, QWidget

from src.ui.widgets.custom_combo import CustomComboBox


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_set_current_index_emits_signals() -> None:
    _app()
    combo = CustomComboBox()
    combo.addItems(["A", "B", "C"])

    changed_indexes: list[int] = []
    changed_texts: list[str] = []
    combo.currentIndexChanged.connect(changed_indexes.append)
    combo.currentTextChanged.connect(changed_texts.append)

    combo.setCurrentIndex(1)
    combo.setCurrentIndex(1)

    assert changed_indexes == [1]
    assert changed_texts == ["B"]


def test_combo_popup_is_backed_by_qlistwidget() -> None:
    _app()
    combo = CustomComboBox()

    popup_list = combo.findChild(QListWidget)
    assert popup_list is not None


def test_popup_stays_open_after_first_click_and_allows_selection() -> None:
    app = _app()
    host = QWidget()
    layout = QVBoxLayout(host)
    combo = CustomComboBox(host)
    combo.addItems(["A", "B", "C"])
    layout.addWidget(combo)
    host.show()
    app.processEvents()

    QTest.mouseClick(combo._button, Qt.MouseButton.LeftButton)  # noqa: SLF001
    app.processEvents()
    assert combo._popup.isVisible() is True  # noqa: SLF001

    second_item = combo._popup.list_widget.item(1)  # noqa: SLF001
    rect = combo._popup.list_widget.visualItemRect(second_item)  # noqa: SLF001
    QTest.mouseClick(
        combo._popup.list_widget.viewport(),  # noqa: SLF001
        Qt.MouseButton.LeftButton,
        pos=rect.center(),
    )
    app.processEvents()

    assert combo.currentIndex() == 1
    assert combo.currentText() == "B"
    assert combo._popup.isVisible() is False  # noqa: SLF001
    host.close()


def test_popup_hides_when_host_widget_hides() -> None:
    app = _app()
    host = QWidget()
    layout = QVBoxLayout(host)
    combo = CustomComboBox(host)
    combo.addItems(["A", "B"])
    layout.addWidget(combo)
    host.show()
    app.processEvents()

    combo._show_popup()  # noqa: SLF001
    app.processEvents()
    assert combo._popup.isVisible() is True  # noqa: SLF001

    host.hide()
    app.processEvents()
    assert combo._popup.isVisible() is False  # noqa: SLF001


def test_opening_another_combo_hides_previous_popup() -> None:
    app = _app()
    host = QWidget()
    layout = QVBoxLayout(host)
    combo1 = CustomComboBox(host)
    combo2 = CustomComboBox(host)
    combo1.addItems(["A", "B"])
    combo2.addItems(["X", "Y"])
    layout.addWidget(combo1)
    layout.addWidget(combo2)
    host.show()
    app.processEvents()

    combo1._show_popup()  # noqa: SLF001
    app.processEvents()
    assert combo1.isPopupVisible() is True

    combo2._show_popup()  # noqa: SLF001
    app.processEvents()
    assert combo1.isPopupVisible() is False
    assert combo2.isPopupVisible() is True
    host.close()


def test_popup_is_horizontally_aligned_and_below_button_when_space_allows() -> None:
    app = _app()
    host = QWidget()
    host.setGeometry(100, 100, 360, 260)
    layout = QVBoxLayout(host)
    combo = CustomComboBox(host)
    combo.setFixedWidth(120)
    combo.addItems([f"Item {i}" for i in range(8)])
    layout.addWidget(combo)
    host.show()
    app.processEvents()

    combo._show_popup()  # noqa: SLF001
    app.processEvents()

    popup_rect = combo.popupGeometryGlobal()
    button_rect = combo._button.rect()  # noqa: SLF001
    button_top_left = combo._button.mapToGlobal(button_rect.topLeft())  # noqa: SLF001
    button_bottom = combo._button.mapToGlobal(button_rect.bottomLeft()).y()  # noqa: SLF001

    assert popup_rect.left() == button_top_left.x()
    assert popup_rect.top() >= button_bottom
    host.close()
