"""
GitPilot: Main application entry point.

This script initializes and runs the PyQt5 application and the main window.
"""
import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont
from ui_main import MainWindow

def main():
    """
    Initializes the QApplication and shows the MainWindow.
    """
    app = QApplication(sys.argv)
    app.setFont(QFont("Arial", 13))
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
