#!/usr/bin/env python3
"""
WayKeyLight - System tray application for controlling Elgato Key Lights on Wayland/Hyprland
"""

import os
import sys
import json
import threading

# Suppress Qt style warnings
os.environ.pop('QT_STYLE_OVERRIDE', None)
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import requests
from zeroconf import ServiceBrowser, Zeroconf, ServiceInfo
from PyQt6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QWidget, QPushButton,
    QSlider, QLabel, QHBoxLayout, QVBoxLayout, QCheckBox, QFrame,
    QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QPoint, QRect, QThread, pyqtSlot, QEvent
from PyQt6.QtGui import QIcon, QAction, QCursor, QScreen, QPalette, QColor, QMouseEvent


class APIWorker(QThread):
    """Worker thread for API calls to avoid blocking UI"""
    result_ready = pyqtSignal(str, bool, int)  # serial, is_on, brightness
    
    def __init__(self, light, operation, value=None):
        super().__init__()
        self.light = light
        self.operation = operation
        self.value = value
        
    def run(self):
        """Execute API call in thread"""
        try:
            if self.operation == 'toggle':
                success = self.light.toggle()
                if success:
                    self.result_ready.emit(self.light.serial_number, self.light.is_on, self.light.brightness)
            elif self.operation == 'brightness':
                success = self.light.set_state(brightness=self.value)
                if success:
                    self.result_ready.emit(self.light.serial_number, self.light.is_on, self.light.brightness)
            elif self.operation == 'power':
                success = self.light.set_state(on=self.value)
                if success:
                    self.result_ready.emit(self.light.serial_number, self.light.is_on, self.light.brightness)
            elif self.operation == 'status':
                self.light.get_status()
                self.result_ready.emit(self.light.serial_number, self.light.is_on, self.light.brightness)
        except Exception as e:
            print(f"API Worker error: {e}")


@dataclass
class KeyLight:
    """Represents an Elgato Key Light device"""
    name: str
    ip: str
    port: int
    serial_number: str
    is_on: bool = False
    brightness: int = 50
    temperature: int = 4500
    
    @property
    def base_url(self) -> str:
        return f"http://{self.ip}:{self.port}/elgato"
    
    def get_status(self) -> Optional[Dict[str, Any]]:
        """Get current light status"""
        try:
            response = requests.get(f"{self.base_url}/lights", timeout=1)
            if response.status_code == 200:
                data = response.json()
                if data.get("lights") and len(data["lights"]) > 0:
                    light = data["lights"][0]
                    self.is_on = light.get("on", 0) == 1
                    self.brightness = light.get("brightness", 50)
                    self.temperature = light.get("temperature", 4500)
                    return light
        except Exception as e:
            print(f"Error getting status for {self.name}: {e}")
        return None
    
    def get_friendly_name(self) -> str:
        """Get the user-configured friendly name from settings"""
        try:
            # Try settings endpoint first
            response = requests.get(f"{self.base_url}/settings", timeout=1)
            if response.status_code == 200:
                settings = response.json()
                if "displayName" in settings and settings["displayName"]:
                    return settings["displayName"]
        except:
            pass
        
        try:
            # Try accessory-info endpoint
            response = requests.get(f"{self.base_url}/accessory-info", timeout=1)
            if response.status_code == 200:
                info = response.json()
                if "displayName" in info and info["displayName"]:
                    return info["displayName"]
        except:
            pass
        
        # Fallback to original name with IP for differentiation
        return f"{self.name} ({self.ip.split('.')[-1]})"
    
    def set_state(self, on: Optional[bool] = None, brightness: Optional[int] = None, 
                  temperature: Optional[int] = None) -> bool:
        """Set light state"""
        try:
            # Prepare update data
            update_data = {
                "lights": [{
                    "on": 1 if (on if on is not None else self.is_on) else 0,
                    "brightness": brightness if brightness is not None else self.brightness,
                    "temperature": temperature if temperature is not None else self.temperature
                }]
            }
            
            response = requests.put(
                f"{self.base_url}/lights",
                json=update_data,
                headers={"Content-Type": "application/json"},
                timeout=1
            )
            
            if response.status_code == 200:
                # Update local state
                if on is not None:
                    self.is_on = on
                if brightness is not None:
                    self.brightness = brightness
                if temperature is not None:
                    self.temperature = temperature
                return True
        except Exception as e:
            print(f"Error setting state for {self.name}: {e}")
        return False
    
    def toggle(self) -> bool:
        """Toggle light on/off"""
        return self.set_state(on=not self.is_on)


