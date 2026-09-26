import re, random
from pydub import AudioSegment
from coquiTTS_archivos.parametros import *

SIGNOS_DE_PAUSAS = {
    "zh-cn": ["，", "。", "！", "？", "；", "："],
    "ja":    ["、", "。", "！", "？"],
    "default": [",", ".", "!", "?", ";", ":"]
}

PESO_SIGNOS = {
    ",": 2,
    ".": 3,
    "!": 3,
    "?": 3,
    ";": 4,
    ":": 3,
    "...": 5,
    "、": 2,
    "。": 3,
    "，": 2,
    "！": 3,
    "？": 3
}

#La función se ha modificado para que cuente los signos de puntuación según el idioma, lo que permite un ajuste más preciso de las pausas en la narración. Además, usar un diccionario para los signos de puntuación por idioma permite una mayor flexibilidad y adaptabilidad a diferentes lenguajes, mejorando la naturalidad del audio generado, ya que si se mantiene la pausa muy exacta para cada idioma, puede sonar más robótico y menos humano. Por ejemplo, en japonés, las pausas naturales son diferentes a las del español o inglés, y esta función permite ajustar eso de manera más precisa.
def contar_pausas(texto, idioma):
    signos = SIGNOS_DE_PAUSAS.get(idioma, SIGNOS_DE_PAUSAS["default"])
    return sum(texto.count(signo) for signo in signos)


def is_hiragana(character):
     return re.match(r'[\u3040-\u309F]', character)


def is_katakana(character):
     return re.match(r'[\u30A0-\u30FF]', character)


def conviene_dividir(seg, idioma):
    texto = seg.get("texto", "")
    duracion = seg.get("duracion", 0)

    if not texto or duracion <= 0:
        return False

    longitud = len(texto)

    # 🔴 Muy corto → no dividir nunca
    if longitud < 15:
        return False

    # 🔴 Muy poco tiempo → dividir rompe audio
    if duracion < 1200:
        return False

    # 🔴 Sin puntuación → dividir queda artificial
    if not any(p in texto for p in ".,!?。、！？，"):
        return False

    # 🟡 Ratio texto/duración (densidad)
    ratio = longitud / duracion

    # 🔴 Demasiado denso → mejor no dividir (TTS se rompe)
    if ratio > 0.03:
        return False

    # 🟢 Casos por idioma
    if idioma == "ja":
        
        if texto.strip().endswith("、"):
            return False
        
        # 🔴 Frase larga pero continua → mejor completa
        if "、" in texto and "。" not in texto:
            return False
        
        # Japonés es delicado
        kana = sum(1 for c in texto if is_hiragana(c) or is_katakana(c))
        proporcion_kana = kana / longitud if longitud > 0 else 0

        # 🔴 Mucho kana → no dividir
        if proporcion_kana > 0.7:
            return False

    elif idioma in ["zh-cn", "ko"]:
        # Idiomas compactos
        if longitud < 20:
            return False
    else:
        # Idiomas latinos
        palabras = texto.split()

        # 🔴 pocas palabras → no dividir
        if len(palabras) < 6:
            return False

    return True


def unir_por_cada_duracion(segmentos, idioma):

    config = {
        "zh-cn": {"min_ms": 1200, "max_ms": 4000},
        "ja":    {"min_ms": 1400, "max_ms": 4200},
        "ko":    {"min_ms": 1400, "max_ms": 4200},
        "ru":    {"min_ms": 1600, "max_ms": 4500},
        "en":    {"min_ms": 1500, "max_ms": 4500},
    }

    conf = config.get(idioma, config["en"])
    
    resultado = []
    i = 0

    while i < len(segmentos):
        actual = segmentos[i]

        # 🟡 intentar fusionar si es muy corto
        while (actual["duracion"] < conf["min_ms"] and i + 1 < len(segmentos)):
            siguiente = segmentos[i + 1]

            combinado = fusionar(actual, siguiente)

            
            #Acá puse esto
            if idioma == "ru" and actual["duracion"] < 1200:
                break
            
            # 🔴 evitar pasarse del máximo
            if combinado["duracion"] > conf["max_ms"]:
                break

            actual = combinado
            i += 1

        resultado.append(actual)
        i += 1

    return resultado


