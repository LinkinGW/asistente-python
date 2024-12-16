import speech_recognition as sr
import pyttsx3
import time
import json
import sys
import ctypes
import os
import subprocess
import webbrowser
import yt_dlp
import vlc
import requests
import win32com.client
import datetime
import winreg
from threading import Thread
from googlesearch import search as gsearch
from bs4 import BeautifulSoup
from transformers import pipeline
import torch

def es_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def ejecutar_como_admin():
    if not es_admin():
        # Re-ejecuta el programa con privilegios de administrador
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()

class Asistente:
    def __init__(self):
        self.nlp = pipeline("text-generation", model="EleutherAI/gpt-neo-1.3B", device=0 if torch.cuda.is_available() else -1)
        self.recognizer = sr.Recognizer()
        self.engine = pyttsx3.init()
        self.comandos = self.cargar_comandos()
        self.conocimiento = self.cargar_conocimiento()
        self.configurar_voz()
        self.nombre = "asistente"
        self.reproductor = None
        self.esta_reproduciendo = False
        self.historial_conversacion = []


    def mantener_contexto(self, texto):
        self.historial_conversacion.append(texto)
        if len(self.historial_conversacion) > 5:
            self.historial_conversacion.pop(0)

    def procesar_conversacion(self, texto):
        
        respuestas_predefinidas = {
            "hola": "Hola, ¿cómo estás?",
            "buenos días": "¡Buenos días! ¿En qué puedo ayudarte?",
            "buenas tardes": "Buenas tardes, ¿qué tal tu día?",
            "buenas noches": "Buenas noches, espero que hayas tenido un buen día.",
        }

        if texto in respuestas_predefinidas:
            return respuestas_predefinidas[texto]


        contexto = " ".join(self.historial_conversacion[-5:])  # Últimas 5 interacciones
        prompt = f"{contexto}\nUsuario: {texto}\nAsistente:"
        try:
            respuesta = self.nlp(prompt, max_length=200, num_return_sequences=1, temperature=0.7)[0]['generated_text']
            respuesta = respuesta.split("Asistente:")[-1].strip()  # Extraer respuesta generada
            self.mantener_contexto(f"Usuario: {texto}")
            self.mantener_contexto(f"Asistente: {respuesta}")
            self.guardar_conversacion(texto, respuesta)
            return respuesta
        except Exception as e:
            print(f"Error al generar respuesta: {e}")
            return "Lo siento, hubo un error al procesar tu solicitud."

    def cargar_conocimiento(self):
        try:
            with open('conocimiento.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {"temas": {}, "ultima_actualizacion": ""}

    def cambiar_nombre(self, nuevo_nombre):
        self.nombre = nuevo_nombre
        self.hablar(f"Mi nuevo nombre es {nuevo_nombre}")

    def guardar_conocimiento(self):
        with open('conocimiento.json', 'w', encoding='utf-8') as f:
            json.dump(self.conocimiento, f, ensure_ascii=False, indent=4)

    def reproducir_audio(self, url):
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                url_stream = info['url']
            instance = vlc.Instance()
            self.reproductor = instance.media_player_new()
            self.reproductor.audio_set_volume(50)
            media = instance.media_new(url_stream)
            self.reproductor.set_media(media)
            self.reproductor.play()
            self.esta_reproduciendo = True
            while self.esta_reproduciendo:
                time.sleep(1)
        except Exception as e:
            print(f"Error al reproducir: {e}")
            self.esta_reproduciendo = False

    def buscar_informacion(self, tema):
        try:
            resultados = []
            for url in gsearch(tema, num=3, lang="es"):
                if len(resultados) >= 3:
                    break
                response = requests.get(url, timeout=5)
                soup = BeautifulSoup(response.text, 'html.parser')
                parrafos = soup.find_all('p')
                for parrafo in parrafos:
                    if len(parrafo.text.strip()) > 50:
                        resultados.append({
                            "info": parrafo.text.strip()[:200],
                            "fuente": url
                        })
                        break
                if len(resultados) >= 3:
                    break
            if resultados:
                self.conocimiento["temas"][tema] = {
                    "info": [r["info"] for r in resultados],
                    "fecha": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "fuentes": [r["fuente"] for r in resultados]
                }
                self.guardar_conocimiento()
                return resultados
            else:
                return None
        except Exception as e:
            print(f"Error al buscar información: {e}")
            return None

    def guardar_conversacion(self, pregunta, respuesta):
        if not hasattr(self, 'conversaciones'):
            self.conversaciones = {}
        self.conversaciones[pregunta] = respuesta
        with open('conversaciones.json', 'w') as f:
            json.dump(self.conversaciones, f)

    def cargar_conversaciones(self):
        try:
            with open('conversaciones.json', 'r') as f:
                self.conversaciones = json.load(f)
        except FileNotFoundError:
            self.conversaciones = {}

    def cargar_comandos(self):
        if os.path.exists('comandos.json'):
            with open('comandos.json', 'r') as f:
                return json.load(f)
        return {}

    def guardar_comandos(self):
        with open('comandos.json', 'w') as f:
            json.dump(self.comandos, f)

    def aprender(self, comando, respuesta):
        self.comandos[comando] = respuesta
        self.guardar_comandos()
        self.hablar(f"He aprendido que cuando me digas '{comando}', debo responder '{respuesta}'")

    def escuchar(self):
        with sr.Microphone() as source:
            print(f"Esperando palabra clave ({self.nombre})...")
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            try:
                audio = self.recognizer.listen(source, timeout=None, phrase_time_limit=5)
                texto = self.recognizer.recognize_google(audio, language="es-ES")
                if self.nombre in texto.lower():
                    self.hablar("Te escucho")
                    print("Escuchando comando...")
                    audio_comando = self.recognizer.listen(source, phrase_time_limit=5)
                    texto_comando = self.recognizer.recognize_google(audio_comando, language="es-ES")
                    print(f"Has dicho: {texto_comando}")
                    return texto_comando.lower()
                return ""
            except sr.UnknownValueError:
                return ""
            except sr.RequestError as e:
                print(f"Error en el servicio de reconocimiento de voz; {e}")
                return ""
            except sr.WaitTimeoutError:
                print("Tiempo de espera agotado, volviendo a escuchar...")
                return ""

    def escuchar_comando(self):
        with sr.Microphone() as source:
            print("Escuchando comando...")
            self.recognizer.adjust_for_ambient_noise(source)
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                texto = self.recognizer.recognize_google(audio, language="es-ES")
                print(f"Has dicho: {texto}")
                return texto.lower()
            except sr.UnknownValueError:
                print("No pude entender el audio")
                return ""
            except sr.RequestError as e:
                print(f"Error en el servicio; {e}")
                return ""

    def configurar_voz(self):
        self.engine = pyttsx3.init()
        voices = self.engine.getProperty('voices')
        for voice in voices:
            try:
                if hasattr(voice, 'languages') and voice.languages:
                    if "spanish" in voice.languages[0].lower():
                        self.engine.setProperty('voice', voice.id)
                        break
            except:
                continue
        self.engine.setProperty('rate', 150)
        self.engine.setProperty('volume', 0.9)

    def buscar_programa(self, nombre_programa):
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths")
            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    app_name = winreg.EnumKey(key, i)
                    if nombre_programa.lower() in app_name.lower():
                        app_key = winreg.OpenKey(key, app_name)
                        path = winreg.QueryValue(app_key, None)
                        return path
                except WindowsError:
                    continue
        except WindowsError:
            pass
        program_folders = [
            os.environ.get('ProgramFiles'),
            os.environ.get('ProgramFiles(x86)'),
            os.path.join(os.environ.get('LOCALAPPDATA'), 'Programs'),
            r"C:\Program Files",
            r"C:\Program Files (x86)"
        ]
        for folder in program_folders:
            for root, dirs, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith('.exe') and nombre_programa.lower() in file.lower():
                        return os.path.join(root, file)
        return None

    def ejecutar_comando(self, comando):
        comando = comando.lower()
        if "abre" in comando or "abrir" in comando:
            app = comando.split("abre" if "abre" in comando else "abrir", 1)[1].strip().lower()
            if "steam" in app:
                try:
                    steam_path = r"C:\Program Files (x86)\Steam\Steam.exe"
                    if os.path.exists(steam_path):
                        os.startfile(steam_path)
                        self.hablar("Abriendo Steam")
                        return
                    else:
                        self.hablar("No pude encontrar Steam en la ruta especificada")
                except Exception as e:
                    print(f"Error al abrir Steam: {str(e)}")
                    self.hablar("Hubo un problema al abrir Steam")
                return
            ruta_programa = self.buscar_programa(app)
            if ruta_programa:
                try:
                    subprocess.Popen([ruta_programa])
                    self.hablar(f"Abriendo {app}")
                except Exception as e:
                    print(f"Error al abrir {app}: {str(e)}")
                    self.hablar(f"No pude abrir {app}")
            else:
                self.hablar(f"No pude encontrar {app}")
        elif "abrir carpeta" in comando:
            carpeta = comando.split("abrir carpeta", 1)[1].strip()
            ruta_escritorio = os.path.join(os.environ['USERPROFILE'], 'Desktop')
            try:
                for item in os.listdir(ruta_escritorio):
                    if carpeta.lower() in item.lower() and os.path.isdir(os.path.join(ruta_escritorio, item)):
                        os.startfile(os.path.join(ruta_escritorio, item))
                        self.hablar(f"Abriendo la carpeta {item}")
                        return
                self.hablar(f"No pude encontrar la carpeta {carpeta}")
            except Exception as e:
                self.hablar("Hubo un error al intentar abrir la carpeta")
                print(f"Error: {str(e)}")
        elif "busca" in comando:
            query = comando.split("busca", 1)[1].strip()
            url = f"https://www.google.com/search?q={query}"
            webbrowser.open(url)
            self.hablar(f"Buscando {query} en Google")
        elif "reproduce" in comando or "busca en youtube music" in comando:
            try:
                busqueda = comando.split("reproduce", 1)[1].strip()
                self.hablar(f"Buscando {busqueda}")
                ydl_opts = {
                    'default_search': 'ytsearch',
                    'format': 'bestaudio/best',
                    'noplaylist': True,
                    'quiet': True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(f"ytsearch:{busqueda}", download=False)
                    if 'entries' in info:
                        video = info['entries'][0]
                        url = f"https://music.youtube.com/watch?v={video['id']}"
                        titulo = video['title']
                        if self.esta_reproduciendo:
                            self.esta_reproduciendo = False
                            if self.reproductor:
                                self.reproductor.stop()
                        Thread(target=self.reproducir_audio, args=(url,)).start()
                        self.hablar(f"Reproduciendo {titulo}")
                    else:
                        self.hablar("No encontré esa canción")
            except Exception as e:
                self.hablar("Hubo un error al reproducir la música")
                print(f"Error: {e}")
        elif "pausa" in comando:
            if self.reproductor:
                self.reproductor.pause()
                self.hablar("Música pausada")
            return
        elif "continua" in comando or "resume" in comando:
            if self.reproductor:
                self.reproductor.play()
                self.hablar("Continuando reproducción")
            return
        elif "detener" in comando or "stop" in comando:
            if self.reproductor:
                self.reproductor.stop()
                self.esta_reproduciendo = False
                self.hablar("Reproducción detenida")
            return
        else:
            self.hablar("No entiendo ese comando")
        if not any(palabra in comando for palabra in ["abre", "busca", "reproduce"]):
            respuesta = self.procesar_conversacion(comando)
            self.hablar(respuesta)

    def manejar_archivos(self, comando):
        if "crear carpeta" in comando:
            try:
                partes = comando.split("crear carpeta", 1)[1].strip()
                ruta = partes.split("en", 1)
                nombre_carpeta = ruta[0].strip()
                if len(ruta) > 1:
                    ruta_completa = os.path.join(ruta[1].strip(), nombre_carpeta)
                else:
                    ruta_completa = nombre_carpeta
                os.makedirs(ruta_completa, exist_ok=True)
                self.hablar(f"He creado la carpeta {nombre_carpeta}")
            except Exception as e:
                self.hablar(f"No pude crear la carpeta: {str(e)}")
        elif "abre" in comando or "abrir" in comando:
            if "abre" in comando:
                app = comando.split("abre", 1)[1].strip().lower()
            else:
                app = comando.split("abrir", 1)[1].strip().lower()
            rutas_busqueda = [
                os.path.join(os.environ['USERPROFILE'], 'Desktop'),
                os.path.join(os.environ['ProgramData'], 'Microsoft\Windows\Start Menu\Programs'),
                os.path.join(os.environ['APPDATA'], 'Microsoft\Windows\Start Menu\Programs')
            ]
            for ruta in rutas_busqueda:
                try:
                    for archivo in os.listdir(ruta):
                        nombre_archivo = archivo.lower()
                        if app in nombre_archivo:
                            ruta_completa = os.path.join(ruta, archivo)
                            try:
                                if archivo.endswith('.lnk'):
                                    shell = win32com.client.Dispatch("WScript.Shell")
                                    shortcut = shell.CreateShortCut(ruta_completa)
                                    subprocess.Popen(shortcut.Targetpath)
                                else:
                                    os.startfile(ruta_completa)
                                self.hablar(f"Abriendo {archivo}")
                                return
                            except Exception as e:
                                print(f"Error al abrir {archivo}: {str(e)}")
                                continue
                except Exception as e:
                    print(f"Error al buscar en {ruta}: {str(e)}")
                    continue
            self.hablar(f"No pude encontrar {app}")

    def hablar(self, texto):
        self.engine.say(texto)
        self.engine.runAndWait()

    def ejecutar(self):
        self.cargar_conversaciones()
        while True:
            comando = self.escuchar().lower()
            if "quiero cambiar tu nombre" in comando:
                self.hablar("¿Cuál será mi nuevo nombre?")
                nuevo_nombre = self.escuchar_comando()
                if nuevo_nombre:
                    self.cambiar_nombre(nuevo_nombre.strip())
                else:
                    self.hablar("No pude entender el nuevo nombre")
            if "busca información sobre" in comando:
                tema = comando.split("busca información sobre")[1].strip()
                self.hablar(f"Buscando información sobre {tema}")
                resultados = self.buscar_informacion(tema)
                if resultados:
                    self.hablar("He encontrado esta información:")
                    for i, resultado in enumerate(resultados, 1):
                        self.hablar(f"Fuente {i}:")
                        self.hablar(resultado["info"][:200])
                else:
                    self.hablar("Lo siento, no pude encontrar información sobre ese tema")
            if comando in self.conversaciones:
                respuesta = self.conversaciones[comando]
                self.hablar(respuesta)
            elif "aprende" in comando:
                self.hablar("¿Qué comando debo aprender?")
                nuevo_comando = self.escuchar_comando()
                if nuevo_comando:
                    self.hablar("¿Qué debo responder a ese comando?")
                    nueva_respuesta = self.escuchar_comando()
                    if nueva_respuesta:
                        self.guardar_conversacion(nuevo_comando.strip(), nueva_respuesta.strip())
                        self.hablar(f"He aprendido que cuando me digas '{nuevo_comando}', responderé '{nueva_respuesta}'")
                    else:
                        self.hablar("No pude entender la respuesta")
                else:
                    self.hablar("No pude entender el comando")
            if "abre" in comando or "busca" in comando:
                self.ejecutar_comando(comando)
            elif "abrir" in comando:
                self.manejar_archivos(comando)
            elif "reproduce" in comando or "busca en youtube music" in comando or "pon musica de" in comando:
                self.ejecutar_comando(comando)
            elif "pausa" in comando or "continua" in comando or "detener" in comando or "stop" in comando:
                self.ejecutar_comando(comando)
            elif "adiós" in comando:
                self.hablar("Hasta luego")
                break

if __name__ == "__main__":
    ejecutar_como_admin()
    asistente = Asistente()
    asistente.ejecutar()