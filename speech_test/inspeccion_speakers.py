import torch, os
from pydub import AudioSegment
from TTS.api import TTS
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import XttsAudioConfig, XttsArgs
from TTS.config.shared_configs import BaseDatasetConfig
from TTS.tts.utils.speakers import SpeakerManager
from TTS.tts.utils.text.tokenizer import TTSTokenizer
from TTS.utils.audio import AudioProcessor
from transformers import AutoTokenizer


tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
torch.set_num_threads(os.cpu_count() or 8)


torch.serialization.add_safe_globals([
    XttsConfig,
    XttsAudioConfig,
    BaseDatasetConfig,
    XttsArgs,
    SpeakerManager,
    TTSTokenizer,
    AudioProcessor
])


cpu_cores = os.cpu_count()
if cpu_cores:
    torch.set_num_threads(cpu_cores)
    print(f"Hilos de Torch configurados en: {cpu_cores}")
else:
    torch.set_num_threads(4) # Valor seguro por defecto

modelo = "tts_models/multilingual/multi-dataset/xtts_v2"
tts = TTS(model_name=modelo, progress_bar=True)
tts.to("cpu")

idioma = "en"
oración = "Hello everyone, I want to share with you that I graduated as a systems analyst, and I feel satisfied with my greatest achievement."
salida_del_archivo = "mi voz inglesa.wav"
referencia_speaker = "romance_clean.wav"

def generar_oración(tts, oración, idioma, salida, speaker, 
                    velocidad_base=1.00,
                    temperature= 0.60,
                    repetition_penalty=2.0,
                    factor_min=0.92,
                    factor_max=1.10):


    tts.tts_to_file(
        text=oración,
        file_path=salida,
        language=idioma,
        speaker_wav=speaker, 
        temperature=temperature, 
        speed=velocidad_base, 
        repetition_penalty=repetition_penalty
    )

    audio = AudioSegment.from_wav(salida_del_archivo)
    duración_audio = len(audio)
    duración_oración = len(oración) * 60

    factor = duración_oración / duración_audio
    factor = max(factor_min, min(factor_max, factor))
    nueva_velocidad = max(0.90, min(1.15, factor * velocidad_base))

            
            
    if abs(factor - 1) > 0.03:
        tts.tts_to_file(text=oración,
                        file_path=salida,
                        language=idioma,
                        speaker_wav=speaker,
                        temperature=temperature,
                        speed=nueva_velocidad,
                        repetition_penalty=repetition_penalty
                        )
    
    if len(audio) < duración_oración:
        audio += AudioSegment.silent(duration=duración_oración - len(audio))
    else:
        audio = audio[:duración_oración]
    print(f"[{idioma}] Texto: {oración}")
    print(f"Velocidad final usada: {round(nueva_velocidad, 3)}")
        

generar_oración(
    tts,
    oración,
    idioma,
    salida_del_archivo,
    referencia_speaker
    )