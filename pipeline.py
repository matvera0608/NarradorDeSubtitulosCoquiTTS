import narrador_de_subtítulos, estimating
import os


def pipeline_tts(texto, idioma, perfil, carpeta, duracion_sub, sub_id=None, start=None, end=None):
     
     texto = estimating.normalizar_texto_para_tts(texto, idioma)

     texto = estimating.adaptar_puntuacion_para_naturalizacion(texto, idioma)

     segmentos = estimating.segmentar_texto(texto, idioma)

     segmentos = estimating.unir_fragmentos_debiles_dict(segmentos, idioma)

     duraciones = estimating.repartir_duracion_de_cada_fragmento(segmentos, duracion_sub, idioma)

     resultados = []
     
     for i, (seg, duracion_seg) in enumerate(zip(segmentos, duraciones)):
          
          speed = perfil["speed"]  # Velocidad base del perfil
          temp = perfil["temperature"]    # Temperatura base del perfil
     
          
          tipo = analizar_entonacion(seg)
          
          match tipo:
               case "pregunta":
                    speed *= 0.98  # Ligeramente más lento para preguntas
                    temp += 0.05   # Un poco más creativo para preguntas
               case "enfasis":
                    speed *= 1.05  # Ligeramente más rápido para énfasis
                    temp += 0.08   # Más creativo para énfasis
               case "pausa":
                    speed *= 0.98  # Ligeramente más lento para pausas
                    temp += 0.02   # Un poco más creativo para pausas
               case _:
                    pass  # Sin cambios para texto neutral
          
          speed, temp = narrador_de_subtítulos.ajustar_parametros_finales(idioma, speed, temp, seg)

          file_path = os.path.join(carpeta, f"{sub_id}_{start}_{end}_{i + 1}.wav")

          audio = narrador_de_subtítulos.generar_con_retry(
          seg,
          idioma,
          perfil,
          file_path,
          duracion_seg,
          speed,
          temp,
          seg_id=i+1
          )
          
          resultados.append(audio)

     # print("Segmentos generados:")
     # for s in segmentos:
     #      print(repr(s))
     
     # print("\nAudios generados:")
     # for i, audio in enumerate(resultados):
     #      print(i, audio is not None)
     
     return resultados

def analizar_entonacion(texto):

    texto = texto.strip()

    if texto.endswith("?") or texto.startswith("¿"):
        return "pregunta"

    if texto.endswith("!") or texto.startswith("¡"):
        return "enfasis"

    # SOLO pausas suaves reales
    if "—" in texto or "," in texto or "，" in texto:
        return "pausa"

    return "neutral"