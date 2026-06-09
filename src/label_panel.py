"""类别管理面板"""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class LabelPanel(QWidget):
    """左侧类别列表面板"""

    label_selected = pyqtSignal(str)  # 选中类别名

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(200)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("🏷️ 类别列表")
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 4px;")
        layout.addWidget(title)

        # 类别列表
        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_item_changed)
        layout.addWidget(self.list_widget)

        # 添加 / 删除按钮
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("+ 添加")
        self.btn_add.clicked.connect(self._add_label)
        self.btn_del = QPushButton("- 删除")
        self.btn_del.clicked.connect(self._del_label)
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_del)
        layout.addLayout(btn_layout)

        # 快速输入框
        self.input = QLineEdit()
        self.input.setPlaceholderText("输入类别名，回车添加")
        self.input.returnPressed.connect(self._add_from_input)
        layout.addWidget(self.input)

    def _on_item_changed(self, current, _previous):
        if current:
            self.label_selected.emit(current.text())

    def _add_label(self):
        name, ok = QInputDialog.getText(self, "添加类别", "类别名称：")
        if ok and name.strip():
            self.add_label(name.strip())

    def _del_label(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.list_widget.takeItem(row)

    def _add_from_input(self):
        name = self.input.text().strip()
        if name:
            self.add_label(name)
            self.input.clear()

    def add_label(self, name: str) -> None:
        # 去重
        for i in range(self.list_widget.count()):
            if self.list_widget.item(i).text() == name:
                self.list_widget.setCurrentRow(i)
                return
        self.list_widget.addItem(name)
        self.list_widget.setCurrentRow(self.list_widget.count() - 1)

    def current_label(self) -> str:
        item = self.list_widget.currentItem()
        return item.text() if item else ""

    def get_all_labels(self) -> list[str]:
        return [
            self.list_widget.item(i).text() for i in range(self.list_widget.count())
        ]
