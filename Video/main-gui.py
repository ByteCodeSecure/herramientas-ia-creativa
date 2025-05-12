import sys
import time
import json
import requests # Import the requests library for actual API calls
import os # Needed for saving files

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QStatusBar, QMessageBox,
    QFileDialog, QSizePolicy, QSpinBox
)
from PySide6.QtGui import QPalette, QColor, QFont, QDesktopServices
from PySide6.QtCore import Qt, Slot, Signal, QThread, QUrl

# --- Actual Novita.ai API Client ---
NOVITA_API_BASE_URL = "https://api.novita.ai/v3/async" # Base URL for async tasks

class NovitaApiClient:
    """
    Cliente para interactuar con la API asíncrona de Novita.ai (wan-i2v).
    Usa la librería 'requests' para las llamadas HTTP reales.
    """
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def check_api_status(self):
        """
        Verifica el estado de la API o la validez de la clave
        haciendo una llamada a un endpoint ligero si existe,
        o simulando basado en la respuesta de un endpoint común.
        Nota: Novita.ai podría no tener un endpoint de "status" directo.
        Podemos intentar un endpoint de listado de modelos o similar si la documentación lo indica.
        Por ahora, simularemos la verificación, pero una implementación real
        debería verificar una llamada API que requiera autenticación.
        """
        if not self.api_key:
            return False, "API Key no proporcionada."

        # Intentar una llamada real a un endpoint simple para verificar la clave.
        # El endpoint /v1/models es un ejemplo que podría funcionar si requiere autenticación.
        # Consulta la documentación más reciente de Novita.ai para el endpoint correcto.
        test_url = "https://api.novita.ai/v2/models" # Usando un endpoint v2 como ejemplo para verificación
        # Nota: La API v3 async es para tareas, la verificación puede estar en v1 o v2.
        # AJUSTAR ESTA URL segun la documentación real de Novita.ai para verificar keys.

        try:
            response = requests.get(test_url, headers={"Authorization": f"Bearer {self.api_key}"}, timeout=10)

            if response.status_code == 200:
                 # Asumimos que un 200 OK en un endpoint que requiere autenticación
                 # significa que la clave es válida.
                 return True, "API Key válida."
            elif response.status_code == 401:
                 return False, "API Key inválida o no autorizada."
            else:
                 # Otros códigos de error pueden indicar problemas con el servicio o la clave.
                 return False, f"Error al verificar API: Código {response.status_code} - {response.text}"
        except requests.exceptions.RequestException as e:
             return False, f"Error de conexión al verificar API: {e}"
        except Exception as e:
             return False, f"Ocurrió un error inesperado durante la verificación: {e}"


    def start_image_to_video_task(self, image_url: str, prompt: str, width: int, height: int, seed: int):
        """
        Inicia la tarea de generación de video de imagen a video.
        Retorna el ID de la tarea y un mensaje, o None y un mensaje de error.
        """
        if not self.api_key:
            return None, "API Key no proporcionada.", None
        if not image_url:
            return None, "La URL de la imagen no puede estar vacía.", None
        if not prompt:
            return None, "El prompt no puede estar vacío.", None

        endpoint = f"{NOVITA_API_BASE_URL}/wan-i2v"
        payload = {
            "model_name": "wan2.1-i2v", # Ajusta si usas otro modelo wan-i2v
            "image_url": image_url,
            "width": width,
            "height": height,
            "seed": seed,
            "prompt": prompt
        }

        try:
            response = requests.post(endpoint, headers=self.headers, json=payload, timeout=30) # Aumentar timeout para el inicio

            if response.status_code == 200:
                data = response.json()
                task_id = data.get("task_id")
                if task_id:
                    return task_id, "Tarea de generación iniciada.", data # Devolver task_id y datos completos
                else:
                    return None, f"Error: La API no devolvió un task_id válido. Respuesta: {data}", data
            else:
                return None, f"Error al iniciar tarea: Código {response.status_code} - {response.text}", response.json() if response.text else None
        except requests.exceptions.RequestException as e:
            return None, f"Error de conexión al iniciar tarea: {e}", None
        except Exception as e:
             return None, f"Ocurrió un error inesperado al iniciar la tarea: {e}", None


    def get_task_result(self, task_id: str):
        """
        Consulta el estado y el resultado de una tarea asíncrona.
        Retorna el estado, el resultado (con video_url si está completada)
        y un mensaje, o None y un mensaje de error si falla la consulta.
        """
        if not self.api_key:
            return "failed", None, "API Key no proporcionada."
        if not task_id:
            return "failed", None, "Task ID no proporcionado."

        endpoint = f"{NOVITA_API_BASE_URL}/task-result?task_id={task_id}"

        try:
            # El polling no necesita un timeout muy largo
            response = requests.get(endpoint, headers=self.headers, timeout=15)

            if response.status_code == 200:
                data = response.json()
                # La estructura de la respuesta de /task-result puede variar.
                # Basado en la documentación general de Novita async, esperamos 'task'.
                # Verificamos el 'status' dentro de 'task'.
                task_data = data.get("task", {})
                status = task_data.get("status", "unknown")
                result = task_data.get("result", {}) # El resultado debería estar aquí si está completado
                error_message = task_data.get("error_message") # Si hay un error

                if status == "completed":
                     video_url = result.get("video_url") # Buscar la URL del video
                     if video_url:
                          return status, result, "Tarea completada exitosamente."
                     else:
                          return "failed", result, "Tarea completada, pero no se encontró la URL del video en el resultado."
                elif status == "failed":
                     return status, result, f"Tarea fallida: {error_message or 'Motivo desconocido'}"
                else: # pending, processing, etc.
                     return status, result, f"Estado de la tarea: {status}..."

            else:
                return "failed", None, f"Error al consultar estado de tarea {task_id}: Código {response.status_code} - {response.text}"
        except requests.exceptions.RequestException as e:
            return "failed", None, f"Error de conexión al consultar estado de tarea {task_id}: {e}"
        except Exception as e:
             return "failed", None, f"Ocurrió un error inesperado al consultar el estado de la tarea {task_id}: {e}"

