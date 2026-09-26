import torch, os
torch.set_num_threads(os.cpu_count() or 8)
os.environ["CUDA_VISIBLE_DEVICES"] = ""
torch.set_grad_enabled(False) #Este saca los gradientes innecesarios para que sea menos trabajo para la CPU.
from pydub import AudioSegment
from TTS.api import TTS
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import XttsAudioConfig, XttsArgs
from TTS.config.shared_configs import BaseDatasetConfig
from TTS.tts.utils.speakers import SpeakerManager
from TTS.tts.utils.text.tokenizer import TTSTokenizer
from TTS.utils.audio import AudioProcessor

#REGIÓN PARA MODULARIZACIÓN DE ARCHIVOS
from coquiTTS_archivos.parametros import *
from coquiTTS_archivos.conversion_de_parametros import *

import traceback, random, naturalization, estimating, pipeline
from pathlib import Path

cpu_cores = os.cpu_count()
if cpu_cores:
    torch.set_num_threads(cpu_cores)
    print(f"Hilos de Torch configurados en: {cpu_cores}")
else:
    torch.set_num_threads(4) # Valor seguro por defecto

#torch.serialization.add_safe_globals([XttsConfig, XttsAudioConfig, BaseDatasetConfig, XttsArgs, SpeakerManager, TokenizerConfig, AudioProcessorConfig]) es una función que se utiliza para agregar clases o funciones a la lista de objetos seguros que pueden ser deserializados por PyTorch. Esto es importante para evitar problemas de seguridad al cargar modelos o datos que podrían contener código malicioso. En este caso, se están agregando varias clases relacionadas con la configuración y el procesamiento de audio para el modelo TTS (Text-to-Speech) que se está utilizando.
torch.serialization.add_safe_globals([
    XttsConfig,
    XttsAudioConfig,
    BaseDatasetConfig,
    XttsArgs,
    SpeakerManager,
    TTSTokenizer,
    AudioProcessor
])

"""-----------------------------------------------------------------------------------------------------"""


tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=True)
tts.to("cpu")

def ajustar_parametros_finales(idioma, speed, temperature, frase):
    """
    Ajuste final de parámetros antes de enviar al TTS.
    Prioriza naturalidad, evita velocidades artificiales
    y adapta según idioma + tipo de frase.
    """

    palabras = frase.split()
    num_palabras = len(palabras)

    # 🔵 Clasificación básica
    if num_palabras <= 2:
        tipo = "micro"
    elif num_palabras <= 8:
        tipo = "media"
    else:
        tipo = "larga"
        
    # 🔴 Clamp global base
    speed = max(0.85, min(1.30, speed))

    # 🟣 Clamp por idioma (único y consistente)
    limites = {
        "zh-cn": (0.90, 1.02),
        "ja":    (1.00, 1.08),
        "ko":    (0.95, 1.10),
        "ru":    (0.95, 1.06),
        "en":    (0.95, 1.15),
    }

    min_s, max_s = limites.get(idioma, (0.9, 1.1))
    speed = max(min_s, min(max_s, speed))

    
    # 🟢 Microsegmentos → evitar aceleración artificial
    if tipo == "micro":
        speed *= 0.97
    # 🟡 Frases largas → más estabilidad
    elif tipo == "larga":
        speed *= 1.02

    # 🟠 Protección extra contra valores extremos
    speed = max(min_s, min(max_s, speed))

    return speed, temperature


def ajustar_velocidad_con_afinación(idioma):
    if idioma == "zh-cn":
        return random.uniform(0.94, 0.97)
    elif idioma == "ja":
        return random.uniform(1.03, 1.07)
    elif idioma == "ko":
        return random.uniform(0.95, 1.05)
    elif idioma == "en":
        return random.uniform(1.05, 1.15)
    elif idioma == "ru":
        return random.uniform(1.00, 1.08)
    
    return 1.1


def mapear_nombres_de_idiomas():
    nombres = []
    for código, datos in IDIOMAS.items():
        nombres.append(datos["nombre"])
        
    return nombres


def obtener_codigo_por_nombre(nombre):
    for codigo, datos in IDIOMAS.items():
        if datos["nombre"] == nombre:
            return codigo
    return None


