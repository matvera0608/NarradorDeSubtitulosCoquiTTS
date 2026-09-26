def enriquecer_segmento(seg, idioma):
    params = {
        "pause_ms": 0,
        "emotion": "neutral"
    }

    if "?" in seg:
        params["emotion"] = "question"
        params["pause_ms"] = 120

    elif "!" in seg:
        params["emotion"] = "emphasis"
        params["pause_ms"] = 80

    elif seg.endswith(","):
        params["pause_ms"] = 60

    return params


def aplicar_silencio(audio, ms):
    silencio = generar_silencio(ms)
    return audio + silencio