silabas_debiles = [
        # Hiragana originales
        "ひ", "し", "つ", "ふ", "は", "へ", "ほ", "ん",
        # Consonantes sordas/fricativas adicionales
        "さ", "せ", "そ", "す",  # s-row
        "ち",  # ch
        "き", "け", "こ",  # k-row
        "た", "て", "と",  # t-row
        "ぎ", "げ", "ご",  # g-row
        "じ", "ぜ", "ず",  # z/j-row
        "ぴ", "ぺ", "ぽ", "ぱ",  # p-row
        # Katakana equivalentes
        "ヒ", "シ", "ツ", "フ", "ハ", "ヘ", "ホ",
        "サ", "セ", "ソ", "ス", "チ", "キ", "ケ", "コ",
        "タ", "テ", "ト", "ギ", "ゲ", "ゴ", "ジ", "ゼ", "ズ",
        "ピ", "ペ", "ポ", "パ"
    ]


def detectar_peligros_foneticos(frase, idioma):
    
    idioma_diferente_a_japones = idioma != "ja"
    sin_frase = not frase
    longitud = len(frase)
    kana_count = sum(1 for c in frase if is_hiragana(c) or is_katakana(c))
    proporcion_de_kanas = kana_count / longitud  if longitud > 0 else 0
    
    
    if idioma_diferente_a_japones or sin_frase:
        return False
    
    conteo_de_silabas = sum(1 for c in frase if c in silabas_debiles)
    

    if proporcion_de_kanas > 0.75:
        return True
    
    if conteo_de_silabas >= 3:
        return True
    
    if longitud > 20 and proporcion_de_kanas > 0.6:
        return True
    
    return False


def ajustar_pronunciacion_muy_sensible(frase, idioma, speed):
    if idioma != "ja" or not frase:
        return frase, speed

    sentence_length = len(frase)
    
    kana_count = sum(1 for c in frase if is_hiragana(c) or is_katakana(c))
    
    if sentence_length > 0:
        proporcion_kana = kana_count / sentence_length
    else:
        proporcion_kana = 0
    
    if proporcion_kana >= 0.80:
        speed *= 0.98
    
    speed = max(0.95, min(1.10, speed))
    
    return frase, speed


def ajustar_duracion_por_idioma(audio, duracion_objetivo_sub, idioma):
    """
    Ajusta la duración del audio respetando límites naturales por idioma.
    Evita cortes agresivos y mantiene la prosodia lo más estable posible.
    """
    
    config = IDIOMAS.get(idioma, {})
    
    duracion_actual = len(audio)

    if duracion_actual == 0:
        return audio

    if duracion_actual < 600:
        return audio

    # 🔵 Factor necesario
    ratio =  duracion_actual / duracion_objetivo_sub

    if 0.98 <= ratio <= 1.02:
        return audio
    
    #ESTO VA ACA ESTE MINICONTROL PARA NO COMPRIMIR INNECESARIAMENTE?
    if abs(duracion_actual - duracion_objetivo_sub) < 125:
        return audio
    
    
    min_ratio = config.get("min_ratio", 0.88)
    max_ratio = config.get("max_ratio", 1.15)

    max_compresion = config.get("max_compresion", 0.85)
    max_expansion = config.get("max_expansion", 1.15)

    margen_de_silencio = config.get("silencio_ms", 100)
    
    dentro_del_rango = min_ratio <= ratio <= max_ratio
    
    if dentro_del_rango:
        return audio
    
    audios_cortos = ratio < min_ratio
    

    
    if audios_cortos:
        faltante = duracion_objetivo_sub - duracion_actual
        
        #Lo limito para evitar pausas innecesarias
        faltante = min(faltante, margen_de_silencio * 3)
        
        return audio + AudioSegment.silent(duration=faltante)
    
    else:
        factor = duracion_objetivo_sub / duracion_actual
        factor = max(max_compresion, min(max_expansion, factor))
        nuevo_audio = audio._spawn(audio.raw_data, 
                                overrides={"frame_rate": int(audio.frame_rate * factor)}).set_frame_rate(audio.frame_rate)
        
        if len(nuevo_audio) > duracion_objetivo_sub:
            exceso = len(nuevo_audio) - duracion_objetivo_sub
            
            if exceso < 125:
                nuevo_audio = nuevo_audio.fade_out(exceso)
            else:
                nuevo_audio = nuevo_audio[:duracion_objetivo_sub]
    
    
    return nuevo_audio


