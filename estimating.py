import re, naturalization

def termina_en_pausa_suave(texto):
    return texto.strip().endswith(",") or texto.strip().endswith("—")


def es_fragmento_debil(segmento, idioma):
    if idioma != "ru":
        return False

    segmento = segmento.strip()
    palabras = segmento.lower().split()

    conectores = {"и", "но", "а", "или", "да", "либо", "зато", "однако"}
    preposiciones = {"в", "на", "с", "к", "по", "из", "у", "о", "об", "за", "для", "под", "без", "при"}
    particulas = {"же", "ли", "бы", "вот", "уж", "то"}

    # 1. termina en coma
    if idioma == "ru" and segmento.endswith(","):
        return True
    
    # 2. una sola palabra débil
    if len(palabras) == 1:
        return palabras[0] in conectores or palabras[0] in preposiciones or palabras[0] in particulas

    # 3. dos palabras pero empieza con preposición
    if len(palabras) == 2:
        if palabras[0] in preposiciones:
            return True
        
    if len(palabras) <= 3:
        return True

    return False


def debe_unirse(actual, siguiente, idioma):

    conf = {}
    
    if idioma != "ru":
        return False

    texto = actual["texto"]

    # 🟣 PRIORIDAD 1: pausa natural (coma, guion)
    if termina_en_pausa_suave(texto):
        duracion_total = siguiente["end"] - actual["start"]
        return duracion_total <= conf["max_ms"] * 1.15

    # 🔴 PRIORIDAD 2: fragmento débil
    if not es_fragmento_debil(texto, idioma):
        return False

    # 🟡 control de duración
    duracion_total = siguiente["end"] - actual["start"]

    if duracion_total > conf["max_ms"]:
        return False
    
    return True


def unir_fragmentos_debiles_dict(segmentos, idioma):

    resultado = []
    i = 0

    while i < len(segmentos):
        actual = segmentos[i]

        if i + 1 < len(segmentos):
            siguiente = segmentos[i + 1]

            if debe_unirse(actual, siguiente, idioma):
                combinado = naturalization.fusionar(actual, siguiente)
                resultado.append(combinado)
                i += 2
                continue

        resultado.append(actual)
        i += 1

    return resultado


def repartir_duracion_de_cada_fragmento(segmentos, duracion_total, idioma):
    print("segmentos:", segmentos)
    print("duracion_total:", duracion_total, type(duracion_total))
    
    pesos = [naturalization.calcular_peso_del_segmento(segmento) for segmento in segmentos]
    
    total_de_peso = sum(pesos)

    print("pesos:", pesos)
    print("total_de_peso:", total_de_peso, type(total_de_peso))
    

    duraciones = [round((duracion_total * peso)/ total_de_peso) for peso in pesos]

    diferencia = duracion_total - sum(duraciones)
    duraciones[-1] += diferencia
    
    return duraciones
    

def segmentar_texto(texto, idioma):
    """
    Divide el texto en segmentos equilibrados según idioma y duración.
    """

    # 🔧 Configuración por idioma
    config = {
        "zh-cn": {"split_coma": True,  "min_ms": 1200, "max_ms": 4000},
        "ja":    {"split_coma": False,  "min_ms": 1400, "max_ms": 4200},
        "ko":    {"split_coma": True,  "min_ms": 1400, "max_ms": 4200},
        "ru":    {"split_coma": False, "min_ms": 1600, "max_ms": 4500},
        "en":    {"split_coma": True,  "min_ms": 1500, "max_ms": 4500},
    }

    conf = config.get(idioma, config["en"])

    # 🧩 1. Separar por puntuación fuerte
    partes = re.split(r'(?<=[.!?。！？])', texto)

    segmentos = []

    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue

        # 🟡 2. División secundaria por comas (según idioma)
        if conf["split_coma"]:
            subpartes = re.split(r'[，,]', parte)
        else:
            subpartes = [parte]

        buffer = ""

        for sub in subpartes:
            sub = sub.strip()
            if not sub:
                continue

            candidato = (buffer + " " + sub).strip() if buffer else sub

            # 📏 estimar duración
            duracion_estimada = predecir_duracion_texto(candidato, idioma)
            
            #¿Esto me puede tirar error silencioso a la hora de narrar?
            if duracion_estimada <= conf["max_ms"]:
                buffer = candidato
            else:
                if buffer:
                    segmentos.append(buffer)
                buffer = sub

        if buffer:
            segmentos.append(buffer)

    # 🔵 3. Post-procesado: unir segmentos muy cortos
    segmentos_finales = []
    buffer = ""

    for seg in segmentos:
        dur = predecir_duracion_texto(seg, idioma)

        if dur < conf["min_ms"]:
            buffer = (buffer + " " + seg).strip()
        else:
            if buffer:
                segmentos_finales.append(buffer)
                buffer = ""
            segmentos_finales.append(seg)

    
    if buffer:
        segmentos_finales.append(buffer)

    segmentos_finales = unir_fragmentos_debiles_dict(segmentos_finales, idioma) #ACÁ LE COLOQUÉ COMO ME PEDISTE EN EL LUGAR CORRESPONDIENTE.
    #SIEMPRE ESTÁ DESPUÉS DE SEGMENTACIÓN BASE
    
    
    return segmentos_finales


# --------------------------------------------------------------
# --------------------------------------------------------------
# --------------------------------------------------------------