class KeyLightDiscovery(QObject):
    """Discovers Elgato Key Lights on the network using mDNS"""
    
    light_discovered = pyqtSignal(KeyLight)
    light_removed = pyqtSignal(str)  # serial number
    
    def __init__(self):
        super().__init__()
        self.zeroconf = None
        self.browser = None
        self.lights: Dict[str, KeyLight] = {}
        self.executor = ThreadPoolExecutor(max_workers=2)
        
    def start(self):
        """Start discovery service"""
        self.zeroconf = Zeroconf()
        self.browser = ServiceBrowser(
            self.zeroconf,
            "_elg._tcp.local.",
            self
        )
        print("Started Key Light discovery service")
    
    def stop(self):
        """Stop discovery service"""
        if self.zeroconf:
            self.zeroconf.close()
            self.zeroconf = None
            self.browser = None
        self.executor.shutdown(wait=False)
        print("Stopped Key Light discovery service")
    
    def add_service(self, zeroconf: Zeroconf, type_: str, name: str) -> None:
        """Called when a new service is discovered"""
        self.executor.submit(self._process_service_async, zeroconf, type_, name)
    
    def update_service(self, zeroconf: Zeroconf, type_: str, name: str) -> None:
        """Called when a service is updated"""
        self.executor.submit(self._process_service_async, zeroconf, type_, name)
    
    def remove_service(self, zeroconf: Zeroconf, type_: str, name: str) -> None:
        """Called when a service is removed"""
        # Extract serial number from name (format: "Elgato Key Light XXXX._elg._tcp.local.")
        parts = name.split(" ")
        if len(parts) >= 4:
            serial = parts[3].split(".")[0]
            if serial in self.lights:
                del self.lights[serial]
                self.light_removed.emit(serial)
                print(f"Key Light removed: {serial}")
    
    def _process_service_async(self, zeroconf: Zeroconf, type_: str, name: str):
        """Process service info in thread pool"""
        info = zeroconf.get_service_info(type_, name)
        if info:
            self._process_service(info)
    
    def _process_service(self, info: ServiceInfo) -> None:
        """Process discovered service info"""
        if info.addresses:
            ip = ".".join(map(str, info.addresses[0]))
            port = info.port
            
            # Extract properties
            properties = info.properties
            serial = properties.get(b'id', b'').decode('utf-8')
            display_name = properties.get(b'md', b'Elgato Key Light').decode('utf-8')
            
            if serial and serial not in self.lights:
                light = KeyLight(
                    name=display_name,
                    ip=ip,
                    port=port,
                    serial_number=serial
                )
                
                # Get initial status
                light.get_status()
                
                # Get friendly name from device
                friendly_name = light.get_friendly_name()
                light.name = friendly_name
                
                self.lights[serial] = light
                self.light_discovered.emit(light)
                print(f"Discovered Key Light: {friendly_name} at {ip}:{port}")


