# WayKeyLight 💡

A beautiful, dark-themed system tray application for controlling Elgato Key Lights on Wayland/Hyprland.

![License](https://img.shields.io/badge/license-BSD--3--Clause-blue.svg)
![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![PyQt6](https://img.shields.io/badge/PyQt6-6.5%2B-green.svg)
![Wayland](https://img.shields.io/badge/Wayland-Compatible-orange.svg)

## ✨ Features

- 🔍 **Auto-discovery** of Elgato Key Lights on your network
- 🎛️ **Intuitive controls** with on/off toggles and brightness sliders
- 🌙 **Beautiful dark theme** that looks great on modern desktops
- 🖱️ **System tray integration** - left-click to open controls
- 🔄 **Real-time sync** - automatically updates when lights change
- 🚀 **Lightweight & responsive** - async API calls prevent UI blocking
- 🖼️ **Wayland native** - designed for Hyprland with proper window positioning

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Wayland compositor (tested on Hyprland)
- Elgato Key Light(s) on the same network

### Installation

1. **Clone the repository:**
```bash
git clone https://github.com/riclib/waykeylight.git
cd waykeylight
```

2. **Run the setup:**
```bash
make setup  # Creates virtual environment and installs dependencies
make run    # Launches the application
```

3. **For permanent installation:**
```bash
make install     # Installs to ~/.local/share/waykeylight
make autostart   # Enables autostart on login
```

## 🎮 Usage

### Basic Controls

- **Left-click** the tray icon to open the control panel
- **Toggle** lights on/off with the checkbox
- **Adjust brightness** with the slider (1-100%)
- **Refresh** to discover new lights
- **Right-click** for quick menu options

### Keyboard Shortcuts

The popup window can be dragged to reposition if needed.

## ⚙️ Configuration

### Hyprland Window Positioning

For proper positioning on Hyprland, add these rules to `~/.config/hypr/hyprland.conf`:

```bash
# Float and position the WayKeyLight popup
windowrulev2 = float, title:(WayKeyLight Controls)
windowrulev2 = move 100%-320 40, title:(WayKeyLight Controls), floating:1
windowrulev2 = size 280 350, title:(WayKeyLight Controls), floating:1
windowrulev2 = pin, title:(WayKeyLight Controls), floating:1
```

Adjust `100%-320` for your screen:
- `100%-320` = 280px window + 40px margin from right edge
- For ultrawide monitors, this keeps it near the tray icon

### Auto-start with Hyprland

Add to your `~/.config/hypr/hyprland.conf`:
```bash
exec-once = /path/to/waykeylight/run.sh
```

## 🛠️ Development

### Project Structure

```
waykeylight/
├── waykeylight.py          # Main application
├── requirements.txt        # Python dependencies
├── setup.sh               # Setup script
├── run.sh                 # Launch script
├── Makefile              # Installation automation
└── venv/                 # Virtual environment (after setup)
```

### API Endpoints

The app communicates with Key Lights via REST API:
- Discovery: mDNS `_elg._tcp.local.`
- Status: `GET http://<ip>:9123/elgato/lights`
- Control: `PUT http://<ip>:9123/elgato/lights`
- Settings: `GET http://<ip>:9123/elgato/settings`

### Building from Source

```bash
# Clone and enter directory
git clone https://github.com/riclib/waykeylight.git
cd waykeylight

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run
python waykeylight.py
```

## 🐛 Troubleshooting

### Lights Not Discovered

- Ensure Key Lights are powered on and connected to the same network
- Check firewall settings (allow mDNS port 5353)
- Try the "Refresh" button in the app
- Verify with: `avahi-browse -ar | grep elg`

### Window Positioning Issues

Window positioning is controlled by the Wayland compositor, not the application. Use Hyprland window rules as shown above.

### System Tray Icon Missing

Ensure your bar/panel supports StatusNotifierItem protocol:
- Waybar with tray module enabled
- Other bars with system tray support

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the BSD 3-Clause License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Elgato for the Key Light API
- PyQt6 for the excellent GUI framework
- The Hyprland community for the amazing compositor

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/riclib/waykeylight/issues)
- **Discussions:** [GitHub Discussions](https://github.com/riclib/waykeylight/discussions)

---

Made with ❤️ for the Wayland community