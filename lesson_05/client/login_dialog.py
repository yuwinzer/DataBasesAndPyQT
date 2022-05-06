import sys

from PyQt5.QtWidgets import QApplication, qApp, QDialog
sys.path.append('../')

from client.login_dialog_ui import Ui_UserLoginDialog


class LoginWindow(QDialog):
    def __init__(self):
        super().__init__()

        self.enter = False

        self.login_window = Ui_UserLoginDialog()
        self.login_window.setupUi(self)

        self.login_window.EnterPB.clicked.connect(self.run)
        self.login_window.ExitPB.clicked.connect(qApp.exit)

        self.show()

    def run(self):
        if self.login_window.LoginLE.text():
            self.enter = True
            qApp.exit()


if __name__ == '__main__':
    app = QApplication([])
    dial = LoginWindow()
    app.exec_()
