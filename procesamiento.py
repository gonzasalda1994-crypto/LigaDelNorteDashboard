import os
import glob
import pandas as pd
import unicodedata
import json
import re

# NUEVA ESCALA DE PUNTOS GP
GP_POINTS = {1: 10, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1}

def normalizar_columnas(df):
    """Mapea las columnas de chess-results a nombres fijos, incluyendo procedencia."""
    mapping = {}
    for col in df.columns:
        col_clean = str(col).lower().strip()
        if col_clean in ['rk.', 'rk', 'pos', 'pos.', 'posicion', 'no.']:
            mapping[col] = 'Posicion'
        elif col_clean in ['name', 'nombre', 'jugador']:
            mapping[col] = 'Jugador'
        elif col_clean in ['pts', 'pts.', 'puntos', 'ptos']:
            mapping[col] = 'Puntos'
        elif col_clean in ['club/city', 'club', 'procedencia', 'localidad', 'fedil', 'club/origen']:
            mapping[col] = 'Procedencia'
        elif col_clean == 'tb1':
            mapping[col] = 'TB1'
            
    df = df.rename(columns=mapping)
    if 'Puntos' not in df.columns and 'TB1' in df.columns:
        df = df.rename(columns={'TB1': 'Puntos'})
    return df

def limpiar_nombre(nombre_crudo):
    if not isinstance(nombre_crudo, str): return "Desconocido"
    texto = unicodedata.normalize('NFD', nombre_crudo)
    nombre_limpio = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    partes = nombre_limpio.split(',')
    if len(partes) >= 2:
        apellido = " ".join(partes[0].split()).title()
        nombres = " ".join(partes[1].split()).title()
        return f"{apellido}, {nombres}"
    return " ".join(nombre_limpio.split()).title()

def limpiar_procedencia(texto):
    if pd.isna(texto) or not isinstance(texto, str):
        return "-"
    return " ".join(texto.split()).title()

def cargar_alias():
    """Carga el diccionario de unificación de nombres si existe."""
    if os.path.exists("alias_jugadores.json"):
        try:
            with open("alias_jugadores.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[-] Error al leer alias_jugadores.json: {e}")
    return {}

def extraer_numero_fase(nombre_fase):
    numeros = re.findall(r'\d+', nombre_fase)
    return int(numeros[0]) if numeros else 0

def procesar_todo():
    links_map = {}
    if os.path.exists("enlaces.txt"):
        with open("enlaces.txt", "r") as f:
            for linea in f:
                if linea.strip():
                    partes = linea.split(',')
                    if len(partes) == 3:
                        fase_num, c, url = [p.strip() for p in partes]
                        links_map[f"{fase_num}_{c}"] = f"{url}?art=1&zeilen=99999&lan=1"

    archivos = glob.glob("data/fase_*/*.csv")
    categorias = set(os.path.basename(f).replace("posiciones_", "").replace(".csv", "") for f in archivos)
    
    diccionario_alias = cargar_alias()
    if diccionario_alias:
        print(f"[+] Se cargaron {len(diccionario_alias)} reglas de alias para unificación.")
    
    estructura_final = {}

    for cat in categorias:
        carpetas_fases = sorted(glob.glob("data/fase_*"))
        dfs_fases = []
        
        for idx, carpeta in enumerate(carpetas_fases, start=1):
            archivo_pos = os.path.join(carpeta, f"posiciones_{cat}.csv")
            if os.path.exists(archivo_pos):
                df = pd.read_csv(archivo_pos)
                df = normalizar_columnas(df)
                df['Fase'] = f"Fase {idx}"
                if 'Procedencia' not in df.columns:
                    df['Procedencia'] = "-"
                dfs_fases.append(df)
                
        if not dfs_fases: continue
        
        df_total = pd.concat(dfs_fases, ignore_index=True)
        
        df_total['Jugador'] = df_total['Jugador'].apply(limpiar_nombre)
        df_total['Procedencia'] = df_total['Procedencia'].apply(limpiar_procedencia)
        
        if diccionario_alias:
            df_total['Jugador'] = df_total['Jugador'].replace(diccionario_alias)

        df_total['Puntos'] = pd.to_numeric(df_total['Puntos'], errors='coerce').fillna(0)
        df_total['Posicion'] = pd.to_numeric(df_total['Posicion'], errors='coerce')
        df_total['Puntos_GP'] = df_total['Posicion'].map(GP_POINTS).fillna(0)

        # 1. Posiciones individuales por fase
        fases_dict = {}
        fases_unicas = sorted(df_total['Fase'].unique().tolist(), key=extraer_numero_fase)

        for fase in fases_unicas:
            df_fase = df_total[df_total['Fase'] == fase]
            num_fase = fase.split()[-1]
            url_cr = links_map.get(f"{num_fase}_{cat}", "#")
            
            fases_dict[fase] = {
                "link_chess_results": url_cr,
                "resultados": df_fase[['Posicion', 'Jugador', 'Procedencia', 'Puntos']].to_dict(orient='records')
            }

        df_procedencias = df_total[df_total['Procedencia'] != "-"].groupby('Jugador')['Procedencia'].last().reset_index()

        # 2. Acumulado Puntos (Ahora como Pivot Table para tener detalle por fase)
        pivot_ptos = df_total.pivot_table(index='Jugador', columns='Fase', values='Puntos', aggfunc='sum', fill_value=0)
        pivot_ptos['Total'] = pivot_ptos.sum(axis=1)
        pivot_ptos = pivot_ptos.reset_index().merge(df_procedencias, on='Jugador', how='left').fillna("-")
        ac_puntos = pivot_ptos.sort_values(by='Total', ascending=False).to_dict(orient='records')

        # 3. Acumulado GP (También como Pivot Table)
        pivot_gp = df_total.pivot_table(index='Jugador', columns='Fase', values='Puntos_GP', aggfunc='sum', fill_value=0)
        pivot_gp['Total'] = pivot_gp.sum(axis=1)
        pivot_gp = pivot_gp.reset_index().merge(df_procedencias, on='Jugador', how='left').fillna("-")
        ac_gp = pivot_gp.sort_values(by='Total', ascending=False).to_dict(orient='records')

        estructura_final[cat] = {
            "fases_nombres": fases_unicas,
            "fases": fases_dict,
            "acumulado_puntos": ac_puntos,
            "acumulado_gp": ac_gp
        }

    with open("datos_liga.json", "w", encoding="utf-8") as f:
        json.dump(estructura_final, f, ensure_ascii=False, indent=2)
    print("[+] datos_liga.json generado con éxito con detalle por fase.")

if __name__ == "__main__":
    procesar_todo()
