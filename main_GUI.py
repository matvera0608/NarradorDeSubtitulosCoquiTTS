##CREÉ UN ARCHIVO LLAMADO main_GUI.py para armar la GUI con el fin de trabajar de manera más cómoda y más visible
import threading, os, pysrt
from customtkinter import CTkButton, CTkLabel, CTkOptionMenu, filedialog
import customtkinter as ctk
from tkinter import Menu
from tkinterdnd2 import DND_FILES, TkinterDnD
import re, traceback, narrador_de_subtítulos

#Esta clase pertenece a la interfaz gráfica actual
class MainGUI(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("Narrador de subtítulos PRO")
        self.resizable(False, False)
        # Configurar tema global
        self.configure(bg="black")
        
        # Definición de paleta
        color_bg = ("white", "black")
        
        barra_de_menú = Menu(self)
        
        marco_opciones = ctk.CTkFrame(self)
        marco_opciones.pack(pady=15)
        
       
        self.status_label = CTkLabel(self, text="Esperando archivo...")
        self.status_label.pack(pady=10)
        
        
        self.textBox = ctk.CTkTextbox(self, width=600, height=600, fg_color=color_bg, text_color="white") # type: ignore
        
        self.textBox.pack(pady=10)
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self.on_drop)
        self.textBox.bind("<Control-s>", self.guardar_srt)
        
        menú_archivo = Menu(barra_de_menú, tearoff=0)
        barra_de_menú.add_cascade(label="Archivo", menu=menú_archivo)
        
        menú_archivo.add_command(label="Abrir", command=self.seleccionar_srt)
        menú_archivo.add_separator()
        menú_archivo.add_command(label="Salir", command=self.quit)
        
        
        self.config(menu=barra_de_menú)
        
        
        self.label = CTkLabel(marco_opciones, text="Elige el idioma ")
        self.label.grid(row=0, column=0, padx=5)
        
        
        self.idioma_menu = CTkOptionMenu(marco_opciones, values=narrador_de_subtítulos.mapear_nombres_de_idiomas())
        self.idioma_menu.grid(row=0, column=1, padx=5)
        
        
        self.label = CTkLabel(marco_opciones, text="Referencia ")
        self.label.grid(row=0, column=0, padx=5)
        

        
        
        self.button = CTkButton(self, text="Narrar subtítulo", command=self.narrar)
        self.button.pack(pady=10)
    
    
    def on_drop(self, event):
        file_paths = self.tk.splitlist(event.data)
        for path in file_paths:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    contenido = f.read()
                    
                validación_del_srt = re.search(r"\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}", contenido)
                
                if not validación_del_srt:
                    self.status_label.configure(text="❌ El archivo no parece ser un subtítulo SubRip válido")
                    self.srt_path = None
                else:
                    self.status_label.configure(text="✔ El archivo es válido y está preparado para narrar")
                    self.srt_path = path
                    
                self.textBox.delete("1.0", "end")
                self.textBox.insert("end", contenido)
            except Exception as e:
                self.textBox.insert("end", f"Error al abrir {path}: {e}\n")
                self.srt_path = None
    
    def guardar_srt(self, event=None):
        self.editar_srt_desde_TextBox()
    
    def seleccionar_srt(self):
        archivo = filedialog.askopenfilename(filetypes=[("SubRip", "*.srt"), ("Texto", "*.txt")])
        
        if archivo:
            self.archivo_seleccionado = archivo #Acá está bien entonces
            with open(archivo, "r", encoding="utf-8") as f:
                contenido = f.read()
                
                validación_del_srt = re.search(r"\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}", contenido)
                
                if not validación_del_srt:
                    self.status_label.configure(text="❌ El archivo no parece ser un subtítulo SubRip válido", text_color="red")
                    self.srt_path = None  # Limpiar la ruta si el archivo no es válido
                else:
                    self.status_label.configure(text="✔ El archivo es válido y está preparado para narrar", text_color="green")
                    self.srt_path = archivo
                    
                self.textBox.delete("1.0", "end")
                self.textBox.insert("1.0", contenido)
                
    def editar_srt_desde_TextBox(self):
        try:
            contenido_editado = self.textBox.get("1.0", "end-1c").strip()
            if not contenido_editado:
                self.status_label.configure(text="❌ No hay contenido para guardar")
                return

            if hasattr(self, "srt_path") and self.srt_path:
                with open(self.srt_path, "w", encoding="utf-8") as f:
                    f.write(contenido_editado)
                self.status_label.configure(text=f"✔ Subtítulo reemplazado", text_color="green")
            else:
                self.status_label.configure(text="❌ No hay archivo original para reemplazar", text_color="red")
        except Exception as e:
            self.status_label.configure(text=f"❌ Error al guardar: {e}", text_color="red")
   
    def narrar(self):
        if not hasattr(self, "srt_path") or self.srt_path is None:
            self.status_label.configure(text="❌ No se seleccionó ningún subtítulo")
            return
    
        # aquí tu lógica de narración usando self.srt_path
        self.status_label.configure(text=f"Narrando subtítulo: {self.srt_path}")
        self.button.configure(state="disabled")
        threading.Thread(target=self._narrar_thread, daemon = True).start()
        
    def _narrar_thread(self):
        try:
            self.procesar_narracion_en_tiempo_real()
        finally:
            # Reactivar el botón desde el hilo principal
            self.after(0, lambda: self.button.configure(state="normal"))
        
    def procesar_narracion_en_tiempo_real(self):
        idioma_gui = self.idioma_menu.get()
        idioma_actual = idioma_gui 
        código_idioma = narrador_de_subtítulos.obtener_codigo_por_nombre(idioma_actual)
        
        print(f"Idioma enviado al TTS: {código_idioma}") #Acá le puse el verificador
        
        
        if código_idioma not in narrador_de_subtítulos.IDIOMAS:
            self.after(0, lambda: self.status_label.configure(text="❌ Idioma inválido", text_color="red"))
            return

        archivo = getattr(self, "archivo_seleccionado", None)  # recuperás lo que guardaste

        if not archivo:
            self.after(0, lambda: self.status_label.configure(text="❌ No se seleccionó ningún archivo"))
            return
        try:
            # Supongamos que usás pysrt para leer subtítulos
            subs = pysrt.open(archivo, encoding="utf-8")
            nombre_archivo, _ = os.path.splitext(os.path.basename(archivo))
            
            self.after(0, lambda: self.status_label.configure(text="🎙 Narrando..."))
            for incremento, sub in enumerate(subs):
                duración_sub = narrador_de_subtítulos.speechear_por_cada_duracion(código_idioma, sub, nombre_archivo) #speaker_limpio le pasé como parámetro.
                duracion_ms = len(duración_sub) if duración_sub else None #type: ignore
                if duración_sub is not None:
                    if incremento % 2 == 0:
                        self.after(4000, lambda d = duracion_ms, lang=idioma_actual: self.status_label.configure(text=f"duración: {d/1000:.2f} segundos")) #type: ignore
                        self.after(2500, lambda: self.status_label.configure(text="🎙 Narrando..."))
                else:
                    print("⚠ No se pudo calcular duración del subtítulo")
            self.after(0, lambda: self.status_label.configure(text="✅ Narración finalizada", text_color="green"))

        except Exception as e:
            self.after(0, lambda exc= e: self.status_label.configure(text=f"⚠ Error al narrar: {exc}", text_color="red"))
            traceback.print_exc()
    
#Este if se encarga de manejar mejor el flujo y que el archivo se ejecute cuando corre directamente con el fin de tener un flujo de trabajo limpio y también evitar posibles ejecuciones no deseadas
if __name__ == "__main__":
    app = MainGUI()
    app.mainloop()