class LightControlWidget(QWidget):
    """Widget for controlling a single light"""
    
    def __init__(self, light: KeyLight, parent=None):
        super().__init__(parent)
        self.light = light
        self.api_worker = None
        self.brightness_timer = None
        self.pending_brightness = None
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)
        
        # Header with checkbox and name
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        # Power checkbox
        self.power_checkbox = QCheckBox()
        self.power_checkbox.setChecked(self.light.is_on)
        self.power_checkbox.stateChanged.connect(self.on_power_changed)
        header_layout.addWidget(self.power_checkbox)
        
        # Light name
        self.name_label = QLabel(self.light.name)
        self.name_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        header_layout.addWidget(self.name_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Brightness control
        brightness_layout = QHBoxLayout()
        brightness_layout.setSpacing(8)
        
        # Brightness icon/label
        brightness_label = QLabel("☀")
        brightness_label.setFixedWidth(20)
        brightness_layout.addWidget(brightness_label)
        
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(1)
        self.brightness_slider.setMaximum(100)
        self.brightness_slider.setValue(self.light.brightness)
        self.brightness_slider.setFixedHeight(20)
        # Enable jump-to-position on click
        self.brightness_slider.setPageStep(1)
        self.brightness_slider.setSingleStep(1)
        self.brightness_slider.valueChanged.connect(self.on_brightness_changed)
        # Install event filter for click-to-position
        self.brightness_slider.installEventFilter(self)
        brightness_layout.addWidget(self.brightness_slider)
        
        self.brightness_value = QLabel(f"{self.light.brightness}%")
        self.brightness_value.setFixedWidth(35)
        self.brightness_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        brightness_layout.addWidget(self.brightness_value)
        
        layout.addLayout(brightness_layout)
        
        self.setLayout(layout)
        
    def on_power_changed(self, state):
        """Handle power checkbox change"""
        is_on = state == Qt.CheckState.Checked.value
        # Run in thread
        self.api_worker = APIWorker(self.light, 'power', is_on)
        self.api_worker.result_ready.connect(self.on_api_result)
        self.api_worker.start()
        
    def on_brightness_changed(self, value):
        """Handle brightness slider change with heavy throttling"""
        self.brightness_value.setText(f"{value}%")
        self.pending_brightness = value
        
        # Cancel previous timer if it exists
        if self.brightness_timer:
            self.brightness_timer.stop()
            self.brightness_timer = None
            
        # Create new timer with longer delay for dragging
        self.brightness_timer = QTimer()
        self.brightness_timer.setSingleShot(True)
        self.brightness_timer.timeout.connect(self.apply_pending_brightness)
        self.brightness_timer.start(500)  # 500ms delay
        
    def apply_pending_brightness(self):
        """Apply the pending brightness change"""
        if self.pending_brightness is not None:
            self.api_worker = APIWorker(self.light, 'brightness', self.pending_brightness)
            self.api_worker.result_ready.connect(self.on_api_result)
            self.api_worker.start()
            self.pending_brightness = None
            
    @pyqtSlot(str, bool, int)
    def on_api_result(self, serial, is_on, brightness):
        """Handle API result from worker thread"""
        if serial == self.light.serial_number:
            self.light.is_on = is_on
            self.light.brightness = brightness
            self.update_state()
        
    def update_state(self):
        """Update widget to reflect current light state"""
        self.power_checkbox.blockSignals(True)
        self.power_checkbox.setChecked(self.light.is_on)
        self.power_checkbox.blockSignals(False)
        
        if self.pending_brightness is None:  # Only update if not currently dragging
            self.brightness_slider.blockSignals(True)
            self.brightness_slider.setValue(self.light.brightness)
            self.brightness_value.setText(f"{self.light.brightness}%")
            self.brightness_slider.blockSignals(False)
        
    def update_name(self, name: str):
        """Update the light name label"""
        self.name_label.setText(name)
    
    def eventFilter(self, source, event):
        """Event filter to handle click-to-position on slider"""
        if source == self.brightness_slider and event.type() == QEvent.Type.MouseButtonPress:
            if isinstance(event, QMouseEvent):
                # Calculate position as percentage
                click_x = event.position().x()
                slider_width = self.brightness_slider.width()
                
                # Calculate the value based on click position
                if slider_width > 0:
                    # Account for slider handle width (roughly 12px)
                    effective_width = slider_width - 12
                    adjusted_x = max(0, min(click_x - 6, effective_width))
                    
                    # Calculate percentage and map to slider range
                    percentage = adjusted_x / effective_width
                    min_val = self.brightness_slider.minimum()
                    max_val = self.brightness_slider.maximum()
                    new_value = int(min_val + (max_val - min_val) * percentage)
                    
                    # Set the value directly
                    self.brightness_slider.setValue(new_value)
                    return True  # Event handled
                    
        return super().eventFilter(source, event)


class ControlPopup(QWidget):
    """Popup window for light controls"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.light_widgets: Dict[str, LightControlWidget] = {}
        self.setup_ui()
        
        # Set window title for identification
        self.setWindowTitle("WayKeyLight Controls")
        
        # Window flags for floating overlay
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Dialog
        )
        
        # Make it a tooltip-style window for Wayland
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        
    def setup_ui(self):
        # Main container with background
        container = QWidget()
        container.setObjectName("container")
        
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(12, 10, 12, 10)
        self.main_layout.setSpacing(8)
        
        # Title with lightbulb icon
        title = QLabel("💡 WayKeyLight")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(title)
        
        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("separator")
        self.main_layout.addWidget(line)
        
        # Container for light controls
        self.lights_layout = QVBoxLayout()
        self.lights_layout.setSpacing(6)
        self.main_layout.addLayout(self.lights_layout)
        
        # No lights message
        self.no_lights_label = QLabel("No lights found")
        self.no_lights_label.setObjectName("no_lights")
        self.no_lights_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lights_layout.addWidget(self.no_lights_label)
        
        # Bottom buttons - more compact
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        refresh_button = QPushButton("↻")
        refresh_button.setObjectName("refresh_btn")
        refresh_button.setFixedSize(28, 24)
        refresh_button.setToolTip("Refresh")
        refresh_button.clicked.connect(self.refresh_requested)
        button_layout.addWidget(refresh_button)
        
        button_layout.addStretch()
        
        close_button = QPushButton("✕")
        close_button.setObjectName("close_btn")
        close_button.setFixedSize(28, 24)
        close_button.setToolTip("Close")
        close_button.clicked.connect(self.hide)
        button_layout.addWidget(close_button)
        
        self.main_layout.addLayout(button_layout)
        
        container.setLayout(self.main_layout)
        
        # Outer layout for the transparent window
        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(container)
        self.setLayout(outer_layout)
        
        # Dark theme styling
        self.setStyleSheet("""
            #container {
                background-color: #1e1e1e;
                border: 1px solid #3c3c3c;
                border-radius: 8px;
            }
            
            #title {
                color: #e0e0e0;
                font-weight: bold;
                font-size: 12px;
                padding: 2px;
            }
            
            #separator {
                background-color: #3c3c3c;
                max-height: 1px;
            }
            
            QLabel {
                color: #e0e0e0;
            }
            
            #no_lights {
                color: #808080;
                padding: 15px;
            }
            
            QCheckBox {
                color: #e0e0e0;
                spacing: 5px;
            }
            
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #606060;
                border-radius: 3px;
                background-color: #2d2d2d;
            }
            
            QCheckBox::indicator:checked {
                background-color: #0d7377;
                border-color: #14b8a6;
            }
            
            QSlider::groove:horizontal {
                height: 4px;
                background: #3c3c3c;
                border-radius: 2px;
            }
            
            QSlider::handle:horizontal {
                width: 12px;
                height: 12px;
                background: #14b8a6;
                border-radius: 6px;
                margin: -4px 0;
            }
            
            QSlider::sub-page:horizontal {
                background: #0d7377;
                border-radius: 2px;
            }
            
            QPushButton {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 2px;
                font-weight: bold;
            }
            
            QPushButton:hover {
                background-color: #3c3c3c;
                border-color: #4c4c4c;
            }
            
            QPushButton:pressed {
                background-color: #252525;
            }
            
            #refresh_btn, #close_btn {
                font-size: 14px;
            }
        """)
        
        # Set fixed size to prevent stretching
        self.setFixedWidth(280)
        self.setMaximumHeight(400)  # Prevent vertical stretching
        
    def add_light(self, light: KeyLight):
        """Add a light control widget"""
        if light.serial_number not in self.light_widgets:
            # Remove "no lights" label if this is the first light
            if len(self.light_widgets) == 0:
                self.no_lights_label.setVisible(False)
                
            widget = LightControlWidget(light)
            self.light_widgets[light.serial_number] = widget
            
            # Add separator between lights
            if len(self.light_widgets) > 1:
                separator = QFrame()
                separator.setFrameShape(QFrame.Shape.HLine)
                separator.setObjectName("light_separator")
                separator.setStyleSheet("background-color: #2d2d2d; max-height: 1px;")
                self.lights_layout.addWidget(separator)
                
            self.lights_layout.addWidget(widget)
            
    def remove_light(self, serial: str):
        """Remove a light control widget"""
        if serial in self.light_widgets:
            widget = self.light_widgets[serial]
            self.lights_layout.removeWidget(widget)
            widget.deleteLater()
            del self.light_widgets[serial]
            
            # Show "no lights" label if no lights remain
            if len(self.light_widgets) == 0:
                self.no_lights_label.setVisible(True)
                
    def update_light(self, light: KeyLight):
        """Update a light control widget"""
        if light.serial_number in self.light_widgets:
            self.light_widgets[light.serial_number].update_state()
            
    def showEvent(self, event):
        """Handle show event"""
        super().showEvent(event)
        # Note: Window positioning doesn't work on Wayland
        # Position is controlled by Hyprland window rules instead
        # Update all light states when showing
        for widget in self.light_widgets.values():
            widget.update_state()
            
    def refresh_requested(self):
        """Signal that refresh was requested"""
        pass
    
    def mousePressEvent(self, event):
        """Allow dragging the window"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            
    def mouseMoveEvent(self, event):
        """Handle window dragging"""
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, 'drag_position'):
            self.move(event.globalPosition().toPoint() - self.drag_position)


