import os
import requests
import pandas as pd
import io

def descargar_datos_liga(archivo_txt):
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/111.0'
    }

    # Leer el archivo con el formato: Fase,Categoria,Link
    with open(archivo_txt, 'r') as f:
        lineas = [linea.strip() for linea in f if linea.strip()]

    for linea in lineas:
        partes = linea.split(',')
        if len(partes) != 3:
            print(f"  [!] Línea ignorada por mal formato: {linea}")
            continue
            
        fase, categoria, url_base = [p.strip() for p in partes]

        print(f"\nProcesando Fase {fase} - Categoría {categoria}: {url_base}")
        
        dir_fase = f"data/fase_{fase}"
        os.makedirs(dir_fase, exist_ok=True)
        
        url_posiciones = f"{url_base}?art=1&zeilen=99999&lan=1"
        
        try:
            response = requests.get(url_posiciones, headers=headers)
            response.raise_for_status()
            
            tablas = pd.read_html(io.StringIO(response.text), decimal=',', thousands='.')
            
            if tablas:
                # Nos quedamos con la tabla más grande de la página (la de posiciones)
                df_posiciones = max(tablas, key=len)
                df_posiciones = df_posiciones.dropna(axis=1, how='all').dropna(axis=0, how='all')
                
                ruta_pos = os.path.join(dir_fase, f'posiciones_{categoria}.csv')
                df_posiciones.to_csv(ruta_pos, index=False)
                print(f"  [+] Posiciones guardadas en {ruta_pos}")
            else:
                print(f"  [!] No se encontró la tabla de posiciones.")
        except Exception as e:
            print(f"  [!] Error al procesar {url_base}: {e}")

if __name__ == "__main__":
    descargar_datos_liga("links.txt")
