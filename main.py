import sys
import os
import signal
from PySide6.QtCore import QProcess
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout,
    QLabel, QPushButton
)
from PySide6.QtGui import QIcon




app = QApplication(sys.argv)

window = QWidget()
window.setWindowTitle("PLauncher")
window.resize(400, 250)

layout = QVBoxLayout(window)

title = QLabel("PLauncher")
title.setStyleSheet("font-size: 20px; font-weight: bold;")

status = QLabel("")


process = None

def launch_system_skakavi_krompir():
    global process
    print("Launching System Skakavi Krompir...")
    status.setText("Launching...")
    
    if process is None:
        process = QProcess()
        process.started.connect(lambda: status.setText("Running"))
        process.finished.connect(handle_finished)
        process.errorOccurred.connect(handle_error)

    if process.state() == QProcess.ProcessState.NotRunning:
        # Use setsid to start the game in its own process group
        process.start("setsid", ["/usr/local/bin/skakavi-krompir-alpha"])
    else:
        status.setText("Already running")

def handle_finished(exit_code, exit_status):
    if exit_status == QProcess.ExitStatus.CrashExit:
        status.setText("Crashed")
    else:
        status.setText(f"Finished (Exit Code: {exit_code})")

def handle_error(error):
    if error == QProcess.ProcessError.FailedToStart:
        status.setText("Error: Binary not found or failed to start")
    else:
        status.setText(f"Process Error: {error}")

def kill_system_skakavi_krompir():
    global process
    if process is not None and process.state() == QProcess.ProcessState.Running:
        pid = process.processId()
        try:
            # Kill the process group to ensure children like the game window are also killed
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            # Fallback if PGID cannot be reached or identified
            process.kill()
            
        process.waitForFinished(1000)
        process = None
        status.setText("Killed")
    else:
        status.setText("Not running")

launch_btn = QPushButton("Launch System Skakavi Krompir")
launch_btn.clicked.connect(launch_system_skakavi_krompir)

kill_btn = QPushButton("Kill System Skakavi Krompir")
kill_btn.clicked.connect(kill_system_skakavi_krompir)

layout.addWidget(title)
layout.addWidget(status)
layout.addStretch()
layout.addWidget(launch_btn)
layout.addWidget(kill_btn)

window.show()
sys.exit(app.exec())