def ajustar_naturalidad_por_idioma(idioma, speed, temperature, texto):
     """
     Ajustamos los parámetros y texto según el idioma para mejorar naturalidad,
     estabilidad fonética y reducir artefactos.
     """
     texto_ajustado = texto


     match idioma:
          case "ko":
               # Limitar velocidad (evita pérdida de consonantes)
               speed = min(speed, 1.15)
               # Limitar temperatura (evita inestabilidad)
               temperature = max(0.55, min(0.62, temperature))

               # Micro pausas
               texto_ajustado = texto_ajustado.replace(",", ", ")
               texto_ajustado = texto_ajustado.replace("  ", " ")
               texto_ajustado = texto_ajustado.replace("첫", "첫 번째 ")
               texto_ajustado = texto_ajustado.replace("두", "두 번째 ")
               texto_ajustado = texto_ajustado.replace("그", "그 ")

               reemplazos = {
                    "첫": "첫 ",   # uno
                    "두": "두 ",   # dos
                    "세": "세 ",   # tres
                    "네": "네 ",   # cuatro
                    "다섯": "다섯 ", # cinco
                    "여섯": "여섯 ", # seis
                    "일곱": "일곱 ", # siete
                    "여덟": "여덟 ", # ocho
                    "아홉": "아홉 ", # nueve
                    "열": "열 ",   # diez
                    }

               for k, v in reemplazos.items():
                    texto_ajustado = texto_ajustado.replace(k, v)

          case "ja":
              
            speed = max(1.00, min(1.08, speed))
            temperature = max(0.50, min(0.58, temperature))
            
            # Limpieza de puntuación japonesa
            texto_ajustado = texto_ajustado.replace("。.", "。")
            texto_ajustado = texto_ajustado.replace("。。", "。")
            texto_ajustado = texto_ajustado.replace("！！", "！")
            texto_ajustado = texto_ajustado.replace("？？", "？")
            
          case "zh-cn":
              # Separación ligera para mejorar claridad tonal
               speed = min(speed, 1.18)
               temperature = max(0.58, min(0.65, temperature))

               # Separación ligera para mejorar claridad tonal
               texto_ajustado = texto_ajustado.replace("，", "， ")
               texto_ajustado = texto_ajustado.replace("。", "。 ")
               
          case _:
               # Mantener estabilidad general
               speed = max(0.9, min(1.25, speed))
               temperature = max(0.55, min(0.70, temperature))

     return speed, temperature, texto_ajustado

#Una función para optimizar segmentación de subtítulos para no tener que recortar manualmente
#ESTAS FUNCIONES HACEN INTELIGENTEMENTE LA OPTIMIZACIÓN DEL AUDIO SEGÚN EL IDIOMA Y LA LONGITUD DE LA FRASE?
def evaluar(frase, duracion_sub_milisegundos, idioma):
     sin_duracion = duracion_sub_milisegundos <= 0
     longitud_de_la_frase = len(frase)
     
     if sin_duracion:
          return "invalido"
     
     match idioma:
     
          case "ja":
               caracteres_minimos = 8
               caracteres_maximos = 28
          case "zh-cn":
               caracteres_minimos = 6
               caracteres_maximos = 24
          case "ko":
               caracteres_minimos = 10
               caracteres_maximos = 30
          case _:
               caracteres_minimos = 12
               caracteres_maximos = 40
               
     if longitud_de_la_frase < caracteres_minimos:
          return "corto"
     elif longitud_de_la_frase > caracteres_maximos:
          return "largo"
     else:
          return "ideal"


