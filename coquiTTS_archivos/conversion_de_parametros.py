import os
from pydub import AudioSegment
from TTS.api import TTS
from pathlib import Path

tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=True)
tts.to("cpu")

CARPETA_DE_SPEAKERS = Path("audio")

#Estas funciones guardaré en un archivo a parte llamado Conversión de parámetros.py para separar muy bien
def convertir_codec_audio(clave_familia, perfiles):
    
    speaker_file = CARPETA_DE_SPEAKERS / perfiles[clave_familia]["speaker"]
    
    audio = AudioSegment.from_wav(speaker_file)
    necesita_conversion = False

    if audio.channels != 1:
        audio = audio.set_channels(1)
        necesita_conversion = True

    if audio.frame_rate != 22050:
        audio = audio.set_frame_rate(22050)
        necesita_conversion = True

    if necesita_conversion:
        salida = CARPETA_DE_SPEAKERS / f"{clave_familia}_clean.wav"
        audio.export(salida, format="wav") #Acá se encuentra
        return salida
    else:
        return speaker_file

def limpiar_srt(archivo_final):
    with open(archivo_final, "r", encoding="utf-8") as f:
        lineas = f.readlines()

    resultado = []
    skip_blank = False
    inicio = True
    for line in lineas:
        # Ignorar espacios en blanco iniciales
        if inicio and line.strip() == "" and not resultado:
            continue
        inicio = False
        
        if "-->" in line:  
            # si la línea es un rango de tiempo, la próxima vacía se salta
            resultado.append(line.rstrip() + "\n")
            skip_blank = True
        elif skip_blank and line.strip() == "":
            # saltar solo la línea vacía inmediatamente después del tiempo
            skip_blank = False
            continue
        else:
            resultado.append(line.rstrip() + "\n")
            skip_blank = False

    with open(archivo_final, "w", encoding="utf-8") as f:
        f.writelines(resultado)

def convertir_a_srt(file_txt):
    nombre_base, _ = os.path.splitext(file_txt)
    archivo_srt = f"{nombre_base}.srt" #Mirá, ya tengo esta línea para crear el nombre del archivo srt a partir del txt, así que no entiendo por qué me preguntas eso. El código que te di ya hace eso, no es necesario agregar nada más para crear el archivo srt con el mismo nombre que el txt. Si quieres, puedo explicarte cómo funciona esa parte del código, pero no es necesario agregar nada más para crear el archivo srt con el mismo nombre que el txt.

    with open(file_txt, "r", encoding="utf-8") as f:
        lineas = [linea.strip() for linea in f if linea.strip()]

    with open(archivo_srt, "w", encoding="utf-8") as f:
        indice = 1
        for linea in lineas:
            if "-->" in linea:
                partes = linea.split("-->")
                inicio = partes[0].strip()
                resto = partes[1].strip()

                # separar tiempo final y texto
                fin, *texto = resto.split(" ", 1)
                texto = texto[0] if texto else ""

                f.write(f"{indice}\n")
                f.write(f"{inicio} --> {fin}\n")
                f.write(f"{texto}\n\n")

                indice += 1

    print(f"Archivo convertido: {archivo_srt}")
    return archivo_srt #No se si es este el problema? porque yo tengo definido archivo final en lugar de srt

def formatear_tiempo(srt_time):
    return f"{srt_time.hours:02}-{srt_time.minutes:02}-{srt_time.seconds:02},{srt_time.milliseconds:03}"

def optimizar_texto(frase):
    frase = frase.strip()
    
    if not frase.endswith(('.', '!', '?')):
        frase += '.'
    
    frase = frase[0].upper() + frase[1:]
    
    return frase