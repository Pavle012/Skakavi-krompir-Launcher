import sys
import os
import shutil
import signal
import json
import requests
import time
from PySide6.QtWidgets import QStyleFactory
from PySide6.QtCore import QProcess, Qt, QSize, QThread, Signal, QIODevice, QTimer
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout,
    QLabel, QPushButton, QHBoxLayout,
    QFileDialog, QMessageBox, QListWidget, QListWidgetItem,
    QApplication, QWidget, QVBoxLayout,
    QLabel, QPushButton, QHBoxLayout,
    QFileDialog, QMessageBox, QListWidget, QListWidgetItem,
    QApplication, QWidget, QVBoxLayout,
    QLabel, QPushButton, QHBoxLayout,
    QFileDialog, QMessageBox, QListWidget, QListWidgetItem,
    QAbstractItemView, QProgressDialog, QComboBox, QDialog,
    QPlainTextEdit, QTabWidget, QCheckBox, QTextBrowser, QLineEdit, QSpinBox,
    QDoubleSpinBox, QFormLayout
)
from PySide6.QtGui import QIcon, QPixmap, QPalette, QColor, QDesktopServices
from PySide6.QtCore import QUrl

INSTANCES_FILE = "instances.json"
RELEASES_URL = "https://api.github.com/repos/Pavle012/Skakavi-krompir/releases"
REPO_API_URL = "http://localhost:8000"

