#!/usr/bin/env python3
"""Deterministic Qt fixture with an independent JSON effect oracle."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


STATE_PATH = Path.home() / ".cache/linuxvm-testbed/qt-fixture/state.json"


class Canvas(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setAccessibleName("Qt Visual Canvas")
        self.setMinimumHeight(260)

    def paintEvent(self, _event: Any) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#141f33"))
        painter.setPen(QPen(QColor("#33b2f2"), 4))
        painter.drawRect(24, 24, self.width() - 48, self.height() - 48)
        painter.setPen(QColor("#edf2ff"))
        painter.drawText(
            self.rect(),
            Qt.AlignCenter,
            "Qt custom-rendered visual fallback",
        )


class Fixture(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.state = {
            "pid": os.getpid(),
            "sequence": 0,
            "semanticPresses": 0,
            "text": "",
            "lastEvent": "",
        }
        self.setWindowTitle("Machine Control Qt Fixture")
        self.resize(720, 520)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Machine Control Deterministic Qt Fixture"))
        self.entry = QLineEdit()
        self.entry.setAccessibleName("Qt Fixture Text")
        self.entry.setPlaceholderText("Type Qt fixture text")
        self.entry.textChanged.connect(self.on_text)
        layout.addWidget(self.entry)
        button = QPushButton("Qt Semantic Increment")
        button.clicked.connect(self.on_press)
        layout.addWidget(button)
        layout.addWidget(Canvas())
        self.status = QLabel("ready")
        self.status.setAccessibleName("Qt Fixture Status")
        layout.addWidget(self.status)
        self.save("ready")

    def save(self, event: str) -> None:
        self.state["sequence"] += 1
        self.state["lastEvent"] = event
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = STATE_PATH.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self.state, separators=(",", ":"), ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(STATE_PATH)
        if hasattr(self, "status"):
            self.status.setText(f"{event} · sequence {self.state['sequence']}")

    def on_press(self) -> None:
        self.state["semanticPresses"] += 1
        self.save("semantic_press")

    def on_text(self, value: str) -> None:
        self.state["text"] = value
        self.save("text_changed")


def main() -> int:
    application = QApplication([])
    application.setApplicationName("machine-control-qt-fixture")
    fixture = Fixture()
    fixture.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