def generar_con_retry(frase, idioma, perfil, archivo, duracion_sub, speed=None, temperature=None, ratio_previo=None, seg_id=None, max_intentos=None):
    """
    Esta función genera audio mediante TTS con un sistema de reintentos controlados.

    Además intenta producir una voz lo más natural posible impidiendo:
    - resultados demasiado rígidos o planos (poca variación)
    - resultados inestables o con artefactos

    Funcionamiento:
    1. Genera audio con parámetros dinámicos (temperature, speed).
    2. Evalúa la calidad del resultado:
        a. relación entre duración del audio y subtítulo
        b. nivel de volumen (dBFS)
    3. Si el resultado no es aceptable:
        a. reintenta ajustando ligeramente los parámetros hasta que los intentos máximos lleguen a su límite
    4. Se limita a un número máximo de intentos para evitar bucles innecesarios.

    Objetivo:
    Mantener un equilibrio entre naturalidad, estabilidad e identidad de la voz
    en distintos idiomas. ESTE ES EL VERDADERO OBJETIVO, NO BUSCAR LA MEJOR O LA PERFECTA TEMPERATURE Y VELOCIDAD
    """

    base_temp = perfil["temperature"]
    base_speed = perfil["speed"]
    
    if duracion_sub <= 0:
        print("Duracion invalida")
        return None
    
    frase_original = frase

    # Rangos de tolerancia por idioma
    if idioma == "zh-cn":
        min_ratio, max_ratio = 0.97, 1.04
        umbral_score = 0.10
    elif idioma == "ko":
        min_ratio, max_ratio = 0.95, 1.15
        umbral_score = 0.12
    elif idioma == "ja":
        min_ratio, max_ratio = 0.97, 1.125
        umbral_score = 0.12
    else:
        min_ratio, max_ratio = 0.92, 1.08
        umbral_score = 0.18
    
    mejor_score = float("inf")
    mejor_audio = None
    mejor_speed = None
    mejor_temp = None
    mejor_ratio = None

    nivel_de_riesgo = naturalization.detectar_peligros_de_desfasaje(frase)
    
    debug_log(idioma, f"RIESGO detectado: {nivel_de_riesgo}")
    
    
    if idioma == "ru":
        max_intentos = 2
    else:
        match nivel_de_riesgo:
            case "alto":
                max_intentos = 2
            case _:
                max_intentos = 1

    if speed is None:
        speed = base_speed * ajustar_velocidad_con_afinación(idioma)
        print(f"VELOCIDAD CALCULADA: {speed:.3f}\n")
    else:
        print(f"VELOCIDAD PREDEFINIDA: {speed:.3f}\n")
        
    if temperature is None:
        temperature = base_temp
        print(f"TEMMPERATURE CALCULADA: {temperature:.3f}\n")
    else:
        print(f"TEMPERATURE PREDEFINIDAS: {temperature:.3f}\n")
        
    print("Base:", speed)
    
    ratio_previo = estimating.evaluar_ajuste_previo(frase_original, idioma, duracion_sub)
    
    #El for es para repetir intentos.
    for intento in range(max_intentos):
        frase_en_iteración = frase_original
        
        
        speed, temperature, frase_en_iteración = naturalization.ajustar_naturalidad_por_idioma(idioma, speed, temperature, frase_en_iteración)
        print("Naturalidad:", speed)
        
        # speed = estimating.ajustar_speed_por_prediccion(speed, ratio_previo)
        # print("Predicción:", speed)
        
        speed *= estimating.ajustar_factor_complejidad(frase_en_iteración, idioma)
        print("Complejidad:", speed)
        
        #EL AJUSTE SE HACE SÓLAMENTE CUANDO HAY SILABAS QUE CORREN EL RIESGO DE CORTARSE
        if naturalization.detectar_peligros_foneticos(frase_en_iteración, idioma):
            frase, speed = naturalization.ajustar_pronunciacion_muy_sensible(frase_en_iteración, idioma, speed)


        speed, temperature = ajustar_parametros_finales(idioma, speed, temperature, frase_en_iteración)
        print("Final:", speed)
    
        if idioma == "ru":
            speed = max(0.90, min(1.25, speed))
        else:
            speed = max(0.85, min(1.15, speed))
            
        debug_log(idioma, f"[INTENTO {intento+1}] speed={speed:.3f} temp={temperature:.3f} ratio_previo={ratio_previo:.3f} | TEXTO: {frase_en_iteración}")
        
        try:
            tts.tts_to_file(
                text=frase_en_iteración,
                file_path=archivo,
                language=idioma,
                speaker_wav=perfil["speaker"],
                temperature=temperature,
                speed=speed,
                repetition_penalty=perfil["repetition_penalty"]
            )
        except Exception as e:
            print(f"⚠ Error en TTS (intento {intento}): {e}")
            traceback.print_exc()
            continue
        
        audio = AudioSegment.from_wav(archivo)
    
        duración_audio = len(audio)
        ratio = duración_audio / duracion_sub

        
        # 🔥 NUEVO: corrección basada en duración real
        correccion = 1 / ratio

        if intento < max_intentos - 1:
            speed *= correccion
        
        if ratio > 1.5:
            correccion = max(0.75, min(1.10, 1 / ratio))
        else:
            correccion = max(0.90, min(1.10, 1 / ratio))
        
        
        score = (abs(ratio - 1) * 1.2 +
                max(0, (-38 - audio.dBFS) / 25) * 0.08 +
                (0.05 if len(frase_en_iteración) < 6 else 0.0)
                )
        
        if ratio < 1:
            score += abs(ratio - 1) * 1.2  # más castigo si es corto
        else:
            score += abs(ratio - 1) * 1.1
        
        if score < 0.08:
            debug_log(idioma, f" ACEPTADO CON ÉXITO")
            return audio
        
        #ESTA LÓGICA LO PUEDO MOVER A ajustar_pronunciacion_muy_sensible(frase, idioma, speed)
        
        subtítulo_muy_corto = duración_audio < duracion_sub * 0.33
        
        # Penalizaciones adicionales
        if subtítulo_muy_corto:
            print("⚠ Audio demasiado corto, penalización aplicada")
            score += 0.12
        
        if ratio > 2.0:
            
            score += (ratio - 2.0) * 1.0

        if idioma == "ko" and not (0.90 <= speed <= 1.15):
            score += 0.08
        
        
        #Aca mejore el ratio para que no se alargue de mas. Si hay otros idiomas descalibrados lo ajustaremos a medida que vaya pasando el tiempo
        if idioma == "zh-cn":
            if ratio < 0.9:
                score += (0.9 - ratio) * 1.2

        if idioma == "ko" and ratio < 0.95:
            score += (0.95 - ratio) * 0.5
        
        if idioma == "ko" and audio.dBFS < -35:
            score += (-35 - audio.dBFS) * 0.01
        
        if audio.dBFS > -12:
            score += (audio.dBFS + 12) * 0.01
        
        
        debug_log(idioma, f"[RESULTADO] ratio={ratio:.3f} dBFS={audio.dBFS:.1f} score={score:.3f}")
        

        if score < mejor_score:
            mejor_score = score
            mejor_audio = audio
            mejor_speed = speed
            mejor_temp = temperature
            mejor_ratio = ratio
        
        if (min_ratio <= ratio <= max_ratio and audio.dBFS > -40 and score < umbral_score):
            return audio
    
    if mejor_score < 0.08:
        return mejor_audio
        
    if mejor_audio is not None:
        if mejor_score < umbral_score:
            print(f"[BEST] ratio={mejor_ratio:.3f} speed={mejor_speed:.3f} temp={mejor_temp:.3f}\n")
        else:
            debug_log(idioma, f"USANDO MEJOR INTENTO [FALLBACK]")
    else:
        print("❌ No se generó ningún audio válido")

    return mejor_audio


