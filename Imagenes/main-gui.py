#!/usr/bin/env python3
import sys
import os
import requests
import json
import base64
import datetime
import time
from pathlib import Path

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QTextEdit, QPushButton,
                               QFileDialog, QProgressBar, QMessageBox, QFrame,
                               QLineEdit) # Añadido QLineEdit
from PySide6.QtCore import Qt, QThread, Signal, QSize, QPropertyAnimation, QEasingCurve, QSettings
from PySide6.QtGui import QColor, QPalette, QFont, QPixmap, QIcon, QImage

# Constantes para QSettings
ORG_NAME = "MiApp"
APP_NAME = "GeneradorImagenesFlux"
API_KEY_SETTING = "HuggingFaceApiKey"

class ImageGeneratorThread(QThread):
    """Thread para generar imágenes sin bloquear la interfaz de usuario"""
    progress_signal = Signal(str)
    result_signal = Signal(bytes)
    error_signal = Signal(str)
    finished_signal = Signal(float)

    def __init__(self, prompt, api_key): # Añadido api_key
        super().__init__()
        self.prompt = prompt
        self.api_key = api_key # Guardar la API Key

    def run(self):
        try:
            start_time = time.time()
            self.progress_signal.emit("Enviando solicitud a FLUX.1-schnell...")

            url = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
            headers = {
                "Authorization": f"Bearer {self.api_key}", # Usar la API Key del constructor
                "Content-Type": "application/json"
            }
            data = {
                "inputs": self.prompt
            }

            # Enviar la solicitud POST
            response = requests.post(url, headers=headers, json=data)

            if response.status_code == 200:
                elapsed_time = time.time() - start_time
                self.result_signal.emit(response.content)
                self.finished_signal.emit(elapsed_time)
            else:
                self.error_signal.emit(f"Error {response.status_code}: {response.text}")
        except Exception as e:
            self.error_signal.emit(f"Error: {str(e)}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings(ORG_NAME, APP_NAME) # Para guardar/cargar la API Key
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Generador de Imágenes con FLUX.1-schnell")
        self.setMinimumSize(900, 750) # Aumentado un poco para el nuevo campo

        self.apply_dark_theme()

        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        title_label = QLabel("🌟 GENERADOR DE IMÁGENES CON FLUX.1-SCHNELL")
        title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont("Arial", 16, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #BB86FC; margin-bottom: 10px;")
        main_layout.addWidget(title_label)

        # Sección para la API Key
        api_key_layout = QHBoxLayout()
        api_key_label = QLabel("API Key Hugging Face:")
        api_key_label.setFont(QFont("Arial", 10))
        api_key_label.setStyleSheet("color: #03DAC6;")
        api_key_layout.addWidget(api_key_label)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Ingresa tu API Key de Hugging Face (hf_...)")
        self.api_key_input.setEchoMode(QLineEdit.Password) # Ocultar la API Key
        self.api_key_input.setStyleSheet("""
            QLineEdit {
                background-color: #2D2D2D;
                color: #E0E0E0;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border: 1px solid #BB86FC;
            }
        """)
        self.load_api_key() # Cargar la API Key guardada
        api_key_layout.addWidget(self.api_key_input, 1) # El 1 es para que ocupe más espacio

        self.save_api_key_button = QPushButton("🔒 Guardar Key")
        self.save_api_key_button.setStyleSheet("""
            QPushButton {
                background-color: #4A4A4A; color: #E0E0E0; border: none;
                border-radius: 4px; padding: 6px 10px; font-size: 10px;
            }
            QPushButton:hover { background-color: #5A5A5A; }
            QPushButton:pressed { background-color: #6A6A6A; }
        """)
        self.save_api_key_button.setToolTip("Guarda la API Key para futuras sesiones.")
        self.save_api_key_button.clicked.connect(self.save_api_key)
        api_key_layout.addWidget(self.save_api_key_button)

        main_layout.addLayout(api_key_layout)


        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("background-color: #333333;")
        main_layout.addWidget(separator)

        prompt_layout = QVBoxLayout()
        prompt_label = QLabel("Ingresa tu prompt:")
        prompt_label.setFont(QFont("Arial", 11))
        prompt_label.setStyleSheet("color: #03DAC6; margin-top: 10px;")
        prompt_layout.addWidget(prompt_label)

        self.prompt_textedit = QTextEdit()
        self.prompt_textedit.setStyleSheet("""
            QTextEdit {
                background-color: #2D2D2D;
                color: #E0E0E0;
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 8px;
                font-size: 12px;
            }
            QTextEdit:focus {
                border: 1px solid #BB86FC;
            }
        """)
        self.prompt_textedit.setMinimumHeight(100)

        default_prompt = """A skilled hacker in a dark cyber security environment, surrounded by glowing screens filled with code. Use cool blue and green tones for lighting. The hacker wears a hoodie, their face partially obscured. Emphasize a futuristic, high-tech atmosphere with a dynamic angle and sharp focus on details."""
        self.prompt_textedit.setText(default_prompt)

        prompt_layout.addWidget(self.prompt_textedit)
        main_layout.addLayout(prompt_layout)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)

        self.generate_button = QPushButton("🚀 Generar Imagen")
        self.generate_button.setStyleSheet("""
            QPushButton {
                background-color: #BB86FC; color: #121212; border: none;
                border-radius: 4px; padding: 10px 15px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #A26EFC; }
            QPushButton:pressed { background-color: #8E4AFF; }
        """)
        self.generate_button.setMinimumHeight(40)
        self.generate_button.clicked.connect(self.generate_image)
        buttons_layout.addWidget(self.generate_button)

        self.save_button = QPushButton("💾 Guardar Imagen")
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #03DAC6; color: #121212; border: none;
                border-radius: 4px; padding: 10px 15px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #00C4B0; }
            QPushButton:pressed { background-color: #00A896; }
            QPushButton:disabled { background-color: #4D5656; color: #8E8E8E; }
        """)
        self.save_button.setMinimumHeight(40)
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_image)
        buttons_layout.addWidget(self.save_button)

        self.clear_button = QPushButton("🗑️ Limpiar")
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #3D3D3D; color: #E0E0E0; border: none;
                border-radius: 4px; padding: 10px 15px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #4D4D4D; }
            QPushButton:pressed { background-color: #5D5D5D; }
        """)
        self.clear_button.setMinimumHeight(40)
        self.clear_button.clicked.connect(self.clear_ui)
        buttons_layout.addWidget(self.clear_button)

        main_layout.addLayout(buttons_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555555; border-radius: 3px; text-align: center;
                background-color: #2D2D2D; height: 12px;
            }
            QProgressBar::chunk { background-color: #BB86FC; width: 10px; margin: 0.5px; }
        """)
        main_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #03DAC6; margin-top: 5px;")
        self.status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_label)

        self.image_panel = QLabel("No hay imagen generada")
        self.image_panel.setAlignment(Qt.AlignCenter)
        self.image_panel.setMinimumHeight(300)
        self.image_panel.setStyleSheet("""
            QLabel {
                background-color: #1E1E1E; border: 1px solid #333333;
                border-radius: 5px; color: #6E6E6E; font-style: italic;
            }
        """)
        main_layout.addWidget(self.image_panel)

        info_label = QLabel("Desarrollado con PySide6 | FLUX.1-schnell API by Hugging Face")
        info_label.setAlignment(Qt.AlignRight)
        info_label.setStyleSheet("color: #6E6E6E; font-size: 9px; margin-top: 5px;")
        main_layout.addWidget(info_label)

        self.current_image = None
        self.show()

    def apply_dark_theme(self):
        dark_palette = QPalette()
        dark_color = QColor(18, 18, 18)
        disabled_color = QColor(70, 70, 70)
        text_color = QColor(225, 225, 225)
        highlight_color = QColor(187, 134, 252)

        dark_palette.setColor(QPalette.Window, dark_color)
        dark_palette.setColor(QPalette.WindowText, text_color)
        dark_palette.setColor(QPalette.Base, QColor(30, 30, 30))
        dark_palette.setColor(QPalette.AlternateBase, dark_color)
        dark_palette.setColor(QPalette.ToolTipBase, highlight_color)
        dark_palette.setColor(QPalette.ToolTipText, dark_color)
        dark_palette.setColor(QPalette.Text, text_color)
        dark_palette.setColor(QPalette.Disabled, QPalette.Text, disabled_color)
        dark_palette.setColor(QPalette.Button, QColor(45, 45, 45))
        dark_palette.setColor(QPalette.ButtonText, text_color)
        dark_palette.setColor(QPalette.Disabled, QPalette.ButtonText, disabled_color)
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Link, highlight_color)
        dark_palette.setColor(QPalette.Highlight, highlight_color)
        dark_palette.setColor(QPalette.HighlightedText, dark_color)
        dark_palette.setColor(QPalette.Disabled, QPalette.HighlightedText, disabled_color)

        QApplication.setPalette(dark_palette)
        self.setStyleSheet("""
            QMainWindow { background-color: #121212; }
            QToolTip {
                color: #121212; background-color: #BB86FC;
                border: 1px solid #BB86FC; border-radius: 2px;
            }
        """)

    def load_api_key(self):
        """Carga la API Key desde QSettings."""
        api_key = self.settings.value(API_KEY_SETTING, "")
        if api_key:
            self.api_key_input.setText(api_key)

    def save_api_key(self):
        """Guarda la API Key en QSettings."""
        api_key = self.api_key_input.text().strip()
        if api_key:
            self.settings.setValue(API_KEY_SETTING, api_key)
            QMessageBox.information(self, "API Key Guardada", "La API Key ha sido guardada.")
            self.status_label.setText("🔑 API Key guardada.")
            self.status_label.setStyleSheet("color: #03DAC6;")
        else:
            self.settings.remove(API_KEY_SETTING) # Borrar si está vacía
            QMessageBox.warning(self, "API Key Borrada", "El campo de API Key está vacío. La Key guardada ha sido eliminada.")
            self.status_label.setText("🔑 API Key eliminada de la configuración.")
            self.status_label.setStyleSheet("color: #CF6679;")


    def generate_image(self):
        prompt = self.prompt_textedit.toPlainText().strip()
        api_key = self.api_key_input.text().strip() # Leer la API Key

        if not api_key:
            QMessageBox.warning(self, "Advertencia", "Por favor, ingresa tu API Key de Hugging Face.")
            self.api_key_input.setFocus()
            return
        if not api_key.startswith("hf_"):
             QMessageBox.warning(self, "Advertencia", "La API Key de Hugging Face generalmente comienza con 'hf_'. Verifica que sea correcta.")
             self.api_key_input.setFocus()
             return
        if not prompt:
            QMessageBox.warning(self, "Advertencia", "Por favor, ingresa un prompt primero.")
            self.prompt_textedit.setFocus()
            return

        self.toggle_ui(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Generando imagen...")
        self.status_label.setStyleSheet("color: #BB86FC;")

        self.thread = ImageGeneratorThread(prompt, api_key) # Pasar la API Key al thread
        self.thread.progress_signal.connect(self.update_status)
        self.thread.result_signal.connect(self.process_image)
        self.thread.error_signal.connect(self.show_error)
        self.thread.finished_signal.connect(self.generation_finished)
        self.thread.start()

    def update_status(self, message):
        self.status_label.setText(message)

    def process_image(self, image_data):
        self.current_image = image_data
        image = QImage.fromData(image_data)
        pixmap = QPixmap.fromImage(image)
        scaled_pixmap = pixmap.scaled(
            self.image_panel.width() - 20,
            self.image_panel.height() - 20,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.image_panel.setPixmap(scaled_pixmap)
        self.save_button.setEnabled(True)

    def generation_finished(self, elapsed_time):
        self.toggle_ui(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"✅ ¡Imagen generada en {elapsed_time:.2f} segundos!")
        self.status_label.setStyleSheet("color: #03DAC6;")

    def show_error(self, error_message):
        self.toggle_ui(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"❌ Error: {error_message}")
        self.status_label.setStyleSheet("color: #CF6679;")
        QMessageBox.critical(self, "Error", error_message)

    def save_image(self):
        if not self.current_image:
            return

        images_dir = Path("imagenes")
        images_dir.mkdir(exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = str(images_dir / f"imagen_{timestamp}.jpg")

        filename, _ = QFileDialog.getSaveFileName(
            self, "Guardar Imagen", default_filename, "Imágenes (*.jpg *.jpeg *.png)"
        )

        if filename:
            try:
                with open(filename, "wb") as f:
                    f.write(self.current_image)
                self.status_label.setText(f"💾 Imagen guardada como: {Path(filename).name}")
                self.status_label.setStyleSheet("color: #03DAC6;")
                QMessageBox.information(
                    self, "Imagen Guardada",
                    f"La imagen ha sido guardada exitosamente en:\n{filename}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Error al Guardar", f"No se pudo guardar la imagen: {str(e)}")

    def clear_ui(self):
        # No limpiamos la API Key aquí, el usuario puede borrarla manualmente o con el botón de guardar (si está vacío)
        self.prompt_textedit.clear()
        self.image_panel.clear()
        self.image_panel.setText("No hay imagen generada")
        self.status_label.clear()
        self.current_image = None
        self.save_button.setEnabled(False)

    def toggle_ui(self, enabled):
        self.api_key_input.setEnabled(enabled) # Controlar también la edición de la API key
        self.save_api_key_button.setEnabled(enabled)
        self.prompt_textedit.setEnabled(enabled)
        self.generate_button.setEnabled(enabled)
        self.clear_button.setEnabled(enabled)
        # El botón de guardar se controla por self.current_image

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'current_image') and self.current_image:
            self.process_image(self.current_image)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Para que QSettings funcione correctamente en diferentes OS
    app.setOrganizationName(ORG_NAME)
    app.setApplicationName(APP_NAME)
    window = MainWindow()
    sys.exit(app.exec())