from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton


class SignUpDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create Account")
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Email"))
        self.email = QLineEdit()
        layout.addWidget(self.email)

        layout.addWidget(QLabel("Password"))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password)

        buttons = QHBoxLayout()
        self.signup_btn = QPushButton("Sign Up")
        self.cancel_btn = QPushButton("Cancel")
        buttons.addWidget(self.signup_btn)
        buttons.addWidget(self.cancel_btn)
        layout.addLayout(buttons)

        self.signup_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

    def get_values(self) -> tuple[str, str]:
        return self.email.text().strip(), self.password.text()