PATRONES_PUNTUACION = {
    "zh-cn": r'[，。！？]',
    "ko": r'[.,!?]',
    "ru": r'[.,!?]',
    "default": r'[.,!?]'
}


def dividir(frase, idioma):
    if not frase:
        return []
    
    patrones = PATRONES_PUNTUACION.get(idioma, PATRONES_PUNTUACION["default"])
    partes = re.split(f"({patrones})", frase)

    resultado = []
    buffer = ""
    inc = 0
    
    while inc < len(partes):
        texto = partes[inc].strip()
        
        # Si hay puntuación justo después, la agregamos
        if inc + 1 < len(partes) and re.match(patrones, partes[inc + 1]):
            texto += partes[inc + 1]
            inc += 1
        
        if texto:
            # Regla general: si el fragmento es demasiado corto (<3 caracteres), no lo tratamos como bloque independiente
            if len(texto) < 3:
                buffer += " " + texto
            else:
                if buffer:
                    resultado.append(buffer.strip())
                    buffer = ""
                resultado.append(texto)
        
        inc += 1
    
    if buffer:
        resultado.append(buffer.strip())
    
    # Eliminar duplicados y fragmentos de 1 caracter
    resultado_final = []
    vistos = set()
    for r in resultado:
        if r not in vistos and len(r) > 1:
            resultado_final.append(r)
            vistos.add(r)
    
    return resultado_final


def fusionar(segmento_actual, segmento_siguiente):
    nueva_frase = f"{segmento_actual['texto']} {segmento_siguiente['texto']}".strip()
    
    nueva_duracion = segmento_siguiente["end"] - segmento_actual["start"]
    
    return {
        "texto": nueva_frase,
        "start": segmento_actual["start"],
        "end": segmento_siguiente["end"],
        "duracion": nueva_duracion
    }


def ajustar(lista_segmentos, idioma):
    resultado = []
    i = 0

    if not isinstance(lista_segmentos, list):
        raise ValueError("lista_segmentos debe ser una lista")

    while i < len(lista_segmentos):
        seg = lista_segmentos[i]
        
        if not isinstance(seg, dict):
            raise ValueError(f"Segmento inválido: {seg}")
        
        estado = evaluar(seg["texto"], seg["duracion"], idioma)

        if not seg["texto"].strip() or seg["duracion"] <= 0:
            i += 1
            continue

        
        if estado == "corto" and i < len(lista_segmentos) - 1:
            fusionado = fusionar(seg, lista_segmentos[i+1])
            resultado.append(fusionado)
            i += 2  # salta el siguiente porque ya se usó

        elif estado == "largo":
            
            if not conviene_dividir(seg, idioma):
                print(f"SKIP DIVISIÓN '{seg['texto'][:30]}'")
                resultado.append(seg)
                i += 1
                continue
            
            partes = dividir(seg["texto"], idioma)
            partes = [p for p in partes if len(p.strip()) >= 3]
            
            if not partes:
                resultado.append(seg)
                i += 1
                continue
            
            if len(partes) <= 1:
                resultado.append(seg)
                i += 1
                continue
            
            total_chars = sum(len(p) for p in partes)
            
            buffer = ""
            duracion_buffer = 0
            separador = " " if idioma != "ja" else ""
            
            # --- LA CLAVE: EL CURSOR DE TIEMPO ---
            tiempo_actual = seg["start"]
            
            for p in partes:
                
                if not p.strip():
                    continue
                
                proporcion = len(p) / total_chars
                duracion_real = seg["duracion"] * proporcion
                min_duracion = 600 if idioma == "ja" else 300
            
                if duracion_real < min_duracion:
                    buffer += separador + p
                    duracion_buffer += duracion_real
                    continue
                
                if buffer:
                    #CASO CON BUFER ACUMULADO
                    texto_final = buffer.strip() + separador + p
                    duracion_total = duracion_real + duracion_buffer 
                    
                    resultado.append({
                        "texto": texto_final.strip(),
                        "start": tiempo_actual,  # simplificado
                        "end": tiempo_actual + duracion_total,
                        "duracion": duracion_total
                    })
                    tiempo_actual += duracion_real # Avanzamos el cursor
                    buffer = ""
                    duracion_buffer = 0
                else:
                    #CASO NORMAL
                    resultado.append({
                        "texto": p.strip(),
                        "start": tiempo_actual,  # simplificado
                        "end": tiempo_actual + duracion_real,
                        "duracion": duracion_real
                    })
                    tiempo_actual += duracion_real # Avanzamos el cursor
            if buffer:
                resultado.append({
                        "texto": buffer.strip(),
                        "start": tiempo_actual,  # simplificado
                        "end": tiempo_actual + duracion_buffer,
                        "duracion": duracion_buffer
                    })
            i += 1
        else:
            resultado.append(seg)
            i += 1

    return resultado


