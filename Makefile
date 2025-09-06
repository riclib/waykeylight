.PHONY: setup run install uninstall clean help

INSTALL_DIR := $(HOME)/.local/share/waykeylight
DESKTOP_DIR := $(HOME)/.local/share/applications
AUTOSTART_DIR := $(HOME)/.config/autostart

help:
	@echo "WayKeyLight - Elgato Key Light Controller"
	@echo ""
	@echo "Available targets:"
	@echo "  setup       - Create virtual environment and install dependencies"
	@echo "  run         - Run the application"
	@echo "  install     - Install to ~/.local/share/waykeylight"
	@echo "  uninstall   - Remove installation"
	@echo "  autostart   - Enable autostart on login"
	@echo "  clean       - Remove virtual environment"
	@echo ""
	@echo "Quick start:"
	@echo "  make setup && make run"

setup:
	@echo "Setting up WayKeyLight..."
	@chmod +x setup.sh
	@./setup.sh

run: 
	@if [ ! -d "venv" ]; then \
		echo "Virtual environment not found. Running setup first..."; \
		$(MAKE) setup; \
	fi
	@chmod +x run.sh
	@./run.sh

install: setup
	@echo "Installing WayKeyLight to $(INSTALL_DIR)..."
	@mkdir -p $(INSTALL_DIR)
	@mkdir -p $(DESKTOP_DIR)
	
	# Copy application files
	@cp -r venv $(INSTALL_DIR)/
	@cp waykeylight.py $(INSTALL_DIR)/
	@cp run.sh $(INSTALL_DIR)/
	@cp requirements.txt $(INSTALL_DIR)/
	
	# Create desktop entry with correct path
	@echo "[Desktop Entry]" > $(DESKTOP_DIR)/waykeylight.desktop
	@echo "Type=Application" >> $(DESKTOP_DIR)/waykeylight.desktop
	@echo "Name=WayKeyLight" >> $(DESKTOP_DIR)/waykeylight.desktop
	@echo "Comment=Control Elgato Key Lights from system tray" >> $(DESKTOP_DIR)/waykeylight.desktop
	@echo "Exec=$(INSTALL_DIR)/run.sh" >> $(DESKTOP_DIR)/waykeylight.desktop
	@echo "Icon=preferences-desktop-display" >> $(DESKTOP_DIR)/waykeylight.desktop
	@echo "Terminal=false" >> $(DESKTOP_DIR)/waykeylight.desktop
	@echo "Categories=Utility;" >> $(DESKTOP_DIR)/waykeylight.desktop
	@echo "StartupNotify=false" >> $(DESKTOP_DIR)/waykeylight.desktop
	
	@chmod +x $(INSTALL_DIR)/run.sh
	@chmod +x $(INSTALL_DIR)/waykeylight.py
	
	@echo "Installation complete!"
	@echo "You can now:"
	@echo "  - Run from terminal: $(INSTALL_DIR)/run.sh"
	@echo "  - Find it in your application menu"
	@echo "  - Enable autostart: make autostart"

uninstall:
	@echo "Uninstalling WayKeyLight..."
	@rm -rf $(INSTALL_DIR)
	@rm -f $(DESKTOP_DIR)/waykeylight.desktop
	@rm -f $(AUTOSTART_DIR)/waykeylight.desktop
	@echo "Uninstall complete!"

autostart:
	@echo "Enabling autostart..."
	@mkdir -p $(AUTOSTART_DIR)
	
	@if [ -f "$(INSTALL_DIR)/run.sh" ]; then \
		cp $(DESKTOP_DIR)/waykeylight.desktop $(AUTOSTART_DIR)/; \
		echo "Autostart enabled!"; \
	else \
		echo "Please run 'make install' first"; \
		exit 1; \
	fi

clean:
	@echo "Cleaning up..."
	@rm -rf venv
	@rm -rf __pycache__
	@rm -f *.pyc
	@echo "Clean complete!"