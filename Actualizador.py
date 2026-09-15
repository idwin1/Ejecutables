import truststore
truststore.inject_into_ssl()
import os
import sys
import requests
import subprocess
import json

LIBRERIAS_REQUERIDAS = {
    "colorama": "colorama"
}

def verificar_e_instalar_librerIAS():
    for import_name, pip_name in LIBRERIAS_REQUERIDAS.items():
        try:
            __import__(import_name)
        except ImportError:
            print(f"[!] La librería '{import_name}' no está instalada.")
            print(f"[+] Instalando '{pip_name}' automáticamente en segundo plano...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
                print(f"[✔] '{pip_name}' instalada con éxito.\n")
            except Exception as e:
                print(f"[❌] Error crítico al intentar instalar {pip_name}: {e}")
                sys.exit(1)

verificar_e_instalar_librerIAS()

from colorama import init, Fore, Style

init(autoreset=True)
REPO_OWNER = "idwin1"
REPO_NAME = "Ejecutables"
RAMA = "main"

def obtener_ruta_apps_real():
    """Detecta con precisión la carpeta física real donde reside este ejecutable de forma externa"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.argv[0]))
    else:
        return os.path.dirname(os.path.abspath(__file__))

# El actualizador vive dentro de 'apps', por ende BASE_DIR es la carpeta 'apps'
BASE_DIR = obtener_ruta_apps_real()

def resolver_ruta_local(ruta_github):
    """Calcula la ruta exacta forzando las descargas a la carpeta local 'apps'"""
    nombre_archivo = os.path.basename(ruta_github)
    
    # Regla 1: El menú va a apps/Menu_NUEVO.exe
    if nombre_archivo == "Menu.exe":
        return os.path.join(BASE_DIR, "Menu_NUEVO.exe")
    # --- NUEVA REGLA 2: El actualizador se guarda como temporal ---
    if nombre_archivo.lower() == "actualizador.exe":
        return os.path.join(BASE_DIR, "actualizador_NUEVO.exe")
    
    # Regla 3: Todo LO DEMÁS cae directamente dentro de tu carpeta local 'apps'
    return os.path.join(BASE_DIR, nombre_archivo)

# -------------------------------------------------------------------------
# CARGA DE CONFIGURACIÓN SEGURA
# -------------------------------------------------------------------------
CONFIG_FILE  = os.path.join(BASE_DIR, "config.json")

def cargar_configuracion():
    if not os.path.exists(CONFIG_FILE):
        # Si no existe, creamos una estructura inicial básica para evitar crasheos
        default_config = {"Ultimo_Commit": {"commit": ""}}
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=4)
            return default_config
        except Exception:
            sys.exit(1)
        
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(Fore.RED + f"[❌] Error al cargar la configuración: {e}")
        sys.exit(1)

# --- MODIFICACIÓN 1: Añadir el parámetro a la función ---
def guardar_ultimo_commit(nuevo_commit, actualizar_menu_estado=False, actualizar_actualizador_estado=False):
    try:
        datos = cargar_configuracion()
        if "Ultimo_Commit" not in datos or not isinstance(datos["Ultimo_Commit"], dict):
            datos["Ultimo_Commit"] = {}
        datos["Ultimo_Commit"]["commit"] = nuevo_commit
        
        # Si se descargó un nuevo menú
        if actualizar_menu_estado:
            datos["Estado_Menu"] = 1
            
        # Si se descargó un nuevo actualizador
        if actualizar_actualizador_estado:
            datos["Estado_Actualizador"] = 1
        
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(Fore.RED + f"[⚠️] No se pudo actualizar el commit en el JSON: {e}")

config_datos = cargar_configuracion()

def actualizar_solo_cambios():
    print("Verificando actualizaciones y la integridad de las carpetas...")
    url_commit = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/commits/{RAMA}"
    headers = {'User-Agent': 'request'}
    
    try:
        response = requests.get(url_commit, headers=headers, timeout=5)
        if response.status_code != 200:
            print(f"Error al conectar con GitHub: {response.status_code}")
            return
            
        sha_remoto = response.json()["sha"]
        sha_local = config_datos.get("Ultimo_Commit", {}).get("commit", "")
        
        # --- VERIFICAR ARCHIVOS FÍSICOS FALTANTES ---
        url_tree = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/git/trees/{sha_remoto}?recursive=1"
        res_tree = requests.get(url_tree, headers=headers, timeout=5)
        
        archivos_faltantes = []
        if res_tree.status_code == 200:
            tree_data = res_tree.json()
            archivos_en_repo = [item["path"] for item in tree_data.get("tree", []) if item["type"] == "blob"]
            
            for archivo in archivos_en_repo:
                # CORRECCIÓN CRÍTICA: No busques Menu.exe como "faltante" en apps de forma física,
                # ya que Menu.exe vive en la raíz. Solo debe bajarse si viene en el historial de cambios.
                if os.path.basename(archivo).lower() == "menu.exe":
                    continue
                    
                ruta_local = resolver_ruta_local(archivo)
                if not os.path.exists(ruta_local):
                    archivos_faltantes.append(archivo)

        # --- VERIFICAR CAMBIOS POR HISTORIAL ---
        archivos_actualizados = []
        archivos_eliminados = []
        hay_nuevo_commit = (sha_remoto != sha_local)
        
        if hay_nuevo_commit:
            print(f"Nueva versión detectada: {sha_remoto[:7]}")
            url_cambios = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/compare/{sha_local}...{sha_remoto}" if sha_local else f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/commits/{sha_remoto}"

            res_cambios = requests.get(url_cambios, headers=headers, timeout=5)
            if res_cambios.status_code == 200:
                archivo_list = res_cambios.json().get("files", []) if sha_local else res_cambios.json().get("commit", {}).get("tree", {})
                
                if sha_local:
                    for archivo in archivo_list:
                        if archivo["status"] in ["modified", "added"]:
                            archivos_actualizados.append(archivo["filename"])
                        elif archivo["status"] == "removed":
                            archivos_eliminados.append(archivo["filename"])
                else:
                    # Si el JSON no tiene commit previo, bajamos el menú por primera vez de forma controlada
                    for item in tree_data.get("tree", []):
                        if item["type"] == "blob" and os.path.basename(item["path"]).lower() == "menu.exe":
                            archivos_actualizados.append(item["path"])
        
        descargas_totales = set(archivos_faltantes + archivos_actualizados)

        if not descargas_totales and not archivos_eliminados:
            print("[UI] DONE") # Le avisa a la interfaz que no hay nada que hacer
            if hay_nuevo_commit: 
                guardar_ultimo_commit(sha_remoto)
            return

        # --- CÁLCULO DE PROGRESO REAL ---
        total_tareas = len(archivos_eliminados) + len(descargas_totales)
        print(f"[UI] TAREAS:{total_tareas}", flush=True)
        tarea_actual = 0

        # EJECUTAR ELIMINACIONES
        for nombre_archivo in archivos_eliminados:
            tarea_actual += 1
            print(f"[UI] PROGRESO:{tarea_actual}|Eliminando {nombre_archivo}...", flush=True)
            ruta_local_archivo = resolver_ruta_local(nombre_archivo)
            if os.path.exists(ruta_local_archivo):
                os.remove(ruta_local_archivo)

        # EJECUTAR DESCARGAS
        hubo_cambio_en_menu = False
        hubo_cambio_en_actualizador = False # NUEVA VARIABLE
        
        for nombre_archivo in descargas_totales:
            tarea_actual += 1
            print(f"[UI] PROGRESO:{tarea_actual}|Descargando {nombre_archivo}...", flush=True)
            
            # Detectamos qué se está descargando
            nombre_base = os.path.basename(nombre_archivo).lower()
            if nombre_base == "menu.exe":
                hubo_cambio_en_menu = True
            elif nombre_base == "actualizador.exe":
                hubo_cambio_en_actualizador = True
                
            ruta_local_archivo = resolver_ruta_local(nombre_archivo)
            url_raw = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{sha_remoto}/{nombre_archivo}"
            
            os.makedirs(os.path.dirname(ruta_local_archivo), exist_ok=True)
            
            res_file = requests.get(url_raw)
            if res_file.status_code == 200:
                with open(ruta_local_archivo, "wb") as f:
                    f.write(res_file.content)
            else:
                print(f"Error al descargar {nombre_archivo}")
        
        # Al final, guardamos con ambas banderas
        guardar_ultimo_commit(
            sha_remoto, 
            actualizar_menu_estado=hubo_cambio_en_menu, 
            actualizar_actualizador_estado=hubo_cambio_en_actualizador
        )
        print("[UI] DONE", flush=True)
        
    except Exception as e:
        print(f"Error crítico en actualización: {e}")

        
if __name__ == "__main__":
    actualizar_solo_cambios()