def validar_segmentos(segmentos, idioma):
    """
    Limpia y valida segmentos antes de enviarlos al TTS.
    Elimina basura, corrige inconsistencias y evita errores silenciosos.
    
    """

    if not isinstance(segmentos, list):
        raise ValueError("segmentos debe ser una lista")

    resultado = []

    for i, seg in enumerate(segmentos):

        # 🔴 Validación estructural
        if not isinstance(seg, dict):
            print(f"⚠ Segmento inválido (no dict): {seg}")
            continue

        texto = seg.get("texto", "")
        duracion = seg.get("duracion", 0)
        start = seg.get("start", 0)
        end = seg.get("end", 0)

        # 🔴 Texto inválido
        if not isinstance(texto, str) or not texto.strip():
            print(f"⚠ Segmento descartado (texto vacío) idx={i}")
            continue

        texto = texto.strip()

        # 🔴 Duración inválida
        if not isinstance(duracion, (int, float)) or duracion <= 0:
            print(f"⚠ Segmento descartado (duración inválida) '{texto}'")
            continue

        # 🔴 Duración mínima por idioma
        min_duracion = 600 if idioma == "ja" else 300

        if duracion < min_duracion:
            print(f"⚠ Segmento muy corto descartado '{texto}' ({duracion:.1f} ms)")
            continue

        # 🔴 Evitar basura tipo solo puntuación
        if len(texto) <= 1:
            print(f"⚠ Segmento descartado (muy corto) '{texto}'")
            continue

        # 🔴 Evitar duplicados consecutivos
        if resultado and resultado[-1]["texto"] == texto:
            print(f"⚠ Segmento duplicado omitido '{texto}'")
            continue

        # 🟡 Corrección suave (japonés)
        if idioma == "ja":
            texto = texto.replace("、、", "、")

        # 🟢 Segmento válido
        resultado.append({
            "texto": texto,
            "start": start,
            "end": end,
            "duracion": duracion
        })

    return resultado


def detectar_peligros_de_desfasaje(frase):
    if not frase:
        return "alto"
    
    longitud = len(frase)
    
    # --- DETECCIÓN UNICODE ---
    hiragana = sum(1 for c in frase if is_hiragana(c))
    katakana = sum(1 for c in frase if is_katakana(c))
    # kanji = sum(1 for c in frase if '\u4e00' <= c <= '\u9fff')
    numeros = sum(1 for c in frase if c.isdigit())
    # puntuacion = sum(1 for c in frase if re.match(r'[、。！？,\.]', c))
    
    total = max(1, longitud)

    ratio_katakana = katakana / total
    ratio_hiragana = hiragana / total
    
    tiene_puntuacion = any(re.match(r'[、。！？,\.]', c) for c in frase)
    
    riesgo = 0
    
    if longitud > 35:
        riesgo += 2
        
    if not tiene_puntuacion:
        riesgo += 1
        
    if ratio_katakana > 0.4:
        riesgo += 2 #Va aumentando el riesgo de desfasaje si son prestamos
        
    if ratio_hiragana > 0.8:
        riesgo += 1 #Muy plana
        
    if numeros > 0:
        riesgo += 1
        
    if "・" in frase or "ー" in frase:
        riesgo += 1

    if longitud < 5:
        riesgo += 1

    # ---- clasificación final ----
    if riesgo >= 4:
        return "alto"
    elif riesgo >= 2:
        return "medio"
    else:
        return "bajo"