class GameDownloader(QThread):
    progress = Signal(int)
    finished = Signal(str, str)  # (name, file_path)
    error = Signal(str)

    def __init__(self, download_url, asset_name, version_tag):
        super().__init__()
        self.download_url = download_url
        self.asset_name = asset_name
        self.version_tag = version_tag

    def run(self):
        try:
            base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
            os.makedirs(base_dir, exist_ok=True)
            file_path = os.path.join(base_dir, self.asset_name)
            
            with requests.get(self.download_url, stream=True) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0))
                downloaded = 0
                
                with open(file_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                self.progress.emit(int(downloaded * 100 / total_size))
            
            if sys.platform != "win32":
                os.chmod(file_path, 0o755)
                
            self.finished.emit(f"Skakavi Krompir {self.version_tag}", file_path)
            
        except Exception as e:
            self.error.emit(str(e))

class VersionPicker(QWidget):
    def __init__(self, releases, parent=None):
        super().__init__(parent)
        self.releases = releases
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Select Version:"))
        self.version_combo = QComboBox()
        for release in self.releases:
            self.version_combo.addItem(release["tag_name"], release)
        self.version_combo.currentIndexChanged.connect(self.update_assets)
        layout.addWidget(self.version_combo)
        
        layout.addWidget(QLabel("Select File:"))
        self.asset_combo = QComboBox()
        layout.addWidget(self.asset_combo)
        
        self.update_assets()
        self.auto_select_asset()

    def update_assets(self):
        self.asset_combo.clear()
        release = self.version_combo.currentData()
        if release:
            for asset in release.get("assets", []):
                self.asset_combo.addItem(asset["name"], asset)

    def auto_select_asset(self):
        if sys.platform == "win32":
            target = "Skakavi-krompir-Windows.exe"
        else:
            target = "Skakavi-Krompir-Linux"
            
        for i in range(self.asset_combo.count()):
            if self.asset_combo.itemText(i) == target:
                self.asset_combo.setCurrentIndex(i)
                break

    def get_selected(self):
        return self.version_combo.currentText(), self.asset_combo.currentData()

class LogViewer(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Game Logs")
        self.resize(600, 400)
        layout = QVBoxLayout(self)
        
        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("font-family: monospace; background-color: #1e1e1e; color: #d4d4d4;")
        layout.addWidget(self.text_edit)
        
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.text_edit.clear)
        layout.addWidget(clear_btn)

    def append_log(self, text):
        self.text_edit.appendPlainText(text)

def load_ui(name, parent=None):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    ui_file_path = os.path.join(base_path, name)
    ui_file = QFile(ui_file_path)
    if not ui_file.open(QIODevice.OpenModeFlag.ReadOnly):
        print(f"Cannot open {ui_file_path}: {ui_file.errorString()}")
        return None
        
    loader = QUiLoader()
    widget = loader.load(ui_file, parent)
    ui_file.close()
    return widget

class RepoBrowserDialog(QDialog):
    def __init__(self, target_dir, parent=None):
        super().__init__(parent)
        self.target_dir = target_dir
        self.projects = []
        self.current_project = None
        self.versions = []
        
        # Load UI
        self.ui = load_ui("repo_browser.ui", self)
        
        # Setup layout to contain the loaded UI
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.ui)
        
        self.init_ui()
        self.fetch_projects()

    def init_ui(self):
        # Find widgets
        self.project_list = self.ui.findChild(QListWidget, "projectList")
        self.details_browser = self.ui.findChild(QTextBrowser, "detailsBrowser")
        self.version_combo = self.ui.findChild(QComboBox, "versionCombo")
        install_btn = self.ui.findChild(QPushButton, "installBtn")
        close_btn = self.ui.findChild(QPushButton, "closeBtn")
        
        # Connect signals
        self.project_list.currentItemChanged.connect(self.on_project_selected)
        install_btn.clicked.connect(self.install_version)
        close_btn.clicked.connect(self.reject)

    def fetch_projects(self):
        try:
            response = requests.get(f"{REPO_API_URL}/projects")
            response.raise_for_status()
            self.projects = response.json()
            self.project_list.clear()
            for project in self.projects:
                item = QListWidgetItem(project["name"])
                item.setData(Qt.ItemDataRole.UserRole, project)
                self.project_list.addItem(item)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to fetch projects: {e}")

    def on_project_selected(self, current, previous):
        if not current:
            return
        
        project = current.data(Qt.ItemDataRole.UserRole)
        self.current_project = project
        self.update_details(project)
        self.fetch_versions(project["id"])

    def update_details(self, project):
        html = f"""
        <h2>{project['name']}</h2>
        <p><b>Author:</b> {project['author']}</p>
        <p><b>Description:</b></p>
        <p>{project['description']}</p>
        """
        self.details_browser.setHtml(html)

    def fetch_versions(self, project_id):
        self.version_combo.clear()
        try:
            response = requests.get(f"{REPO_API_URL}/projects/{project_id}/versions")
            response.raise_for_status()
            self.versions = response.json()
            # Sort versions maybe? For now just add them
            for version in self.versions:
                self.version_combo.addItem(f"{version['version_number']} ({version['filename']})", version)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to fetch versions: {e}")

    def install_version(self):
        version_idx = self.version_combo.currentIndex()
        if version_idx < 0:
            QMessageBox.warning(self, "Warning", "Please select a version to install.")
            return
            
        version = self.version_combo.itemData(version_idx)
        version_id = version['id']
        filename = version['filename']
        
        # Download
        url = f"{REPO_API_URL}/download/{version_id}" # API doesn't have download endpoint exposed plainly like this in main.py, let me check
        # Checking main.py: @app.get("/download/{version_id}") -> yes it does.
        
        target_path = os.path.join(self.target_dir, filename)
        
        progress = QProgressDialog(f"Downloading {filename}...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        QApplication.processEvents()
        
        try:
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(target_path, 'wb') as f:
                     for chunk in r.iter_content(chunk_size=8192): 
                        f.write(chunk)
            progress.close()
            QMessageBox.information(self, "Success", f"Installed {filename} successfully!")
            self.accept() # Close dialog to refresh parent list
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Error", f"Failed to download mod: {e}")

class EditInstanceDialog(QDialog):
    def __init__(self, instance_manager, instance_index, parent=None):
        super().__init__(parent)
        self.instance_manager = instance_manager
        self.instance_index = instance_index
        self.instance_data = self.instance_manager.instances[instance_index]
        self.instance_path = self.instance_data["path"]
        self.instance_dir = os.path.dirname(self.instance_path) if self.instance_path else None
        
        # Determine global mod directory
        if sys.platform == "win32":
            self.global_mod_dir = os.path.join(os.environ["APPDATA"], "SkakaviKrompir", "mods")
        else:
            self.global_mod_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "SkakaviKrompir", "mods")

        # Load UI
        self.ui = load_ui("edit_instance.ui", self)
        self.setWindowTitle("Instance Editor")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.ui)
        
        self.init_ui()

    def init_ui(self):
        self.tabs = self.ui.findChild(QTabWidget, "tabWidget")
        close_btn = self.ui.findChild(QPushButton, "closeBtn")
        close_btn.clicked.connect(self.accept)

        # General Tab
        self.create_general_tab()
        
        # Settings Tab
        if self.instance_dir:
            self.create_settings_tab()

        # Instance Mods Tab
        if self.instance_dir:
            instance_mods_path = os.path.join(self.instance_dir, "mods")
            self.create_mod_tab(instance_mods_path, "Instance Mods")

        # Global Mods Tab
        self.create_mod_tab(self.global_mod_dir, "Global Mods")

    def create_general_tab(self):
        tab_widget = load_ui("general_tab.ui")
        
        self.name_edit = tab_widget.findChild(QLineEdit, "nameEdit")
        self.icon_preview = tab_widget.findChild(QLabel, "iconPreview")
        change_icon_btn = tab_widget.findChild(QPushButton, "changeIconBtn")
        save_btn = tab_widget.findChild(QPushButton, "saveBtn")
        
        # Load current data
        self.name_edit.setText(self.instance_data["name"])
        self.current_icon_path = self.instance_data.get("icon_path", "")
        self.update_icon_preview()
        
        # Connect signals
        change_icon_btn.clicked.connect(self.change_icon)
        save_btn.clicked.connect(self.save_general_settings)
        
        self.tabs.insertTab(0, tab_widget, "General")
        self.tabs.setCurrentIndex(0)

    def update_icon_preview(self):
        if self.current_icon_path and os.path.exists(self.current_icon_path):
            pixmap = QPixmap(self.current_icon_path)
        else:
            pixmap = QIcon("icon.png").pixmap(64, 64)
            if pixmap.isNull():
                 pixmap = QIcon.fromTheme("applications-games").pixmap(64, 64)
        
        self.icon_preview.setPixmap(pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def change_icon(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Icon", "", "Images (*.png *.jpg *.ico)")
        if file_path:
            self.current_icon_path = file_path
            self.update_icon_preview()

    def save_general_settings(self):
        new_name = self.name_edit.text()
        if not new_name:
            QMessageBox.warning(self, "Warning", "Instance name cannot be empty.")
            return

        self.instance_data["name"] = new_name
        self.instance_data["icon_path"] = self.current_icon_path
        
        self.instance_manager.update_instance(self.instance_index, self.instance_data)
        QMessageBox.information(self, "Success", "Instance settings saved!")

    def create_settings_tab(self):
        tab_widget = load_ui("settings_tab.ui")
        
        self.jump_spin = tab_widget.findChild(QSpinBox, "jumpVelocitySpin")
        self.scroll_spin = tab_widget.findChild(QSpinBox, "scrollSpeedSpin")
        self.fps_spin = tab_widget.findChild(QSpinBox, "maxFpsSpin")
        self.speed_inc_spin = tab_widget.findChild(QDoubleSpinBox, "speedIncreaseSpin")
        self.player_name_edit = tab_widget.findChild(QLineEdit, "playerNameEdit")
        self.remember_check = tab_widget.findChild(QCheckBox, "rememberNameCheck")
        save_btn = tab_widget.findChild(QPushButton, "saveSettingsBtn")
        
        self.load_game_settings()
        
        save_btn.clicked.connect(self.save_game_settings)
        
        self.tabs.insertTab(1, tab_widget, "Game Settings")

    def get_settings_path(self):
        if not self.instance_dir:
            return None
        return os.path.join(self.instance_dir, "data", "settings.txt")

    def load_game_settings(self):
        settings_path = self.get_settings_path()
        if not settings_path or not os.path.exists(settings_path):
             return
             
        # Initialize defaults
        settings = {
            "jumpVelocity": 12,
            "scrollPixelsPerFrame": 8,
            "maxFps": 60,
            "speed_increase": 0.03,
            "name": "",
            "rememberName": "False"
        }
        
        try:
            with open(settings_path, "r") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        settings[k] = v
        except Exception:
            pass
            
        try:
            self.jump_spin.setValue(int(settings["jumpVelocity"]))
            self.scroll_spin.setValue(int(settings["scrollPixelsPerFrame"]))
            self.fps_spin.setValue(int(settings["maxFps"]))
            self.speed_inc_spin.setValue(float(settings["speed_increase"]))
            self.player_name_edit.setText(settings["name"])
            self.remember_check.setChecked(settings["rememberName"] == "True")
        except ValueError:
            pass

    def save_game_settings(self):
        settings_path = self.get_settings_path()
        if not settings_path:
            return
            
        data_dir = os.path.dirname(settings_path)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            
        try:
            with open(settings_path, "w") as f:
                f.write(f"jumpVelocity={self.jump_spin.value()}\n")
                f.write(f"scrollPixelsPerFrame={self.scroll_spin.value()}\n")
                f.write(f"maxFps={self.fps_spin.value()}\n")
                f.write(f"speed_increase={self.speed_inc_spin.value()}\n")
                f.write(f"name={self.player_name_edit.text()}\n")
                f.write(f"rememberName={self.remember_check.isChecked()}\n")
                
            QMessageBox.information(self, "Success", "Game settings saved!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")

    def create_mod_tab(self, directory, title):
        tab_widget = load_ui("mod_tab.ui")
        
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
            except OSError:
                pass

        list_widget = tab_widget.findChild(QListWidget, "modList")
        add_btn = tab_widget.findChild(QPushButton, "addBtn")
        remove_btn = tab_widget.findChild(QPushButton, "removeBtn")
        open_dir_btn = tab_widget.findChild(QPushButton, "openDirBtn")
        repo_btn = tab_widget.findChild(QPushButton, "repoBtn")
        refresh_btn = tab_widget.findChild(QPushButton, "refreshBtn")
        
        add_btn.clicked.connect(lambda: self.add_mod(directory, list_widget))
        remove_btn.clicked.connect(lambda: self.remove_mod(directory, list_widget))
        open_dir_btn.clicked.connect(lambda: self.open_directory(directory))
        repo_btn.clicked.connect(lambda: self.browse_repo(directory, list_widget))
        refresh_btn.clicked.connect(lambda: self.load_mods(directory, list_widget))
        
        self.tabs.addTab(tab_widget, title)
        
        # Load mods initially
        self.load_mods(directory, list_widget)
        
        # Connect item changed signal for toggling
        list_widget.itemChanged.connect(lambda item: self.toggle_mod(item, directory))

    def open_directory(self, path):
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def load_mods(self, directory, list_widget):
        list_widget.blockSignals(True) # Prevent toggling while loading
        list_widget.clear()
        
        if not os.path.exists(directory):
            list_widget.blockSignals(False)
            return

        for f in sorted(os.listdir(directory)):
            full_path = os.path.join(directory, f)
            if os.path.isfile(full_path):
                name = f
                enabled = True
                
                if f.endswith(".disabled"):
                    name = f[:-9] # Remove .disabled
                    enabled = False
                
                if name.endswith(".py") or name.endswith(".skmod"):
                    item = QListWidgetItem(name)
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked)
                    item.setData(Qt.ItemDataRole.UserRole, f) # Store original filename
                    list_widget.addItem(item)
                    
        list_widget.blockSignals(False)

    def toggle_mod(self, item, directory):
        name = item.text()
        original_filename = item.data(Qt.ItemDataRole.UserRole)
        current_path = os.path.join(directory, original_filename)
        
        is_checked = item.checkState() == Qt.CheckState.Checked
        
        new_filename = name if is_checked else name + ".disabled"
        new_path = os.path.join(directory, new_filename)
        
        try:
            os.rename(current_path, new_path)
            # Update the stored filename
            item.setData(Qt.ItemDataRole.UserRole, new_filename)
        except OSError as e:
            QMessageBox.critical(self, "Error", f"Failed to toggle mod: {e}")
            # Revert checkbox state without triggering signal
            self.load_mods(directory, item.listWidget())

    def add_mod(self, directory, list_widget):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Mod File", "", "Mod Files (*.py *.skmod)")
        if file_path:
            try:
                shutil.copy(file_path, directory)
                self.load_mods(directory, list_widget)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add mod: {e}")

    def browse_repo(self, directory, list_widget):
        dialog = RepoBrowserDialog(directory, self)
        if dialog.exec() == QDialog.Accepted:
            self.load_mods(directory, list_widget)

    def remove_mod(self, directory, list_widget):
        current_item = list_widget.currentItem()
        if not current_item:
            return
            
        filename = current_item.data(Qt.ItemDataRole.UserRole)
        path = os.path.join(directory, filename)
        
        reply = QMessageBox.question(self, "Confirm", f"Are you sure you want to delete '{filename}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                                     
        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.remove(path)
                self.load_mods(directory, list_widget)
            except OSError as e:
                QMessageBox.critical(self, "Error", f"Failed to remove mod: {e}")

class InstanceManager:
    def __init__(self):
        self.instances = self.load_instances()

    def load_instances(self):
        if os.path.exists(INSTANCES_FILE):
            try:
                with open(INSTANCES_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading instances: {e}")
        return []

    def save_instances(self):
        try:
            with open(INSTANCES_FILE, "w") as f:
                json.dump(self.instances, f, indent=4)
        except Exception as e:
            print(f"Error saving instances: {e}")

    def add_instance(self, name, path):
        self.instances.append({"name": name, "path": path})
        self.save_instances()

    def update_instance(self, index, new_data):
        if 0 <= index < len(self.instances):
            self.instances[index] = new_data
            self.save_instances()

    def remove_instance(self, index):
        if 0 <= index < len(self.instances):
            del self.instances[index]
            self.save_instances()

instance_manager = InstanceManager()
instance_manager = InstanceManager()
process = None
downloader = None
log_viewer = None
status_timer = None
current_monitoring_path = None

def check_game_status():
    if not current_monitoring_path:
        return
        
    status_file = os.path.join(current_monitoring_path, "status.json")
    if os.path.exists(status_file):
        try:
            with open(status_file, "r") as f:
                data = json.load(f)
                
            state = data.get("state", "unknown")
            score = data.get("score", 0)
            
            # Check if timestamp is too old (game crashed/closed without updating)
            timestamp = data.get("timestamp", 0)
            if time.time() - timestamp > 5: # 5 seconds timeout
                 status.setText("Status: Not Running (Timeout)")
                 return
                 
            if state == "playing":
                status.setText(f"Playing - Score: {score}")
            elif state == "paused":
                status.setText(f"Paused - Score: {score}")
            elif state == "game_over":
                status.setText(f"Game Over - Final Score: {score}")
            elif state == "stopped":
                status.setText("Finished")
            else:
                status.setText(f"Status: {state}")
                
        except Exception:
            pass # File read error or json error, ignore

def handle_finished(exit_code, exit_status):
    global status_timer
    if status_timer:
        status_timer.stop()
        
    if exit_status == QProcess.ExitStatus.CrashExit:
        status.setText("Crashed")
    else:
        if exit_code == 0:
            status.setText("Finished")
        else:
            status.setText(f"Finished (Exit Code: {exit_code})")

def handle_error(error):
    if error == QProcess.ProcessError.FailedToStart:
        status.setText("Error: Binary not found or failed to start")
    else:
        status.setText(f"Process Error: {error}")

def read_stdout():
    if process and log_viewer:
        data = process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        log_viewer.append_log(data)

def read_stderr():
    if process and log_viewer:
        data = process.readAllStandardError().data().decode("utf-8", errors="replace")
        log_viewer.append_log(data)

def update_selected_instance_details(current=None, previous=None):
    current_item = instance_list.currentItem()
    if current_item:
        instance_index = instance_list.row(current_item)
        if instance_index < len(instance_manager.instances):
            instance = instance_manager.instances[instance_index]
            instance_name_label.setText(instance["name"])
            
            # Set icon
            icon_path = instance.get("icon_path")
            if icon_path and os.path.exists(icon_path):
                 pixmap = QIcon(icon_path).pixmap(128, 128)
            else:
                 pixmap = QIcon("icon.png").pixmap(128, 128)
                 
            if pixmap.isNull():
                 pixmap = QIcon.fromTheme("applications-games").pixmap(128, 128)
            instance_icon_label.setPixmap(pixmap)
            return

    instance_name_label.setText("No selected instance")
    instance_icon_label.clear()

def launch_instance():
    global process
    current_item = instance_list.currentItem()
    if not current_item:
        status.setText("No instance selected")
        return

    instance_index = instance_list.row(current_item)
    instance = instance_manager.instances[instance_index]
    instance_path = instance["path"]
    
    working_dir = os.path.dirname(instance_path)
    
    print(f"Launching Skakavi Krompir for instance: {instance['name']} at {instance_path}")
    status.setText(f"Launching {instance['name']}...")
    
    if log_viewer:
        log_viewer.append_log(f"--- Launching {instance['name']} ---\n")

    if process is None:
        process = QProcess()
        process.started.connect(lambda: status.setText(f"Running: {instance['name']}"))
        process.finished.connect(handle_finished)
        process.errorOccurred.connect(handle_error)
        process.readyReadStandardOutput.connect(read_stdout)
        process.readyReadStandardError.connect(read_stderr)

    if process.state() == QProcess.ProcessState.NotRunning:
        process.setWorkingDirectory(working_dir)
        if not os.path.exists(working_dir):
            os.makedirs(working_dir, exist_ok=True)
            
        # Data directory for this instance
        data_dir = os.path.join(working_dir, "data")
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            
        global current_monitoring_path, status_timer
        current_monitoring_path = data_dir
        
        # Start monitoring
        status_timer = QTimer()
        status_timer.timeout.connect(check_game_status)
        status_timer.start(1000) # Check every second
            
        # Launch with arguments. 
        # Note: We need to pass the arguments to the python script or executable.
        # Assuming instance_path is the executable or script
        
        args = [instance_path, "--data-dir", data_dir]
        
        # If it's a python script, we might need to run it with python
        if instance_path.endswith(".py"):
             program = sys.executable
             args = [instance_path, "--data-dir", data_dir]
             process.start(program, args)
        else:
             # For compiled entry, we pass args directly
             process.start(instance_path, ["--data-dir", data_dir])

    else:
        status.setText("Already running")

def kill_instance():
    global process
    if process is not None and process.state() == QProcess.ProcessState.Running:
        pid = process.processId()
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            process.kill()
            
        process.waitForFinished(1000)
        process = None
        status.setText("Killed")
    else:
        status.setText("Not running")

def add_new_instance():
    file_path, _ = QFileDialog.getOpenFileName(window, "Select Instance Executable or Configuration")
    if file_path:
        name = os.path.basename(file_path)
        instance_manager.add_instance(name, file_path)
        refresh_instances()

def remove_selected_instance():
    current_item = instance_list.currentItem()
    if not current_item:
        QMessageBox.warning(window, "Remove Instance", "No instance selected.")
        return

    instance_index = instance_list.row(current_item)
    instance_name = current_item.text()
    
    reply = QMessageBox.question(window, "Confirm Removal", 
                                 f"Are you sure you want to remove '{instance_name}'?\nThis will not delete the files, only the launcher entry.",
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
    
    if reply == QMessageBox.StandardButton.Yes:
        instance_manager.remove_instance(instance_index)
        refresh_instances()

def show_logs():
    global log_viewer
    if not log_viewer:
        log_viewer = LogViewer(window)
    log_viewer.show()
    log_viewer.raise_()

def download_instance_dialog():
    progress = QProgressDialog("Fetching releases from GitHub...", "Cancel", 0, 0, window)
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.show()
    QApplication.processEvents()
    
    try:
        response = requests.get(RELEASES_URL)
        response.raise_for_status()
        releases = response.json()
        progress.close()
    except Exception as e:
        progress.close()
        QMessageBox.critical(window, "Error", f"Failed to fetch releases: {e}")
        return

    dialog = QMessageBox(window)
    dialog.setWindowTitle("Download Instance")
    dialog.setText("Select the version and file you want to download.")
    
    picker = VersionPicker(releases)
    dialog.layout().addWidget(picker)
    dialog.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
    
    if dialog.exec() == QMessageBox.StandardButton.Ok:
        version, asset = picker.get_selected()
        if asset:
            start_download(asset["browser_download_url"], asset["name"], version)

def start_download(url, filename, version):
    global downloader
    downloader = GameDownloader(url, filename, version)
    
    progress_dialog = QProgressDialog(f"Downloading {filename}...", "Cancel", 0, 100, window)
    progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
    
    downloader.progress.connect(progress_dialog.setValue)
    downloader.finished.connect(lambda name, path: handle_download_finished(name, path, progress_dialog))
    downloader.error.connect(lambda err: handle_download_error(err, progress_dialog))
    
    downloader.start()
    progress_dialog.exec()

def handle_download_finished(name, path, dialog):
    dialog.close()
    instance_manager.add_instance(name, path)
    refresh_instances()
    QMessageBox.information(window, "Success", f"Downloaded and added instance: {name}")

def handle_download_error(err, dialog):
    dialog.close()
    QMessageBox.critical(window, "Download Error", f"Failed to download: {err}")

def open_instance_editor():
    current_item = instance_list.currentItem()
    if not current_item:
        QMessageBox.warning(window, "Edit", "Please select an instance first.")
        return

    instance_index = instance_list.row(current_item)
    
    dialog = EditInstanceDialog(instance_manager, instance_index, window)
    if dialog.exec():
         # Refresh list and details if changed
         refresh_instances()
         update_selected_instance_details()

def refresh_instances():
    instance_list.clear()
    icon = QIcon.fromTheme("applications-games", QIcon("icon.png")) 
    
    for inst in instance_manager.instances:
        icon_path = inst.get("icon_path")
        if icon_path and os.path.exists(icon_path):
            pixmap = QIcon(icon_path).pixmap(64,64)
            if pixmap.isNull():
                 pixmap = QIcon.fromTheme("applications-games").pixmap(64, 64)
            icon = QIcon(pixmap)
        else:
             icon = QIcon.fromTheme("applications-games", QIcon("icon.png"))
        
        item = QListWidgetItem(icon, inst["name"])
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        instance_list.addItem(item)

app = QApplication(sys.argv)

from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile

# Load the UI file
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

ui_file_path = os.path.join(base_path, "mainwindow.ui")
ui_file = QFile(ui_file_path)
if not ui_file.open(QIODevice.OpenModeFlag.ReadOnly):
    print(f"Cannot open {ui_file_path}: {ui_file.errorString()}")
    sys.exit(-1)

loader = QUiLoader()
window = loader.load(ui_file)
ui_file.close()

if not window:
    print(loader.errorString())
    sys.exit(-1)

# Find widgets
status = window.findChild(QLabel, "statusLabel")
instance_list = window.findChild(QListWidget, "instanceList")
add_inst_btn = window.findChild(QPushButton, "addBtn")
remove_inst_btn = window.findChild(QPushButton, "removeBtn")
download_btn = window.findChild(QPushButton, "downloadBtn")
log_btn = window.findChild(QPushButton, "logsBtn")
launch_btn = window.findChild(QPushButton, "launchBtn")
kill_btn = window.findChild(QPushButton, "killBtn")
edit_btn = window.findChild(QPushButton, "editBtn")
instance_name_label = window.findChild(QLabel, "instanceName")
instance_icon_label = window.findChild(QLabel, "instanceIcon")

# Connect signals
instance_list.currentItemChanged.connect(update_selected_instance_details)
instance_list.itemDoubleClicked.connect(lambda: launch_instance())
add_inst_btn.clicked.connect(add_new_instance)
remove_inst_btn.clicked.connect(remove_selected_instance)
download_btn.clicked.connect(download_instance_dialog)
log_btn.clicked.connect(show_logs)
launch_btn.clicked.connect(launch_instance)
kill_btn.clicked.connect(kill_instance)
edit_btn.clicked.connect(open_instance_editor)

# Initialize data
refresh_instances()
update_selected_instance_details()

# Initialize log viewer
log_viewer = LogViewer(window)

window.show()
sys.exit(app.exec())