def speechear_por_cada_duracion(idioma, sub, nombre_del_archivo):
    """
    Esta función se enfoca en convertir las oraciones de un archivo de subtítulos en voz.
    
    1. Se crea una carpeta para separar cada subtítulo correspondiente antes de entrar en un lote de archivos
    
    2. Controla que el archivo tenga oración, en caso contrario corta el sistema.
    
    3. Calcula la duración del subtítulo y renombra como referencia con el fin de:
    
    a. Colocar la narración según la duración
    b. Ordenar la explicación para una mayor claridad
    
    4. Ajusta los parámetros para una pausa natural mayor antes de guardar el archivo en una carpeta específica
    
    5. Finalmente guardan las narraciones con el nombre de la carpeta del subtítulo para una mayor etiqueta y orden para la traducción de un video.
    """
    os.makedirs(f"{nombre_del_archivo}", exist_ok=True) #Esto puse acá para que no se cree infinitamente las carpetas.
    
    código_de_idioma = normalizar_idioma(idioma)
    
    familia = IDIOMAS[código_de_idioma]["familia"]
    
    perfil = PERFILES[familia].copy()
    
    texto_orig = sub.text
    texto_adaptado = adaptar_texto_segun_idioma(código_de_idioma, texto_orig)
    frase = optimizar_texto(texto_adaptado)
    if not frase or not isinstance(frase, str):
        print("⚠ Texto inválido para narrar o está vacío")
        return None
    
    print("Texto original:")
    print(texto_orig)

    print("Texto adaptado:")
    print(texto_adaptado)

    print("Texto optimizado:")
    print(frase)
    
    
    speaker_path = CARPETA_DE_SPEAKERS / perfil["speaker"]
    
    perfil["speaker"] = str(speaker_path)
    
    duración_sub = sub.end.ordinal - sub.start.ordinal
    
    audios_internos = pipeline.pipeline_tts(
    texto=frase,
    idioma=código_de_idioma,
    perfil=perfil,
    carpeta=nombre_del_archivo,
    duracion_sub=duración_sub,
    sub_id=sub.index,  # o contador manual
    start=sub.start.ordinal,
    end=sub.end.ordinal
    )

    audios_internos = [a for a in audios_internos if a]
    
    audio_final = AudioSegment.silent(duration=0)
    
    margen = 40 if código_de_idioma in ["ja", "zh-cn"] else 80
    
    for i, audio in enumerate(audios_internos):
        print(f"Segmento {i}: {len(audio)} ms")

        audio_final += audio

        if i < len(audios_internos) - 1:
            audio_final += AudioSegment.silent(duration=margen)

    print("Duración después de unir segmentos:", len(audio_final))


    audio_final = naturalization.aplicar_pausas_naturales(frase, audio_final)
    
    print("Después de pausas naturales:", len(audio_final))
    
    audio_final = naturalization.ajustar_duracion_por_idioma(audio_final, duración_sub, código_de_idioma)
    
    print("Después de ajustar duración:", len(audio_final))
            
    print(f"Duración final: {len(audio_final)} ms | Duración subtítulo: {duración_sub} ms\n")
    return audio_final