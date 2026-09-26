import unicodedata, json
from pathlib import Path



def normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto) 
        if unicodedata.category(c) != 'Mn').lower()

#¿Qué hace específicamente el BASE_DIR?
BASE_DIR = Path(__file__).resolve().parent
ARCHIVO_JSON = BASE_DIR / "idiomas.json"

with ARCHIVO_JSON.open("r", encoding="utf-8") as f:
    CONFIG = json.load(f)

IDIOMAS = CONFIG["idiomas"]
PERFILES = CONFIG["perfiles_familia_linguistica"]

DEBUG_NECESARIO = True

def debug_log(idioma, mensaje_importante):
    if DEBUG_NECESARIO:
        print(f"[{idioma.upper()}] {mensaje_importante}")


def normalizar_idioma(idioma):
    if idioma in IDIOMAS:
        return idioma
    
    idioma_normalizado = normalizar(idioma)
    
    for codigo, datos in IDIOMAS.items():
        if normalizar(datos["nombre"]) == idioma_normalizado:
            return codigo
        
    return idioma


def safe_duration(duracion_audio):
    return duracion_audio if duracion_audio > 0 else 1


def obtener_perfil(idioma):
    
    if idioma not in IDIOMAS:
        return None
    
    perfil_familia = PERFILES[idioma]["familia"]
    
    if perfil_familia not in PERFILES:
        return None
    
    return PERFILES[perfil_familia]


def adaptar_texto_segun_idioma(idioma, frase):
    frase = frase.strip()
    frase = frase.replace("\n", " ")
    
    # Primero, normalizamos el idioma para asegurarnos de que coincida con las claves del diccionario
    #Esto vale igual la pena tener el idioma_nombre?
      
    código_idioma = normalizar_idioma(idioma)

    familia = IDIOMAS[idioma]["familia"]
    
    
    match familia:
        case "romance":
            
            frase = frase.replace("...", ".")
            frase = frase.replace(" - ", ", ")

        case "germánico":
            
            frase = frase.replace("and", ",")
            frase = frase.replace("...", ".")
            frase = frase.replace("und", ",")
            frase = frase.replace(" - ", ", ")
            
            
        case "asiático":
            
            frase = frase.replace(",", "、")
            frase = frase.replace(".", "。")
            frase = frase.replace("?", "？")
            frase = frase.replace("!", "！")
            
        case "eslavo":
            
            frase = frase.replace(" y ", " и ")
            frase = frase.replace("...", ".")
            frase = frase.replace(" - ", ", ")
            
    
    if código_idioma == 'zh-cn':
        frase = frase.replace("、", "，")  # Elimina espacios para japonés y chino
 
    
    if código_idioma == 'ja':
        frase = frase.replace("，", "、")  # Elimina espacios para japonés y chino
 
    if código_idioma == 'ko':
        frase = frase.replace("。", ".")
    
    if código_idioma not in IDIOMAS:
        return frase.strip()
    
    return frase.strip()

#Esta función sirve para simplificar el texto a algo más corto
def simplificar_texto_segun_idioma(idioma, frase):
    
    if len(frase) <= 80:
        return frase
    
    
    # --- IDIOMAS ESLAVOS (ruso) ---
    if idioma == "ru":
        frase = frase.replace(" который ", " ")
        frase = frase.replace(" которые ", " ")
        frase = frase.replace(" потому что ", " ")
        frase = frase.replace(" и ", ", ")

        partes = frase.split(",")
        if len(partes) > 2:
            frase = ", ".join(partes[:2])

    # --- ROMANCE (español, portugués) ---
    elif idioma == "es":
        frase = frase.replace(" que ", " ")
        frase = frase.replace(" y ", ", ")

        partes = frase.split(",")
        if len(partes) > 2:
            frase = ", ".join(partes[:2])

    # --- GERMÁNICO (inglés) ---
    elif idioma == "en":
        frase = frase.replace(" and ", ", ")
        frase = frase.replace(" which ", " ")

        partes = frase.split(",")
        if len(partes) > 2:
            frase = ", ".join(partes[:2])

    # --- ASIÁTICOS (ja, zh-cn, ko) ---
    elif idioma in ["ja", "zh-cn", "ko"]:
        # ⚠️ No eliminar palabras, solo dividir mejor

        # Normalizar separadores
        frase = frase.replace("。", "。|")
        frase = frase.replace("、", "、|")
        frase = frase.replace("，", "，|")

        partes = frase.split("|")
        
        if len(partes) > 2:
            frase = "".join(partes[:2])

        
        frase = frase.replace("|", "")
    
    #Acá pondré la lógica de limpieza de espacios
    frase = " ".join(frase.split())
    
    return frase.strip() #Que pasaría si la frase no tuviera un strip? Seguro se va a desfasar artefactando de manera rara