def calcular_temperature(frase, base, idioma=None):
    longitud = len(frase)

    if longitud > 120:
        return base  # sin variación
    
    if longitud < 50:
        variación = random.uniform(-0.05, 0.05)
    elif longitud < 100:
        variación = random.uniform(-0.04, 0.04)
    else:
        variación = random.uniform(-0.02, 0.02)


    signos = {
        "!": 0.02,
        "?": 0.02,
        ",": 0.01,
        "、": 0.01,
        ".": 0.015,
        "。": 0.015
    }

    for signo, peso in signos.items():
        if signo in frase:
            variación += peso
        

    # Ajuste leve por idioma (opcional)
    if idioma in ["ja", "zh-cn"]:
        variación *= 0.7  # más control
    elif idioma in ["es", "en", "pt"]:
        variación *= 1.0  # más flexibilidad

    temperature = base + variación

    # Clamp de seguridad
    temperature = max(0.4, min(0.8, temperature))

    return round(temperature, 3)

#Esta función se ha mejorado para una evaluación más precisa del peso de cada segmento, considerando no solo la longitud del texto, sino también la presencia de pausas y signos de puntuación específicos según el idioma. Esto permite una mejor sincronización entre el texto y el audio, logrando una narración más natural y fluida.
def calcular_peso_del_segmento(segmento):
    peso = len(segmento)
    
    texto = segmento.strip()
    
    textoAuxiliar = texto.replace("...", "")
    
    for signo, valor in PESO_SIGNOS.items():
        if signo != "...":
            peso += textoAuxiliar.count(signo) * valor
    
    peso += texto.count("...") * PESO_SIGNOS["..."] 
    
    último = segmento.strip()[-1]
    
    #Acá se evalúa si termina con un punto tanto occidental como oriental con el fin de ajustar la pausa mental y sonar mucho más humano.
    if último == "." or último == "。":
        peso *= 1.4
    elif último == "," or último == "、" or último == "，":
        peso *= 1.2
    elif último in ["!", "?", "！", "？"]:
        peso *= 1.3

    return peso


pausas = {
    ",": 120,     # pausa corta
    ".": 250,     # pausa media
    "!": 300,     # énfasis
    "?": 300,
    "،": 120,     # árabe
    "。": 250,    # japonés/chino
    "、": 120,
    "，": 120
}


def aplicar_pausas_naturales(frase, audio):
    resultado = AudioSegment.empty()
    segmentos = []
    buffer = ""
    
    #Este for separa los textos manteniendo los signos correspondientes del diccionario
    for char in frase:
        buffer += char
        if char in pausas:
            segmentos.append(buffer)
            buffer = ""
            
    if buffer:
        segmentos.append(buffer)
        
    #Acá se debe dividir los audios con el fin de mantener la fluidez
    duración_total = len(audio)
    
    pesos_mentales = [calcular_peso_del_segmento(seg) for seg in segmentos]
    
    suma_total_de_pesos = sum(pesos_mentales)
    
    inicio = 0
    
    #Este for recorre segmento por segmento
    for segmento, peso in zip(segmentos, pesos_mentales):
        
        duración_por_segmento = int((peso/ suma_total_de_pesos) * duración_total)
        
        fin = inicio + duración_por_segmento
        trozo = audio[inicio:fin] #El trozo guarda un audioSegment calculando el inicio hasta el fin
        resultado += trozo #El resultado concatena al trozo
        
        #Ahora hay que añadir pausas cuando corresponde
        if segmento.strip():
            último_carácter = segmento.strip()[-1]
            if último_carácter in pausas:
                silencio = AudioSegment.silent(duration=pausas[último_carácter])
                resultado += silencio
        
        inicio = fin
        
    #Acá evaluamos si el inicio es menor que la duración o longitud del audio.
    #ESTÁ BIEN QUE HAYA PUESTO ACÁ ANTES DE DEVOLVER EL RESULTADO?
    if inicio < len(audio):
        resultado += audio[inicio:]
        
    return resultado