# --- Thread para el Polling Asíncrono ---
class VideoTaskWorker(QThread):
    """Hilo de trabajo para consultar periódicamente el estado de la tarea API."""
    task_status_updated = Signal(str) # Señal para enviar actualizaciones de estado
    task_completed = Signal(str)      # Señal para enviar la URL del video al completar
    task_failed = Signal(str)         # Señal para enviar el mensaje de error al fallar

    def __init__(self, api_client: NovitaApiClient, task_id: str):
        super().__init__()
        self.api_client = api_client
        self.task_id = task_id
        self._is_running = True

    def run(self):
        """Método principal del hilo, realiza el polling."""
        polling_interval = 5 # Segundos entre consultas
        max_polls = 120 # Número máximo de intentos (ej: 10 minutos con 5s intervalo)
        poll_count = 0

        self.task_status_updated.emit(f"Iniciando monitoreo de tarea: {self.task_id}")

        while self._is_running and poll_count < max_polls:
            time.sleep(polling_interval)
            poll_count += 1

            status, result, message = self.api_client.get_task_result(self.task_id)

            self.task_status_updated.emit(f"Tarea {self.task_id[:8]}... - {message}")

            if status == "completed":
                video_url = result.get("video_url")
                if video_url:
                    self.task_completed.emit(video_url)
                else:
                    self.task_failed.emit("La tarea completó pero no se encontró URL de video.")
                self._is_running = False # Terminar hilo
            elif status == "failed":
                self.task_failed.emit(message)
                self._is_running = False # Terminar hilo
            # Si es pending, processing, etc., el bucle continúa

        if self._is_running: # Si salió del bucle por max_polls
            self.task_failed.emit(f"Tiempo de espera agotado. La tarea {self.task_id[:8]}... podría seguir procesando.")

    def stop(self):
        """Método para detener el hilo externamente."""
        self._is_running = False
        self.wait() # Esperar a que el hilo termine su ejecución actual

# --- Paleta de Colores y Estilos (sin cambios, se ve bien) ---
class ModernDarkPalette(QPalette):
    """Paleta de colores oscuros y modernos."""
    def __init__(self):
        super().__init__()
        self.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        self.setColor(QPalette.ColorRole.WindowText, QColor(230, 230, 230))
        self.setColor(QPalette.ColorRole.Base, QColor(42, 42, 42))
        self.setColor(QPalette.ColorRole.AlternateBase, QColor(66, 66, 66))
        self.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 220))
        self.setColor(QPalette.ColorRole.ToolTipText, QColor(0, 0, 0))
        self.setColor(QPalette.ColorRole.Text, QColor(230, 230, 230))
        self.setColor(QPalette.ColorRole.Button, QColor(75, 75, 75))
        self.setColor(QPalette.ColorRole.ButtonText, QColor(230, 230, 230))
        self.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
        self.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        self.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        self.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))

        self.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(128,128,128))
        self.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(128,128,128))
        self.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(128,128,128))

class NovitaVideoGeneratorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.novita_client = None
        self.api_key = ""
        self.current_task_id = None
        self.video_task_worker = None
        self.last_video_url = None # Para almacenar la URL del último video generado

        self.init_ui()
        self.apply_styles()

    def init_ui(self):
        self.setWindowTitle("Novita.ai Image-to-Video (wan-i2v)")
        self.setGeometry(100, 100, 800, 600) # Aumentar tamaño

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # --- Sección de API Key ---
        api_key_layout = QHBoxLayout()
        api_key_layout.addWidget(QLabel("Novita.ai API Key:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Ingresa tu API Key")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_key_layout.addWidget(self.api_key_input, 1) # Estirar campo de texto
        self.check_api_button = QPushButton("Verificar y Guardar")
        self.check_api_button.clicked.connect(self.check_and_save_api_key)
        api_key_layout.addWidget(self.check_api_button)
        main_layout.addLayout(api_key_layout)

        # --- Sección de Entrada (Imagen, Prompt, Parámetros) ---
        input_group_layout = QVBoxLayout()
        input_group_layout.setSpacing(10)

        # Image URL
        image_url_layout = QHBoxLayout()
        image_url_layout.addWidget(QLabel("Image URL:"))
        self.image_url_input = QLineEdit()
        self.image_url_input.setPlaceholderText("Ej: https://example.com/my_image.jpg")
        image_url_layout.addWidget(self.image_url_input, 1)
        input_group_layout.addLayout(image_url_layout)

        # Prompt
        input_group_layout.addWidget(QLabel("Prompt:"))
        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("Ej: Un panda caminando lentamente en un pastizal.")
        self.prompt_input.setMinimumHeight(80)
        self.prompt_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed) # Altura fija, ancho expandible
        input_group_layout.addWidget(self.prompt_input)

        # Parameters (Width, Height, Seed)
        params_layout = QHBoxLayout()
        params_layout.addWidget(QLabel("Width:"))
        self.width_input = QSpinBox()
        self.width_input.setRange(1, 2048) # Ajusta rangos según API docs
        self.width_input.setValue(1280) # Valor por defecto
        params_layout.addWidget(self.width_input)

        params_layout.addWidget(QLabel("Height:"))
        self.height_input = QSpinBox()
        self.height_input.setRange(1, 2048) # Ajusta rangos según API docs
        self.height_input.setValue(720) # Valor por defecto
        params_layout.addWidget(self.height_input)

        params_layout.addWidget(QLabel("Seed (-1 for random):"))
        self.seed_input = QSpinBox()
        self.seed_input.setRange(-1, 999999999) # Rango amplio para seed
        self.seed_input.setValue(-1)
        params_layout.addWidget(self.seed_input)

        params_layout.addStretch(1) # Empujar widgets a la izquierda
        input_group_layout.addLayout(params_layout)

        main_layout.addLayout(input_group_layout)


        # --- Botón de Generación ---
        self.generate_button = QPushButton("Generar Video")
        self.generate_button.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        self.generate_button.setFixedHeight(40)
        self.generate_button.clicked.connect(self.start_video_generation)
        self.generate_button.setEnabled(False) # Deshabilitado hasta que la API Key sea válida
        main_layout.addWidget(self.generate_button)

        # --- Área de Resultados/Estado ---
        result_label = QLabel("Estado / Resultado:")
        main_layout.addWidget(result_label)

        self.result_output = QTextEdit()
        self.result_output.setReadOnly(True)
        self.result_output.setFont(QFont("Monospace", 9))
        self.result_output.setMinimumHeight(100)
        main_layout.addWidget(self.result_output)

        # --- Botones de Video ---
        video_buttons_layout = QHBoxLayout()
        self.open_video_button = QPushButton("Abrir Video en Navegador")
        self.open_video_button.clicked.connect(self.open_video_url)
        self.open_video_button.setEnabled(False)
        video_buttons_layout.addWidget(self.open_video_button)

        self.save_video_button = QPushButton("Exportar/Guardar Video")
        self.save_video_button.clicked.connect(self.save_video_file)
        self.save_video_button.setEnabled(False)
        video_buttons_layout.addWidget(self.save_video_button)

        video_buttons_layout.addStretch(1) # Empujar botones a la izquierda
        main_layout.addLayout(video_buttons_layout)


        # --- Barra de Estado ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Listo. Ingresa y verifica tu API Key.")

        # Aplicar estilos a los SpinBoxes (no cubiertos por el QSS general de QLineEdit)
        self.width_input.setStyleSheet("""
            QSpinBox {
                background-color: #2A2A2A;
                color: #E6E6E6;
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 4px; /* Menos padding que QLineEdit/QTextEdit */
            }
            QSpinBox:focus {
                 border: 1px solid #2A82DA;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 16px; /* Ancho de los botones */
                border-left: 1px solid #555555;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                 background-color: #5A5A5A;
            }
        """)
        self.height_input.setStyleSheet(self.width_input.styleSheet())
        self.seed_input.setStyleSheet(self.width_input.styleSheet())


    def apply_styles(self):
        """Aplica la paleta oscura y estilos QSS."""
        self.setPalette(ModernDarkPalette())

        self.setStyleSheet("""
            QMainWindow {
                background-color: #353535;
            }
            QLabel {
                color: #E6E6E6;
                font-size: 10pt;
            }
            QLineEdit, QTextEdit {
                background-color: #2A2A2A;
                color: #E6E6E6;
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 8px;
                font-size: 10pt;
            }
            QLineEdit:focus, QTextEdit:focus {
                border: 1px solid #2A82DA;
            }
            QPushButton {
                background-color: #4A4A4A;
                color: #E6E6E6;
                border: 1px solid #606060;
                border-radius: 5px;
                padding: 8px 15px;
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5A5A5A;
                border: 1px solid #707070;
            }
            QPushButton:pressed {
                background-color: #3A3A3A;
            }
            QPushButton:disabled {
                background-color: #404040;
                color: #808080;
                border: 1px solid #505050; /* Borde más suave para deshabilitado */
            }
             QStatusBar {
                color: #E6E6E6;
                font-size: 9pt;
                background-color: #4A4A4A; /* Fondo para la barra de estado */
             }
             QStatusBar::item {
                 border: none; /* Evita bordes extraños en los items de la barra de estado */
             }
        """)


    @Slot()
    def check_and_save_api_key(self):
        """Verifica la API Key ingresada y la guarda si es válida."""
        current_key = self.api_key_input.text().strip()
        if not current_key:
            QMessageBox.warning(self, "API Key Vacía", "Por favor, ingresa tu API Key de Novita.ai.")
            self.status_bar.showMessage("Error: API Key no ingresada.", 5000)
            self.api_key_input.setStyleSheet("") # Reset style
            return

        self.status_bar.showMessage("Verificando API Key...")
        self.result_output.setText("Verificando API Key...")
        self.check_api_button.setEnabled(False) # Deshabilitar durante verificación
        QApplication.processEvents() # Asegura que la UI se actualice

        # Usar el cliente real para verificar
        temp_client = NovitaApiClient(current_key)
        is_valid, message = temp_client.check_api_status()

        if is_valid:
            self.api_key = current_key
            self.novita_client = NovitaApiClient(self.api_key) # Crear cliente principal
            self.status_bar.showMessage(message, 10000)
            self.result_output.setText(f"API Key guardada y verificada: {message}")
            self.generate_button.setEnabled(True)
            self.api_key_input.setStyleSheet("border: 1px solid green;") # Feedback visual
            QMessageBox.information(self, "API Key Verificada", message)
        else:
            self.status_bar.showMessage(f"Error de API Key: {message}", 10000)
            self.result_output.setText(f"Error al verificar API Key:\n{message}")
            self.generate_button.setEnabled(False)
            self.api_key_input.setStyleSheet("border: 1px solid red;") # Feedback visual
            QMessageBox.critical(self, "Error de API Key", message)
            self.novita_client = None # Asegurarse de que no hay cliente si la clave es inválida

        self.check_api_button.setEnabled(True) # Re-habilitar botón


    @Slot()
    def start_video_generation(self):
        """Inicia el proceso de generación de video (POST request)."""
        if not self.novita_client:
            QMessageBox.warning(self, "API no lista", "Por favor, verifica tu API Key primero.")
            self.status_bar.showMessage("Error: API Key no verificada.", 5000)
            return

        image_url = self.image_url_input.text().strip()
        prompt_text = self.prompt_input.toPlainText().strip()
        width = self.width_input.value()
        height = self.height_input.value()
        seed = self.seed_input.value()

        if not image_url:
             QMessageBox.warning(self, "Image URL Vacía", "Por favor, ingresa la URL de la imagen.")
             self.status_bar.showMessage("Error: Image URL vacía.", 5000)
             return
        if not prompt_text:
            QMessageBox.warning(self, "Prompt Vacío", "Por favor, ingresa un prompt para generar el video.")
            self.status_bar.showMessage("Error: Prompt vacío.", 5000)
            return

        # Deshabilitar controles de entrada y botón de generación durante el proceso
        self.generate_button.setEnabled(False)
        self.image_url_input.setEnabled(False)
        self.prompt_input.setEnabled(False)
        self.width_input.setEnabled(False)
        self.height_input.setEnabled(False)
        self.seed_input.setEnabled(False)
        self.open_video_button.setEnabled(False)
        self.save_video_button.setEnabled(False)
        self.last_video_url = None # Limpiar URL anterior

        self.status_bar.showMessage("Enviando solicitud de generación de video...")
        self.result_output.setText(f"Iniciando tarea para generar video de:\nImagen: {image_url}\nPrompt: \"{prompt_text[:50]}...\"")
        QApplication.processEvents()

        # Iniciar la tarea de generación (esto no bloquea el GUI porque la llamada requests es síncrona
        # en este método, pero es rápida). El polling posterior se hará en otro hilo.
        task_id, message, api_data = self.novita_client.start_image_to_video_task(image_url, prompt_text, width, height, seed)

        if task_id:
            self.current_task_id = task_id
            self.status_bar.showMessage(f"Tarea iniciada. ID: {task_id[:8]}... Monitoreando estado...")
            self.result_output.setText(f"Tarea iniciada exitosamente.\nID de Tarea: {task_id}\n{message}")
            # Ahora iniciamos el hilo para el polling
            self.video_task_worker = VideoTaskWorker(self.novita_client, task_id)
            self.video_task_worker.task_status_updated.connect(self.update_status_output)
            self.video_task_worker.task_completed.connect(self.on_task_completed)
            self.video_task_worker.task_failed.connect(self.on_task_failed)
            self.video_task_worker.start() # Inicia la ejecución del hilo
        else:
            # La solicitud para iniciar la tarea falló
            self.status_bar.showMessage(f"Error al iniciar tarea: {message}", 15000)
            self.result_output.setText(f"Error al iniciar tarea:\n{message}\nAPI Response Data: {api_data}")
            # Re-habilitar controles si la tarea no pudo iniciar
            self.enable_input_controls()


    @Slot(str)
    def update_status_output(self, message):
        """Actualiza el área de resultado con mensajes de estado del worker."""
        # Agregar el mensaje en lugar de reemplazar si quieres un log de estados
        # self.result_output.append(message)
        # O reemplazar para mostrar solo el último estado
        self.result_output.setText(message)
        self.status_bar.showMessage(message, 5000) # Mostrar también en la barra de estado

    @Slot(str)
    def on_task_completed(self, video_url):
        """Slot llamado cuando la tarea de generación de video se completa."""
        self.status_bar.showMessage("Tarea completada. Video generado.", 15000)
        final_message = f"Tarea completada exitosamente!\nVideo URL: {video_url}"
        self.result_output.setText(final_message)
        self.last_video_url = video_url # Guardar la URL

        # Habilitar botones de video y controles de entrada
        self.open_video_button.setEnabled(True)
        self.save_video_button.setEnabled(True)
        self.enable_input_controls()

        self.current_task_id = None
        self.video_task_worker = None # Limpiar referencia al worker

    @Slot(str)
    def on_task_failed(self, error_message):
        """Slot llamado cuando la tarea de generación de video falla."""
        self.status_bar.showMessage(f"Tarea fallida: {error_message}", 15000)
        self.result_output.setText(f"La tarea de generación de video falló:\n{error_message}")
        self.last_video_url = None # Asegurarse de que no hay URL válida

        # Habilitar controles de entrada
        self.enable_input_controls()
        self.open_video_button.setEnabled(False)
        self.save_video_button.setEnabled(False)

        self.current_task_id = None
        self.video_task_worker = None # Limpiar referencia al worker

        QMessageBox.critical(self, "Generación Fallida", f"La tarea de generación de video falló.\n{error_message}")


    def enable_input_controls(self):
         """Habilita los campos de entrada y el botón de generación."""
         self.generate_button.setEnabled(True)
         self.image_url_input.setEnabled(True)
         self.prompt_input.setEnabled(True)
         self.width_input.setEnabled(True)
         self.height_input.setEnabled(True)
         self.seed_input.setEnabled(True)


    @Slot()
    def open_video_url(self):
        """Abre la URL del video en el navegador o reproductor por defecto."""
        if self.last_video_url:
            try:
                # QDesktopServices.openUrl es la forma multi-plataforma de abrir URLs o archivos
                success = QDesktopServices.openUrl(QUrl(self.last_video_url))
                if not success:
                     self.status_bar.showMessage("No se pudo abrir la URL automáticamente.", 5000)
                     QMessageBox.warning(self, "Error al Abrir URL", "No se pudo abrir la URL automáticamente. Intenta copiar y pegar en tu navegador:\n" + self.last_video_url)
                else:
                     self.status_bar.showMessage(f"Abriendo URL: {self.last_video_url}", 5000)
            except Exception as e:
                self.status_bar.showMessage(f"Error al abrir URL: {e}", 5000)
                QMessageBox.critical(self, "Error al Abrir URL", f"Ocurrió un error al intentar abrir la URL:\n{e}\nIntenta copiar y pegar:\n" + self.last_video_url)
        else:
            self.status_bar.showMessage("No hay URL de video para abrir.", 5000)

    @Slot()
    def save_video_file(self):
        """Descarga el video desde la URL y lo guarda en un archivo local."""
        if not self.last_video_url:
            self.status_bar.showMessage("No hay URL de video para descargar.", 5000)
            return

        # Usar QFileDialog para obtener la ruta de guardado
        file_dialog = QFileDialog()
        file_dialog.setWindowTitle("Guardar Video")
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        file_dialog.setNameFilter("Archivos de Video (*.mp4 *.mov *.gif);;Todos los archivos (*)")
        file_dialog.setDefaultSuffix("mp4") # Sugerir extensión

        if file_dialog.exec():
            file_path = file_dialog.selectedFiles()[0]
            self.status_bar.showMessage(f"Descargando video a: {file_path}...")
            self.save_video_button.setEnabled(False) # Deshabilitar botón durante descarga
            self.open_video_button.setEnabled(False)
            self.generate_button.setEnabled(False) # También deshabilitar generar

            # Descargar el archivo en un hilo separado para no congelar el GUI
            # (Esto es una simplificación; una implementación robusta usaría un QThread dedicado para la descarga)
            try:
                response = requests.get(self.last_video_url, stream=True, timeout=600) # Aumentar timeout para descarga grande
                response.raise_for_status() # Lanzar excepción para errores HTTP

                with open(file_path, 'wb') as f:
                    # Opcional: mostrar progreso de descarga (requiere más código y un hilo)
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk: # filter out keep-alive new chunks
                            f.write(chunk)

                self.status_bar.showMessage(f"Video guardado exitosamente: {file_path}", 15000)
                QMessageBox.information(self, "Video Guardado", f"El video se ha guardado en:\n{file_path}")

            except requests.exceptions.RequestException as e:
                self.status_bar.showMessage(f"Error al descargar video: {e}", 15000)
                QMessageBox.critical(self, "Error de Descarga", f"Ocurrió un error al descargar el video:\n{e}")
            except Exception as e:
                 self.status_bar.showMessage(f"Error inesperado al guardar video: {e}", 15000)
                 QMessageBox.critical(self, "Error al Guardar", f"Ocurrió un error inesperado al guardar el video:\n{e}")
            finally:
                # Re-habilitar botones relevantes (guardar solo si hay URL, abrir solo si hay URL)
                if self.last_video_url:
                    self.save_video_button.setEnabled(True)
                    self.open_video_button.setEnabled(True)
                self.generate_button.setEnabled(True)


def main():
    app = QApplication(sys.argv)

    # Aplicar la paleta oscura a toda la aplicación
    app.setPalette(ModernDarkPalette())

    # Configurar una fuente global si se desea (opcional)
    # font = QFont("Inter", 10) # O "Segoe UI" u otra fuente moderna
    # app.setFont(font) # Esto podría sobrescribir estilos QSS específicos

    window = NovitaVideoGeneratorApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    # Para ejecutar esta aplicación, necesitarás PySide6 y requests.
    # Instala con:
    # pip install PySide6 requests
    main()