class WayKeyLightTray(QSystemTrayIcon):
    """System tray application for controlling Key Lights"""
    
    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.lights: Dict[str, KeyLight] = {}
        self.update_workers = []
        
        # Create popup window
        self.popup = ControlPopup()
        self.popup.refresh_requested = self.refresh_lights
        
        # Setup discovery
        self.discovery = KeyLightDiscovery()
        self.discovery.light_discovered.connect(self.on_light_discovered)
        self.discovery.light_removed.connect(self.on_light_removed)
        
        # Setup UI
        self.setup_tray_icon()
        self.create_menu()
        
        # Connect left-click to show popup
        self.activated.connect(self.on_tray_activated)
        
        # Setup update timer with longer interval
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_light_states)
        self.update_timer.start(10000)  # Update every 10 seconds instead of 5
        
        # Start discovery
        self.discovery.start()
        
    def setup_tray_icon(self):
        """Setup system tray icon"""
        # Try to load custom icon first
        import os
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.svg")
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
        else:
            # Fallback to system icons
            icon = QIcon.fromTheme("preferences-desktop-display")
            if icon.isNull():
                icon = self.app.style().standardIcon(self.app.style().StandardPixmap.SP_ComputerIcon)
        
        self.setIcon(icon)
        self.setToolTip("WayKeyLight - Click to control")
        self.show()
        
    def create_menu(self):
        """Create the right-click context menu"""
        menu = QMenu()
        
        # Open controls action
        open_action = menu.addAction("Open Controls")
        open_action.triggered.connect(self.show_popup)
        
        # Refresh action
        refresh_action = menu.addAction("Refresh")
        refresh_action.triggered.connect(self.refresh_lights)
        
        # Quit action
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_application)
        
        self.setContextMenu(menu)
        
    def on_tray_activated(self, reason):
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # Left click
            self.show_popup()
        
    def show_popup(self):
        """Show the control popup"""
        if self.popup.isVisible():
            self.popup.hide()
        else:
            self.popup.show()
            self.popup.raise_()
            self.popup.activateWindow()
            
    def on_light_discovered(self, light: KeyLight):
        """Handle new light discovery"""
        self.lights[light.serial_number] = light
        self.popup.add_light(light)
        
    def on_light_removed(self, serial: str):
        """Handle light removal"""
        if serial in self.lights:
            del self.lights[serial]
            self.popup.remove_light(serial)
            
    def update_light_states(self):
        """Periodically update light states in background"""
        for light in self.lights.values():
            worker = APIWorker(light, 'status')
            worker.result_ready.connect(self.on_status_update)
            worker.start()
            self.update_workers.append(worker)
            
    @pyqtSlot(str, bool, int)
    def on_status_update(self, serial, is_on, brightness):
        """Handle status update from worker"""
        if serial in self.lights:
            light = self.lights[serial]
            if light.is_on != is_on or light.brightness != brightness:
                light.is_on = is_on
                light.brightness = brightness
                self.popup.update_light(light)
        
        # Clean up finished workers
        self.update_workers = [w for w in self.update_workers if w.isRunning()]
                
    def refresh_lights(self):
        """Manually refresh light discovery"""
        self.discovery.stop()
        self.discovery.start()
        
    def quit_application(self):
        """Quit the application"""
        self.discovery.stop()
        self.popup.close()
        self.app.quit()


def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    # Set application identity for Wayland
    app.setApplicationName("WayKeyLight")
    app.setOrganizationName("WayKeyLight")
    app.setDesktopFileName("waykeylight")  # This sets the Wayland app_id
    
    # Force Fusion style and dark palette
    app.setStyle("Fusion")
    
    # Create system tray
    tray = WayKeyLightTray(app)
    
    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()