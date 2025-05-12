import sys
import os
import requests
import json
import io
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QPushButton, QTextEdit, QLabel,
                               QLineEdit, QMessageBox, QComboBox, QSlider, QFrame,
                               QFileDialog, QProgressBar)
from PySide6.QtCore import Qt, QUrl, QSize, Signal, QObject, QThread
from PySide6.QtGui import QFont, QIcon, QPixmap, QColor, QPalette
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

# Clase para manejar operaciones en segundo plano
class ApiWorker(QObject):
    finished = Signal(object, bool, str) # data, success, error_message
    # progress = Signal(int) # No se usa en ApiWorker actualmente

    def __init__(self, api_key, endpoint, method="GET", data=None):
        super().__init__()
        self.api_key = api_key
        self.endpoint = endpoint
        self.method = method
        self.data = data
        self.is_running = True

    def run(self):
        if not self.is_running: # Podría ser una forma de detenerlo antes de empezar
            self.finished.emit(None, False, "Operación cancelada antes de iniciar.")
            return

        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        try:
            if self.method == "GET":
                response = requests.get(self.endpoint, headers=headers, timeout=30) # Timeout añadido
            elif self.method == "POST":
                response = requests.post(self.endpoint, headers=headers, json=self.data, timeout=30) # Timeout añadido
            
            if not self.is_running: # Comprobar de nuevo por si se canceló durante la petición
                 self.finished.emit(None, False, "Operación cancelada durante la ejecución.")
                 return

            if response.status_code == 200:
                self.finished.emit(response.json() if self.method != "POST" or response.content else response, True, "")
            else:
                self.finished.emit(None, False, f"Error: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e: # Captura errores de red específicos
            self.finished.emit(None, False, f"Error de red: {str(e)}")
        except Exception as e:
            self.finished.emit(None, False, str(e))
        finally:
            self.is_running = False

    def stop(self):
        self.is_running = False


# Clase para manejar la generación de audio en segundo plano
class AudioGenerator(QObject):
    finished = Signal(str, bool, str) # file_path, success, error_message
    progress = Signal(int)
    
    def __init__(self, api_key, voice_id, text, model_id, stability, clarity):
        super().__init__()
        self.api_key = api_key
        self.voice_id = voice_id
        self.text = text
        self.model_id = model_id
        self.stability = stability
        self.clarity = clarity
        self.is_running = True
        
    def run(self):
        if not self.is_running:
            self.finished.emit("", False, "Generación de audio cancelada antes de iniciar.")
            return

        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        data = {
            "text": self.text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": self.stability,
                "similarity_boost": self.clarity
            }
        }
        
        temp_file = ""
        try:
            response = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream",
                headers=headers,
                json=data,
                stream=True,
                timeout=120 # Timeout más largo para generación de audio
            )
            
            if not self.is_running:
                 self.finished.emit("", False, "Generación de audio cancelada durante la petición.")
                 return

            if response.status_code == 200:
                temp_dir = os.path.join(os.path.expanduser("~"), ".elevenlabs_tts")
                if not os.path.exists(temp_dir):
                    os.makedirs(temp_dir)
                
                temp_file = os.path.join(temp_dir, f"temp_audio_{os.urandom(4).hex()}.mp3")
                
                with open(temp_file, "wb") as f:
                    total_size = 0
                    content_length = response.headers.get('content-length')
                    expected_size = int(content_length) if content_length else None
                    
                    for i, chunk in enumerate(response.iter_content(chunk_size=4096)): # Chunk size aumentado
                        if not self.is_running:
                            self.finished.emit(temp_file if os.path.exists(temp_file) else "", False, "Generación de audio cancelada durante la descarga.")
                            return
                        if chunk:
                            f.write(chunk)
                            total_size += len(chunk)
                            if expected_size: # Si conocemos el tamaño total, calculamos el progreso real
                                self.progress.emit(int((total_size / expected_size) * 100))
                            else: # Estimación si no hay content-length (menos preciso)
                                self.progress.emit((i * 5) % 100) # Progreso cíclico simple

                if total_size == 0: # Si el archivo está vacío
                    self.finished.emit(temp_file, False, "Error: Archivo de audio generado está vacío.")
                    return

                self.progress.emit(100) # Asegurar que llega al 100%
                self.finished.emit(temp_file, True, "")
            else:
                self.finished.emit("", False, f"Error al generar audio: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            self.finished.emit(temp_file if temp_file and os.path.exists(temp_file) else "", False, f"Error de red generando audio: {str(e)}")
        except Exception as e:
            self.finished.emit(temp_file if temp_file and os.path.exists(temp_file) else "", False, str(e))
        finally:
            self.is_running = False

    def stop(self):
        self.is_running = False


class ElevenLabsTTS(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("ElevenLabs TTS - Español")
        self.setMinimumSize(800, 650) # Aumentado un poco el alto
        
        self.api_key = ""
        self.voice_id = "21m00Tcm4TlvDq8ikWAM" # ID de voz en español por defecto (Rachel)
        self.voices = {}
        self.models = {} # Cambiado a dict para {display_name: model_id}
        self.current_audio_file = ""
        
        self.worker_thread = None
        self.worker = None # Referencia al worker actual
        
        self.setup_dark_theme()
        
        self.player = QMediaPlayer(self) # Padre asignado
        self.audio_output = QAudioOutput() # QAudioOutput no toma padre, se asocia con setAudioOutput
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.8) # Volumen inicial
        
        self.player.playbackStateChanged.connect(self.handle_playback_state)
        self.player.errorOccurred.connect(self.handle_player_error) # Manejar errores del player
        
        self.setup_ui()
        self.load_saved_api_key()
        
    def setup_dark_theme(self):
        # (El código de setup_dark_theme es largo y no cambia funcionalmente, se omite por brevedad aquí)
        # ... (mismo código que antes para setup_dark_theme) ...
        app = QApplication.instance()
        palette = QPalette()
        background_color = QColor(25, 25, 25)
        text_color = QColor(255, 255, 255)
        accent_color = QColor(0, 122, 204)
        secondary_color = QColor(45, 45, 45)
        palette.setColor(QPalette.Window, background_color)
        palette.setColor(QPalette.WindowText, text_color)
        palette.setColor(QPalette.Base, secondary_color)
        palette.setColor(QPalette.AlternateBase, background_color)
        palette.setColor(QPalette.ToolTipBase, background_color)
        palette.setColor(QPalette.ToolTipText, text_color)
        palette.setColor(QPalette.Text, text_color)
        palette.setColor(QPalette.Button, secondary_color)
        palette.setColor(QPalette.ButtonText, text_color)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, accent_color)
        palette.setColor(QPalette.Highlight, accent_color)
        palette.setColor(QPalette.HighlightedText, Qt.white)
        app.setPalette(palette)
        self.setStyleSheet("""
            QMainWindow { background-color: #191919; }
            QPushButton { background-color: #007ACC; color: white; border: none; border-radius: 4px; padding: 8px 16px; font-weight: bold; }
            QPushButton:hover { background-color: #0095FF; }
            QPushButton:pressed { background-color: #005A9E; }
            QPushButton:disabled { background-color: #444444; color: #999999; }
            QTextEdit, QLineEdit, QComboBox { background-color: #2D2D2D; color: white; border: 1px solid #3D3D3D; border-radius: 4px; padding: 6px; }
            QComboBox::drop-down { border: 0px; }
            QComboBox::down-arrow { image: url(down_arrow.png); width: 12px; height: 12px; } /* Considerar embeber o usar un caracter unicode */
            QSlider::groove:horizontal { border: 1px solid #999999; height: 8px; background: #2D2D2D; margin: 2px 0; border-radius: 4px; }
            QSlider::handle:horizontal { background: #007ACC; border: 1px solid #007ACC; width: 18px; margin: -2px 0; border-radius: 9px; }
            QFrame#line { background-color: #3D3D3D; }
            QLabel { color: white; }
            QProgressBar { border: 1px solid #3D3D3D; border-radius: 4px; text-align: center; background-color: #2D2D2D; color: white;}
            QProgressBar::chunk { background-color: #007ACC; width: 1px; }
        """)

    def setup_ui(self):
        # (El código de setup_ui es largo y no cambia funcionalmente, se omite por brevedad aquí)
        # ... (mismo código que antes para setup_ui) ...
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        api_layout = QVBoxLayout()
        api_title = QLabel("API Key de ElevenLabs")
        api_title.setFont(QFont("Arial", 12, QFont.Bold))
        api_layout.addWidget(api_title)
        api_input_layout = QHBoxLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Introduce tu API key de ElevenLabs")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.connect_button = QPushButton("Conectar")
        self.connect_button.clicked.connect(self.connect_api)
        self.save_key_button = QPushButton("Guardar API Key")
        self.save_key_button.clicked.connect(self.save_api_key)
        self.save_key_button.setEnabled(False)
        api_input_layout.addWidget(self.api_key_input)
        api_input_layout.addWidget(self.connect_button)
        api_input_layout.addWidget(self.save_key_button)
        api_layout.addLayout(api_input_layout)
        main_layout.addLayout(api_layout)
        line = QFrame()
        line.setObjectName("line")
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(line)
        voice_layout = QVBoxLayout()
        voice_header = QHBoxLayout()
        voice_title = QLabel("Seleccionar Voz")
        voice_title.setFont(QFont("Arial", 12, QFont.Bold))
        self.refresh_button = QPushButton("Actualizar Voces")
        self.refresh_button.setFixedWidth(150)
        self.refresh_button.clicked.connect(self.get_voices)
        self.refresh_button.setEnabled(False)
        voice_header.addWidget(voice_title)
        voice_header.addStretch()
        voice_header.addWidget(self.refresh_button)
        voice_layout.addLayout(voice_header)
        self.voice_selector = QComboBox()
        self.voice_selector.setEnabled(False)
        self.voice_selector.currentIndexChanged.connect(self.on_voice_changed)
        voice_layout.addWidget(self.voice_selector)
        model_header = QHBoxLayout()
        model_title = QLabel("Seleccionar Modelo")
        model_title.setFont(QFont("Arial", 12, QFont.Bold))
        self.refresh_models_button = QPushButton("Actualizar Modelos")
        self.refresh_models_button.setFixedWidth(150)
        self.refresh_models_button.clicked.connect(self.get_models)
        self.refresh_models_button.setEnabled(False)
        model_header.addWidget(model_title)
        model_header.addStretch()
        model_header.addWidget(self.refresh_models_button)
        voice_layout.addLayout(model_header)
        self.model_selector = QComboBox()
        self.model_selector.setEnabled(False)
        voice_layout.addWidget(self.model_selector)
        voice_controls = QHBoxLayout()
        stability_layout = QVBoxLayout()
        stability_label = QLabel("Estabilidad")
        self.stability_slider = QSlider(Qt.Horizontal)
        self.stability_slider.setRange(0, 100)
        self.stability_slider.setValue(75) # Default más alto
        self.stability_slider.setTickInterval(10)
        self.stability_slider.setTickPosition(QSlider.TicksBelow)
        self.stability_slider.setEnabled(False)
        self.stability_value = QLabel(f"{self.stability_slider.value()}%")
        self.stability_slider.valueChanged.connect(lambda val: self.stability_value.setText(f"{val}%"))
        stability_layout.addWidget(stability_label)
        stability_layout.addWidget(self.stability_slider)
        stability_layout.addWidget(self.stability_value)
        voice_controls.addLayout(stability_layout)
        clarity_layout = QVBoxLayout()
        clarity_label = QLabel("Claridad + Similaridad") # Nombre más descriptivo
        self.clarity_slider = QSlider(Qt.Horizontal)
        self.clarity_slider.setRange(0, 100)
        self.clarity_slider.setValue(75) # Default más alto
        self.clarity_slider.setTickInterval(10)
        self.clarity_slider.setTickPosition(QSlider.TicksBelow)
        self.clarity_slider.setEnabled(False)
        self.clarity_value = QLabel(f"{self.clarity_slider.value()}%")
        self.clarity_slider.valueChanged.connect(lambda val: self.clarity_value.setText(f"{val}%"))
        clarity_layout.addWidget(clarity_label)
        clarity_layout.addWidget(self.clarity_slider)
        clarity_layout.addWidget(self.clarity_value)
        voice_controls.addLayout(clarity_layout)
        voice_layout.addLayout(voice_controls)
        main_layout.addLayout(voice_layout)
        line2 = QFrame()
        line2.setObjectName("line")
        line2.setFrameShape(QFrame.HLine)
        line2.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(line2)
        tts_layout = QVBoxLayout()
        tts_title = QLabel("Texto a Convertir")
        tts_title.setFont(QFont("Arial", 12, QFont.Bold))
        tts_layout.addWidget(tts_title)
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("Escribe aquí el texto que deseas convertir a voz...")
        self.text_input.setEnabled(False)
        self.text_input.setFixedHeight(100) # Altura fija para el input
        tts_layout.addWidget(self.text_input)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        tts_layout.addWidget(self.progress_bar)
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        self.generate_button = QPushButton("Generar Audio")
        self.generate_button.setMinimumWidth(150)
        self.generate_button.clicked.connect(self.generate_audio)
        self.generate_button.setEnabled(False)
        self.play_button = QPushButton("Reproducir")
        self.play_button.setMinimumWidth(120)
        self.play_button.clicked.connect(self.play_audio)
        self.play_button.setEnabled(False)
        self.stop_button = QPushButton("Detener")
        self.stop_button.setMinimumWidth(120)
        self.stop_button.clicked.connect(self.stop_audio)
        self.stop_button.setEnabled(False)
        self.export_button = QPushButton("Exportar")
        self.export_button.setMinimumWidth(120)
        self.export_button.clicked.connect(self.export_audio)
        self.export_button.setEnabled(False)
        buttons_layout.addWidget(self.generate_button)
        buttons_layout.addWidget(self.play_button)
        buttons_layout.addWidget(self.stop_button)
        buttons_layout.addWidget(self.export_button)
        tts_layout.addLayout(buttons_layout)
        main_layout.addLayout(tts_layout)
        self.statusBar().showMessage("Por favor, introduce tu API key para comenzar.")

    def _start_worker(self, worker_instance, on_finished_slot, on_progress_slot=None):
        if self.worker_thread is not None and self.worker_thread.isRunning():
            QMessageBox.warning(self, "Operación en curso", 
                                "Por favor, espera a que la operación actual termine.")
            return False

        self.worker = worker_instance
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(on_finished_slot)
        if on_progress_slot and hasattr(self.worker, 'progress'):
            self.worker.progress.connect(on_progress_slot)
        
        # Limpieza: cuando el worker termina, se pide al hilo que termine.
        # Cuando el hilo termina, se programan para borrarse a sí mismos.
        # Y también limpiamos nuestras referencias en la clase principal.
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(self._clear_worker_references) # Limpiar self.worker y self.worker_thread

        self.worker_thread.start()
        return True

    def _clear_worker_references(self):
        print("Limpiando referencias de worker y worker_thread.")
        self.worker = None
        self.worker_thread = None
        # Habilitar botones generales si es necesario, pero es mejor hacerlo en los callbacks específicos
        self.connect_button.setEnabled(True) # Por ejemplo, el botón de conectar siempre se podría re-habilitar
        if self.api_key: # Si hay API key, los botones de actualizar deberían estar activos
            self.refresh_button.setEnabled(True)
            self.refresh_models_button.setEnabled(True)


    def load_saved_api_key(self):
        try:
            config_dir = os.path.join(os.path.expanduser("~"), ".elevenlabs_tts")
            config_file = os.path.join(config_dir, "config.json")
            
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    if "api_key" in config and config["api_key"]:
                        self.api_key_input.setText(config["api_key"])
                        self.statusBar().showMessage("API key cargada. Pulsa Conectar para iniciar.")
                        # No conectar automáticamente, esperar al usuario
        except Exception as e:
            self.statusBar().showMessage(f"No se pudo cargar la configuración: {str(e)}")
    
    def save_api_key(self):
        current_key = self.api_key_input.text().strip()
        if not current_key:
            QMessageBox.warning(self, "API Key Vacía", "No se puede guardar una API key vacía.")
            return
        if not self.api_key or current_key != self.api_key:
             QMessageBox.warning(self, "API Key Diferente", "La API Key ingresada es diferente a la conectada. Conecta primero con la nueva API Key para guardarla.")
             return

        try:
            config_dir = os.path.join(os.path.expanduser("~"), ".elevenlabs_tts")
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
            
            config_file = os.path.join(config_dir, "config.json")
            config = {"api_key": self.api_key} # Guardar la API key activa (self.api_key)
            
            with open(config_file, 'w') as f:
                json.dump(config, f)
            
            self.statusBar().showMessage("API key guardada correctamente.")
            QMessageBox.information(self, "Configuración Guardada", "Tu API key ha sido guardada para uso futuro.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo guardar la API key: {str(e)}")

    def on_voice_changed(self, index):
        if index >= 0 and self.voice_selector.count() > 0:
            voice_name = self.voice_selector.currentText()
            # self.voices es {name: id}, así que esto es correcto
            self.voice_id = self.voices.get(voice_name, self.voice_id) 
            print(f"Voz cambiada a: {voice_name} (ID: {self.voice_id})")

    def connect_api(self):
        api_key_from_input = self.api_key_input.text().strip()
        if not api_key_from_input:
            QMessageBox.warning(self, "Error de API", "Por favor, introduce una API key válida.")
            return
        
        self.connect_button.setEnabled(False) # Deshabilitar botón mientras se conecta
        self.statusBar().showMessage("Conectando a ElevenLabs...")
        
        worker = ApiWorker(api_key_from_input, "https://api.elevenlabs.io/v1/user")
        if not self._start_worker(worker, self.on_connect_finished):
            self.connect_button.setEnabled(True) # Re-habilitar si no se pudo iniciar el worker

    def on_connect_finished(self, data, success, error_msg):
        if success:
            self.api_key = self.api_key_input.text().strip() # Guardar la API key validada
            self.statusBar().showMessage("Conexión exitosa!")
            self.refresh_button.setEnabled(True)
            self.refresh_models_button.setEnabled(True)
            self.voice_selector.setEnabled(True)
            self.model_selector.setEnabled(True)
            self.text_input.setEnabled(True)
            self.stability_slider.setEnabled(True)
            self.clarity_slider.setEnabled(True)
            self.save_key_button.setEnabled(True) # Habilitar guardado de API key
            
            self.get_voices()
            self.get_models()
        else:
            QMessageBox.warning(self, "Error de API", f"Error al conectar: {error_msg}")
            self.statusBar().showMessage("Error de conexión. Verifica tu API key e inténtalo de nuevo.")
        
        # El botón connect se re-habilita en _clear_worker_references o si _start_worker falla
        # Si la conexión falló aquí, pero el worker terminó, _clear_worker_references lo habilitará.
        # Si _start_worker falló (otro worker activo), ya se habrá re-habilitado.

    def get_voices(self):
        if not self.api_key:
            QMessageBox.information(self, "API Key Requerida", "Por favor, conecta con una API key primero.")
            return
        
        self.refresh_button.setEnabled(False)
        self.statusBar().showMessage("Obteniendo voces disponibles...")
        
        worker = ApiWorker(self.api_key, "https://api.elevenlabs.io/v1/voices")
        if not self._start_worker(worker, self.on_get_voices_finished):
             self.refresh_button.setEnabled(True) # Re-habilitar si no se pudo iniciar

    def on_get_voices_finished(self, data, success, error_msg):
        if success:
            self.voice_selector.clear()
            self.voices = {} # Limpiar
            
            for voice in data.get("voices", []):
                self.voices[voice["name"]] = voice["voice_id"]
                self.voice_selector.addItem(voice["name"])
            
            if self.voice_selector.count() > 0:
                # Intentar seleccionar la voz por defecto si existe, sino la primera
                default_voice_name = next((name for name, v_id in self.voices.items() if v_id == "21m00Tcm4TlvDq8ikWAM"), None)
                if default_voice_name:
                    self.voice_selector.setCurrentText(default_voice_name)
                else:
                    self.voice_selector.setCurrentIndex(0) # Sino, la primera que encuentre
                self.voice_id = self.voices[self.voice_selector.currentText()]
                self.generate_button.setEnabled(True)
                self.statusBar().showMessage(f"Voces cargadas. Voz actual: {self.voice_selector.currentText()}")
            else:
                self.statusBar().showMessage("No se encontraron voces disponibles.")
        else:
            QMessageBox.warning(self, "Error", f"Error al obtener voces: {error_msg}")
            self.statusBar().showMessage("Error al obtener voces.")
        
        if self.api_key: # Solo re-habilitar si la API key sigue siendo válida
            self.refresh_button.setEnabled(True)


    def get_models(self):
        if not self.api_key:
            QMessageBox.information(self, "API Key Requerida", "Por favor, conecta con una API key primero.")
            return

        self.refresh_models_button.setEnabled(False)
        self.statusBar().showMessage("Obteniendo modelos disponibles...")

        worker = ApiWorker(self.api_key, "https://api.elevenlabs.io/v1/models")
        if not self._start_worker(worker, self.on_get_models_finished):
            self.refresh_models_button.setEnabled(True)

    def on_get_models_finished(self, data, success, error_msg):
        if success:
            self.model_selector.clear()
            self.models = {} # Limpiar {display_name: model_id}
            
            # Modelo multilingüe v2 suele ser una buena opción por defecto
            default_model_id_target = "eleven_multilingual_v2"
            selected_model_index = 0
            found_default = False

            for i, model_data in enumerate(data): # 'data' es una lista de modelos
                # Filtrar solo modelos que pueden usarse para TTS y están disponibles
                if model_data.get("can_be_finetuned") == False and \
                   model_data.get("can_do_text_to_speech") == True and \
                   model_data.get("servable_at_peak_times", True): # Considerar si es servible

                    display_name = f"{model_data['name']} (ID: ...{model_data['model_id'][-6:]})"
                    self.models[display_name] = model_data["model_id"]
                    self.model_selector.addItem(display_name)
                    if model_data["model_id"] == default_model_id_target:
                        selected_model_index = self.model_selector.count() -1 # El índice del que acabamos de añadir
                        found_default = True
            
            if self.model_selector.count() > 0:
                self.model_selector.setCurrentIndex(selected_model_index if found_default else 0)
                self.statusBar().showMessage(f"Modelos cargados. Modelo actual: {self.model_selector.currentText().split(' (ID:')[0]}")
            else:
                self.statusBar().showMessage("No se encontraron modelos TTS disponibles.")
        else:
            QMessageBox.warning(self, "Error", f"Error al obtener modelos: {error_msg}")
            self.statusBar().showMessage("Error al obtener modelos.")

        if self.api_key:
            self.refresh_models_button.setEnabled(True)


    def generate_audio(self):
        text = self.text_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Texto Vacío", "Por favor, introduce un texto para convertir.")
            return
        if not self.api_key:
            QMessageBox.warning(self, "API Key Requerida", "API key no válida o no conectada.")
            return
        if self.voice_selector.currentIndex() < 0 or self.model_selector.currentIndex() < 0:
            QMessageBox.warning(self, "Selección Requerida", "Por favor, selecciona una voz y un modelo.")
            return

        current_voice_name = self.voice_selector.currentText()
        voice_id_to_use = self.voices.get(current_voice_name)
        if not voice_id_to_use:
            QMessageBox.critical(self, "Error de Voz", f"No se pudo encontrar el ID para la voz: {current_voice_name}")
            return
            
        current_model_display_name = self.model_selector.currentText()
        model_id_to_use = self.models.get(current_model_display_name)
        if not model_id_to_use:
            QMessageBox.critical(self, "Error de Modelo", f"No se pudo encontrar el ID para el modelo: {current_model_display_name}")
            return

        stability = self.stability_slider.value() / 100.0
        clarity = self.clarity_slider.value() / 100.0
        
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.generate_button.setEnabled(False)
        self.play_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.statusBar().showMessage("Generando audio...")
        
        worker = AudioGenerator(self.api_key, voice_id_to_use, text, model_id_to_use, stability, clarity)
        if not self._start_worker(worker, self.on_audio_generated, self.update_progress):
            self.generate_button.setEnabled(True) # Re-habilitar si no se pudo iniciar el worker
            self.progress_bar.setVisible(False)


    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def on_audio_generated(self, file_path, success, error_msg):
        self.progress_bar.setVisible(False)
        if success and file_path and os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            self.current_audio_file = file_path
            try:
                self.player.setSource(QUrl.fromLocalFile(file_path)) # Cargar para reproducción
                self.play_button.setEnabled(True)
                self.export_button.setEnabled(True)
                model_name_short = self.model_selector.currentText().split(" (ID:")[0]
                voice_name_short = self.voice_selector.currentText()
                self.statusBar().showMessage(f"Audio generado con {model_name_short} y voz {voice_name_short}.")
            except Exception as e:
                 QMessageBox.critical(self, "Error de Reproductor", f"Error al cargar audio en reproductor: {str(e)}\nArchivo: {file_path}")
                 self.statusBar().showMessage("Error al cargar audio generado.")
        else:
            QMessageBox.warning(self, "Error de Generación", error_msg or "Fallo desconocido al generar audio.")
            self.statusBar().showMessage(f"Error al generar audio: {error_msg}")
            if file_path and os.path.exists(file_path): # Si el archivo existe pero hubo error, borrarlo
                try:
                    os.remove(file_path)
                except OSError as e:
                    print(f"No se pudo borrar el archivo temporal {file_path}: {e}")

        self.generate_button.setEnabled(True) # Re-habilitar después de la operación

    def play_audio(self):
        if not self.current_audio_file or not os.path.exists(self.current_audio_file):
            QMessageBox.warning(self, "Archivo no Encontrado", "No hay un audio disponible para reproducir o el archivo no existe.")
            return
        
        if self.player.source().isEmpty() or self.player.source().toLocalFile() != self.current_audio_file:
            print(f"Fuente del reproductor no coincide o está vacía. Recargando: {self.current_audio_file}")
            self.player.setSource(QUrl.fromLocalFile(self.current_audio_file))

        if self.player.mediaStatus() == QMediaPlayer.MediaStatus.NoMedia or \
           self.player.mediaStatus() == QMediaPlayer.MediaStatus.InvalidMedia:
            QMessageBox.warning(self, "Error de Media", "No se puede reproducir el archivo de audio. Puede estar corrupto o no ser soportado.")
            self.player.setSource(QUrl()) # Limpiar la fuente
            return

        print(f"Reproduciendo: {self.current_audio_file}, Estado: {self.player.playbackState()}")
        self.player.play()
        # Los botones se manejan en handle_playback_state

    def stop_audio(self):
        self.player.stop()
        # Los botones se manejan en handle_playback_state

    def handle_playback_state(self, state):
        print(f"Playback state changed: {state}")
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.statusBar().showMessage("Reproduciendo audio...")
        elif state == QMediaPlayer.PlaybackState.StoppedState:
            self.play_button.setEnabled(True if self.current_audio_file else False)
            self.stop_button.setEnabled(False)
            self.statusBar().showMessage("Reproducción detenida/finalizada.")
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self.play_button.setEnabled(True)
            self.stop_button.setEnabled(False) # O true si quieres un botón "Resume" vs "Play"
            self.statusBar().showMessage("Audio pausado.")
            
    def handle_player_error(self, error, error_string=""): # Añadido error_string para compatibilidad
        error_map = {
            QMediaPlayer.Error.NoError: "No Error",
            QMediaPlayer.Error.ResourceError: "Resource Error",
            QMediaPlayer.Error.FormatError: "Format Error",
            QMediaPlayer.Error.NetworkError: "Network Error",
            QMediaPlayer.Error.AccessDeniedError: "Access Denied Error",
            QMediaPlayer.Error.ServiceMissingError: "Service Missing Error",
            QMediaPlayer.Error.MediaIsPlaylist: "Media Is Playlist (Not supported)"
        }
        # error_string puede ser provisto por algunas versiones/backends de Qt
        msg = error_string if error_string else f"Error del reproductor: {error_map.get(error, 'Error desconocido')}"
        QMessageBox.critical(self, "Error de Reproducción", msg)
        self.statusBar().showMessage(f"Error de reproducción: {msg}")
        self.play_button.setEnabled(True if self.current_audio_file else False)
        self.stop_button.setEnabled(False)
        self.player.setSource(QUrl()) # Limpiar la fuente en error severo

    def export_audio(self):
        if not self.current_audio_file or not os.path.exists(self.current_audio_file):
            QMessageBox.warning(self, "Archivo no Encontrado", "No hay un audio disponible para exportar.")
            return
        
        voice_name = self.voice_selector.currentText().replace(" ", "_").replace("(", "").replace(")", "")
        model_name = self.model_selector.currentText().split(" (ID:")[0].replace(" ", "_")
        default_filename = f"ElevenLabs_{voice_name}_{model_name}.mp3"
        
        # Directorio por defecto para guardar (Mis Documentos/Audio)
        default_save_dir = os.path.join(os.path.expanduser("~"), "Documents", "Audio ElevenLabs")
        if not os.path.exists(default_save_dir):
            try:
                os.makedirs(default_save_dir)
            except OSError:
                default_save_dir = os.path.expanduser("~") # Fallback al home

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar Audio",
            os.path.join(default_save_dir, default_filename),
            "Archivos de Audio (*.mp3)"
        )
        
        if file_path:
            try:
                # Usar shutil.copy para metadatos si es posible, o simple copia binaria
                import shutil
                shutil.copy(self.current_audio_file, file_path)
                self.statusBar().showMessage(f"Audio guardado en: {file_path}")
                QMessageBox.information(self, "Éxito", f"Audio exportado correctamente a:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error de Exportación", f"No se pudo exportar el audio: {str(e)}")
                self.statusBar().showMessage("Error al exportar el audio.")

    def closeEvent(self, event):
        print("Iniciando cierre de la aplicación...")
        self.player.stop() # Detener cualquier reproducción
        
        # Intentar detener el worker y el hilo de forma controlada
        if self.worker_thread is not None and self.worker_thread.isRunning():
            print(f"Intentando detener el hilo de trabajo: {self.worker_thread}")
            if self.worker and hasattr(self.worker, 'stop'):
                self.worker.stop() # Señalizar al worker que debe detenerse

            # Desconectar señales para evitar callbacks a objetos que podrían estar destruyéndose
            try:
                if self.worker:
                    self.worker.finished.disconnect()
                if hasattr(self.worker, 'progress'):
                     self.worker.progress.disconnect()
                self.worker_thread.started.disconnect()
                self.worker_thread.finished.disconnect() # Desconectar todos los slots de 'finished'
            except RuntimeError: # 'disconnect' puede fallar si no hay conexiones
                pass
            except AttributeError: # Si self.worker o thread ya no existen
                pass

            self.worker_thread.quit() # Pedir al bucle de eventos del hilo que termine
            if not self.worker_thread.wait(3000): # Esperar hasta 3 segundos
                print("El hilo de trabajo no respondió a quit(), terminando forzosamente...")
                self.worker_thread.terminate() # Último recurso (puede ser inestable)
                self.worker_thread.wait(1000) # Esperar a la terminación
            print("Hilo de trabajo detenido.")
        else:
            print("No hay hilo de trabajo activo o ya está detenido.")
            
        # Eliminar archivo temporal si existe
        if self.current_audio_file and os.path.exists(self.current_audio_file) and "temp_audio" in self.current_audio_file:
            try:
                print(f"Eliminando archivo de audio temporal: {self.current_audio_file}")
                os.remove(self.current_audio_file)
            except OSError as e:
                print(f"Error al eliminar el archivo temporal {self.current_audio_file}: {e}")

        print("Cierre de aplicación completado.")
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Podrías establecer aquí algunos atributos globales de Qt si es necesario
    # Por ejemplo, para el manejo de DPI alto:
    # QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    # QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    
    window = ElevenLabsTTS()
    window.show()
    sys.exit(app.exec())