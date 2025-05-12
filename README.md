# 🚀 Herramientas de IA Creativa

Un conjunto de tres aplicaciones de escritorio modernas para generar contenido multimedia con IA: audio, imágenes y video. Interfaces gráficas intuitivas construidas con PySide6 que te permiten aprovechar el poder de las APIs de IA más avanzadas.

## 📋 Contenido

- [🎵 Generador de Audio](#-generador-de-audio)
- [🖼️ Generador de Imágenes](#-generador-de-imágenes)
- [🎬 Generador de Video](#-generador-de-video)
- [🛠️ Requisitos](#-requisitos)
- [⚙️ Instalación](#-instalación)
- [📝 Licencia](#-licencia)

---

## 🎵 Generador de Audio

![Audio App Screenshot](./assets/images/placeholder-audio-png.jpg)

### ✨ Características

- Convierte texto a voz con calidad ultra-realista
- Múltiples voces en español y otros idiomas
- Control de estabilidad y claridad de la voz
- Reproducción instantánea del audio generado
- Exportación a formato MP3

### 🔑 API Utilizada: ElevenLabs

Esta aplicación utiliza la API de ElevenLabs, líder en síntesis de voz de alta calidad.

**Registro:**
1. Visita [ElevenLabs](https://elevenlabs.io/)
2. Crea una cuenta gratuita
3. Obtén tu API Key desde el panel de control
4. La aplicación permite guardar tu API Key para usos futuros

**Uso:**
1. Ingresa tu API Key de ElevenLabs
2. Selecciona una voz y un modelo
3. Escribe el texto que deseas convertir a voz
4. Ajusta los parámetros de estabilidad y claridad
5. Genera, reproduce y exporta tu audio

---

## 🖼️ Generador de Imágenes

![Image App Screenshot](./assets/images/placeholder-image-png.jpg)

### ✨ Características

- Genera imágenes impresionantes a partir de descripciones textuales
- Interfaz moderna con tema oscuro
- Guardado automático de imágenes generadas
- Almacenamiento seguro de tu API Key

### 🔑 API Utilizada: Hugging Face (FLUX.1-schnell)

Esta aplicación utiliza el modelo FLUX.1-schnell a través de la API de Hugging Face.

**Registro:**
1. Visita [Hugging Face](https://huggingface.co/)
2. Crea una cuenta gratuita
3. Ve a tu perfil → Settings → Access Tokens
4. Crea un nuevo token (comienza con "hf_")
5. La aplicación permite guardar tu token para usos futuros

**Uso:**
1. Ingresa tu API Key de Hugging Face
2. Escribe un prompt detallado describiendo la imagen que deseas crear
3. Haz clic en "Generar Imagen"
4. Guarda la imagen generada en tu equipo

---

## 🎬 Generador de Video

![Video App Screenshot](./assets/images/placeholder-video-png.jpg)

### ✨ Características

- Convierte imágenes estáticas en videos animados
- Control de dimensiones y semilla para resultados consistentes
- Monitoreo en tiempo real del estado de generación
- Reproducción y descarga directa de videos generados

### 🔑 API Utilizada: Novita.ai (wan-i2v)

Esta aplicación utiliza la API de Novita.ai con el modelo wan-i2v para transformar imágenes en videos.

**Registro:**
1. Visita [Novita.ai](https://novita.ai/)
2. Crea una cuenta
3. Adquiere créditos y obtén tu API Key desde el panel de usuario
4. La aplicación permite verificar y guardar tu API Key

**Uso:**
1. Ingresa y verifica tu API Key de Novita.ai
2. Proporciona la URL de una imagen (debe ser accesible públicamente)
3. Escribe un prompt que describa el movimiento o animación deseada
4. Ajusta el ancho, alto y semilla si lo deseas
5. Genera el video y espera a que se complete el proceso
6. Visualiza o descarga el video resultante

---

## 🛠️ Requisitos

Para todas las aplicaciones:
- Python 3.8 o superior
- PySide6
- Requests

## ⚙️ Instalación

1. Clona este repositorio:
```bash
git clone https://github.com/ByteCodeSecure/herramientas-ia-creativa.git
cd herramientas-ia-creativa
```

2. Instala las dependencias para cada herramienta:
```bash
# Para la herramienta de Audio
cd Audio
pip install -r requirements.txt

# Para la herramienta de Imágenes
cd ../Imagenes
pip install -r requirements.txt

# Para la herramienta de Video
cd ../Video
pip install -r requirements.txt
```

3. Ejecuta la aplicación que desees:
```bash
# Para Audio
python main-gui.py

# Para Imágenes
python main-gui.py

# Para Video
python main-gui.py
```

## 💡 Consejos para mejores resultados

### Audio
- Para voces en español, utiliza modelos multilingües
- Usa signos de puntuación para controlar las pausas y entonación
- Ajusta la estabilidad para voces más consistentes

### Imágenes
- Sé específico en tus prompts: incluye detalles de estilo, iluminación y composición
- Experimenta con diferentes descripciones para obtener resultados variados
- Guarda los prompts que te den buenos resultados para reutilizarlos

### Video
- Usa imágenes de alta calidad para mejores resultados
- Describe claramente el movimiento deseado en el prompt
- Prueba diferentes semillas para obtener variaciones de la misma animación

## 📝 Licencia

Este proyecto está licenciado bajo [MIT License](LICENSE).

---

## 🙏 Agradecimientos

- [ElevenLabs](https://elevenlabs.io/) por su increíble API de síntesis de voz
- [Hugging Face](https://huggingface.co/) por hospedar el modelo FLUX.1-schnell
- [Novita.ai](https://novita.ai/) por su innovadora API de generación de video
- [PySide6](https://doc.qt.io/qtforpython-6/) por el framework de interfaz gráfica

---

Desarrollado con ❤️ por ByteCodeSecure

¿Tienes preguntas o sugerencias? [Abre un issue](https://github.com/ByteCodeSecure/herramientas-ia-creativa/issues)