def contar_caracteres_utiles(texto):
    return len(re.sub(r"[^\w\u4e00-\u9fff]", "", texto))


def predecir_duracion_texto(texto, idioma):
    """
    Estima duración en ms según idioma.
    """
    
    # Factores base (ms por unidad)
    config = {
        "es":    {"unidad": "word", "ms": 295},
        "en":    {"unidad": "word", "ms": 280},
        "zh-cn": {"unidad": "char", "ms": 260},
        "ja":    {"unidad": "char", "ms": 250},
        "ko":    {"unidad": "char", "ms": 180},
        "pt":    {"unidad": "word", "ms": 290},
        "fr":    {"unidad": "word", "ms": 300},
        "de":    {"unidad": "word", "ms": 310},
        "de-ch": {"unidad": "word", "ms": 315},
        "nl":    {"unidad": "word", "ms": 295},
        "it":    {"unidad": "word", "ms": 285},
        "ru":    {"unidad": "word", "ms": 260},
        "ar":    {"unidad": "word", "ms": 305},
        }


    pausa_ms = {
        "es":    110,
        "en":    100,
        "zh-cn": 85,
        "ja":    180,
        "ko":    90,
        "pt-br": 110,
        "fr":    120,
        "de":    110,
        "de-ch": 110,
        "nl":    105,
        "it":    105,
        "ru":    70,
        "ar":    100,
    }


    conf = config.get(idioma, {"unidad": "word", "ms": 300})

    peso = naturalization.calcular_peso_del_segmento(texto)

    duracion = peso * (conf["ms"] / 10)
    
    duracion += naturalization.contar_pausas(texto, idioma) * pausa_ms.get(idioma, 100) #ACÁ PROGRAMÉ LA FUNCIÓN
    
    
    
    return duracion


def evaluar_ajuste_previo(texto, idioma, duracion_sub):
    """
    Compara duración estimada vs duración real del subtítulo.
    """

    estimada = predecir_duracion_texto(texto, idioma)

    if duracion_sub == 0:
        return 1.0

    ratio_previo = estimada / duracion_sub

    if idioma == "zh-cn":
        ratio_previo = 1.25  # 👈 clave
    
    if not duracion_sub:
        return 1.0
    
    return ratio_previo


def ajustar_speed_por_prediccion(speed, ratio_previo):

    factor = max(0.90, min(1.10, ratio_previo))
    speed *= factor
    
    return speed


def ajustar_factor_complejidad(frase, idioma):
    longitud = len(frase)

    if longitud > 80:
        return 0.97
    elif longitud < 30:
        return 1.02

    return 1.0


def limpiar_puntuacion(texto, idioma):

    texto = texto.strip()

    # 🔴 primero lógica por idioma
    if idioma == "ru":
        texto = re.sub(r"[«»]", "", texto)
        texto = re.sub(r"\.\s+", ", ", texto)
        texto = texto.replace("—", ",")

    elif idioma == "en":
        texto = re.sub(r"[-–—]", ",", texto)

    elif idioma in ["zh-cn", "ja", "ko"]:
        texto = re.sub(r"[-–—]", "，", texto)

    # 🔵 después limpieza general
    texto = re.sub(r'\s+', ' ', texto)
    texto = re.sub(r"\s+([.,!?])", r"\1", texto)
    texto = re.sub(r"\.{2,}", ".", texto)
    texto = re.sub(r"\.\s*$", "", texto)

    return texto.strip()

#Esta función la programé para normalizar el texto antes de narrar, quitando espacios innecesarios y uniformando la puntuación según el idioma. Los signos como . o , ayudan a la naturalización y a la predicción de duración, pero a veces pueden venir con espacios raros o en formatos no estándar, así que esta función los limpia para que el pipeline funcione mejor. Además ayuda a no leer signos de puntuación como palabras sueltas, lo que puede arruinar la predicción de duración y la entonación. Es un paso clave para mejorar la calidad final de la narración.
def normalizar_texto_para_tts(texto, idioma):
    
    texto = texto.strip()

    # quitar dobles espacios
    texto = re.sub(r'\s+', ' ', texto)

    # uniformar puntuación
    texto = texto.replace(" ,", ",").replace(" .", ".")
    
    texto = limpiar_puntuacion(texto, idioma)
    
    return texto

#Esta función se adapta la puntuación para sonar más natural y cercano a la percepción humana, especialmente en ruso donde las pausas fuertes pueden sonar muy rígidas.Al convertir algunas de esas pausas fuertes en suaves, el resultado final puede sentirse más fluido y menos robótico, lo que es crucial para la calidad de la narración. Además, al eliminar símbolos raros como guiones largos, se evita que el TTS los interprete de manera extraña, lo que también contribuye a una narración más natural y agradable al oído.
def adaptar_puntuacion_para_naturalizacion(texto, idioma):

    if idioma == "ru" and len(texto.split()) <= 6:
        # 🔹 mantener puntos, pero asegurar espacio correcto
        texto = re.sub(r"\.\s*", ". ", texto)

        # 🔹 comas limpias
        texto = re.sub(r"\s*,\s*", ", ", texto)

        # 🔹 guiones a pausa natural
        texto = texto.replace("—", " — ")

        if texto.endswith("."):
            texto = texto[:-1]
        
    # 🔹 limpieza final universal
    texto = re.sub(r"\s+", " ", texto).strip()


    return texto.strip()