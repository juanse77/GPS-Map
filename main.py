import re
import subprocess
import json
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point
import numpy as np
import contextily as ctx  # Importar contextily
import colorsys  # Importar colorsys para conversión de colores
import pandas as pd
import os
import csv  # Importar el módulo csv
from typing import Optional, Tuple

def dms_to_decimal(dms_str: str) -> float:
    """
    Convierte coordenadas en formato DMS (grados, minutos, segundos) a decimal.
    Ejemplo de entrada: "15 deg 25' 4.30\""
    """
    # Expresión regular para extraer grados, minutos y segundos
    pattern = r'(\d+\.?\d*)'
    parts = re.findall(pattern, dms_str)
    if len(parts) < 3:
        raise ValueError(f"No se pudo parsear DMS: {dms_str}")

    deg = float(parts[0])
    minutes = float(parts[1])
    seconds = float(parts[2])

    decimal = deg + minutes / 60 + seconds / 3600

    # Determinar el signo según presencia de 'S' (Sur) o 'W' (Oeste)
    if 'S' in dms_str.upper() or 'W' in dms_str.upper():
        decimal = -decimal

    return decimal

def decimal_to_dms(decimal_degree: float, is_lat: bool) -> str:
    """
    Convierte coordenadas de decimal a DMS con indicadores direccionales.
    :param decimal_degree: Coordenada en grados decimales.
    :param is_lat: True si es latitud, False si es longitud.
    :return: Cadena en formato DMS con indicador direccional.
    """
    degrees = int(abs(decimal_degree))
    minutes_full = (abs(decimal_degree) - degrees) * 60
    minutes = int(minutes_full)
    seconds = (minutes_full - minutes) * 60

    if is_lat:
        direction = 'N' if decimal_degree >= 0 else 'S'
    else:
        direction = 'E' if decimal_degree >= 0 else 'W'

    # Usar el símbolo de segundos en Unicode para evitar dobles comillas
    return f"{degrees}°{minutes}'{seconds:.1f}″{direction}"

def get_gps_coordinates(image_path: str) -> Optional[Tuple[float, float]]:
    """
    Usa ExifTool para leer metadatos y extraer la latitud y longitud en formato decimal.
    Retorna una tupla (lat, lon) o None si no se encuentran coordenadas.
    """
    # Ejecutar exiftool con opciones -json y -n para obtener coordenadas en decimal con signos
    cmd = ['exiftool', '-json', '-n', image_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error al ejecutar exiftool en {image_path}: {e}")
        return None

    try:
        data = json.loads(result.stdout)
        if len(data) == 0:
            print(f"No se encontró información EXIF para {image_path}.")
            return None
        info = data[0]
        lat = info.get('GPSLatitude')
        lon = info.get('GPSLongitude')
        lon_ref = info.get('GPSLongitudeRef')

        if lat is None or lon is None:
            print(f"No se encontraron coordenadas GPS en {image_path}.")
            return None

        # Ajustar el signo basado en GPSLongitudeRef
        if lon_ref:
            if lon_ref.upper() == 'W':
                lon = -abs(lon)
            elif lon_ref.upper() == 'E':
                lon = abs(lon)
            else:
                print(f"Referencia de longitud desconocida '{lon_ref}' en {image_path}. Asumiendo 'W'.")
                lon = -abs(lon)
        else:
            # Si GPSLongitudeRef no está presente, asumir que longitud positiva es 'W'
            print(f"GPSLongitudeRef ausente en {image_path}. Asumiendo 'W'.")
            lon = -abs(lon)

        return (lat, lon)
    except json.JSONDecodeError as e:
        print(f"Error al decodificar JSON para {image_path}: {e}")
        return None
    except Exception as e:
        print(f"Error al procesar metadatos para {image_path}: {e}")
        return None

def scan_images(directory: str, extensions: Tuple[str, ...]=('.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.gif', '.heic')) -> list:
    """
    Escanea un directorio en busca de imágenes con las extensiones especificadas.
    Retorna una lista de rutas completas a las imágenes encontradas.
    """
    image_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(extensions):
                image_files.append(os.path.join(root, file))
    return image_files

def generate_unique_colors(n: int, s=0.7, l=0.5) -> list:
    """
    Genera una lista de colores únicos variando el tono equidistantemente.
    :param n: Número de colores a generar.
    :param s: Saturación (0 a 1).
    :param l: Luminosidad (0 a 1).
    :return: Lista de colores en formato hexadecimal.
    """
    if n == 0:
        return []
    hues = np.linspace(0, 1, n, endpoint=False)
    colors = [colorsys.hls_to_rgb(h, l, s) for h in hues]
    colors_hex = ['#%02x%02x%02x' % (int(r*255), int(g*255), int(b*255)) for r, g, b in colors]
    return colors_hex

def plot_map_with_contextily(photo_locations: list, output_file: str, title: str = "Mapa"):
    """
    Genera un mapa con GeoPandas y etiquetas numeradas para las ubicaciones GPS usando Contextily.
    :param photo_locations: Lista de tuplas (latitud, longitud, etiqueta, color).
    :param output_file: Nombre del archivo de salida (PNG).
    :param title: Título del mapa.
    """
    if not photo_locations:
        print("No hay ubicaciones para plotear.")
        return

    # 1. Crear GeoDataFrame para los puntos en EPSG:4326
    geometry = [Point(lon, lat) for lat, lon, _, _ in photo_locations]
    gdf = gpd.GeoDataFrame(photo_locations, columns=['Lat', 'Lon', 'Label', 'Color'], geometry=geometry, crs="EPSG:4326")
    print(f"GeoDataFrame de puntos:\n{gdf}\n")

    # 2. Reproyectar a EPSG:3857 para usar con Contextily
    gdf_3857 = gdf.to_crs(epsg=3857)
    print(f"CRS reproyectado de puntos: {gdf_3857.crs}\n")

    # 3. Calcular límites basados en los puntos con un pequeño margen
    minx, miny, maxx, maxy = gdf_3857.total_bounds
    width = maxx - minx
    height = maxy - miny
    buffer_x = width * 0.1 if width != 0 else 1000  # 10% del ancho o un valor por defecto
    buffer_y = height * 0.1 if height != 0 else 1000  # 10% del alto o un valor por defecto
    # Asegurar que el recuadro sea cuadrado
    max_buffer = max(buffer_x, buffer_y)
    minx_buffered = minx - max_buffer
    miny_buffered = miny - max_buffer
    maxx_buffered = maxx + max_buffer
    maxy_buffered = maxy + max_buffer
    print(f"Límites proyectados con buffer: {minx_buffered}, {miny_buffered}, {maxx_buffered}, {maxy_buffered}\n")

    # 4. Crear la figura y los ejes con DPI ajustado a 500
    fig, ax = plt.subplots(figsize=(10,10), dpi=500)  # Figura cuadrada

    # 5. Establecer los límites
    ax.set_xlim(minx_buffered, maxx_buffered)
    ax.set_ylim(miny_buffered, maxy_buffered)
    print(f"Límites del eje establecidos: x [{minx_buffered}, {maxx_buffered}], y [{miny_buffered}, {maxy_buffered}]\n")

    # 6. Añadir el basemap satelital con zoom ajustado a 15
    try:
        ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery, zoom=19)
        print("Basemap añadido correctamente.\n")
    except Exception as e:
        print(f"Error al añadir basemap: {e}\n")

    # 7. Graficar los puntos reproyectados con tamaño y colores específicos
    for idx, row in gdf_3857.iterrows():
        ax.plot(row.geometry.x, row.geometry.y, marker='o', markersize=10, markeredgecolor='black',
                markerfacecolor=row['Color'], zorder=5)
        print(f"Punto '{row['Label']}' ploteado en ({row.geometry.x}, {row.geometry.y}) con color {row['Color']}.")

    print()

    # 8. Crear elementos de la leyenda
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', label=row[2],
               markerfacecolor=row[3], markersize=10, markeredgecolor='black')
        for row in photo_locations
    ]

    # 9. Añadir la leyenda
    ax.legend(handles=legend_elements, loc='lower right', title="Puntos", fontsize=8, title_fontsize=10)
    print("Leyenda añadida.\n")

    # 10. Eliminar los ejes para una apariencia más limpia
    ax.set_axis_off()

    # 11. Ajustar título y guardar el mapa
    plt.title(title, fontsize=16)
    plt.savefig(output_file, dpi=500, bbox_inches='tight')  # DPI ajustado a 500
    plt.close()
    print(f"Mapa guardado como {output_file}\n")

def generate_excel(image_data: list, output_excel: str):
    """
    Genera un archivo Excel (.xlsx) con los datos de las imágenes.
    :param image_data: Lista de diccionarios con claves 'filename', 'latitude_dms', 'longitude_dms'.
    :param output_excel: Ruta al archivo Excel de salida.
    """
    if not image_data:
        print("No hay datos para guardar en el archivo Excel.")
        return

    # Crear un DataFrame de pandas
    df = pd.DataFrame(image_data)

    # Renombrar las columnas para que coincidan con el CSV
    df.rename(columns={
        'filename': 'Nombre de la foto',
        'latitude_dms': 'Latitud',
        'longitude_dms': 'Longitud'
    }, inplace=True)

    # Reemplazar NaN con cadenas vacías
    df.fillna('', inplace=True)

    # Guardar el DataFrame en un archivo Excel
    df.to_excel(output_excel, index=False, engine='openpyxl')
    print(f"Archivo Excel generado como {output_excel}\n")

def generate_csv(image_data: list, output_csv: str):
    """
    Genera un archivo CSV con los datos de las imágenes.
    :param image_data: Lista de diccionarios con claves 'filename', 'latitude_dms', 'longitude_dms'.
    :param output_csv: Ruta al archivo CSV de salida.
    """
    if not image_data:
        print("No hay datos para guardar en el archivo CSV.")
        return

    with open(output_csv, mode='w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Nombre de la foto', 'Latitud', 'Longitud']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)

        writer.writeheader()
        for data in image_data:
            writer.writerow({
                'Nombre de la foto': data['filename'],
                'Latitud': data['latitude_dms'] if data['latitude_dms'] else '',
                'Longitud': data['longitude_dms'] if data['longitude_dms'] else ''
            })
    print(f"Archivo CSV generado como {output_csv}\n")

def generate_unique_colors(n: int, s=0.7, l=0.5) -> list:
    """
    Genera una lista de colores únicos variando el tono equidistantemente.
    :param n: Número de colores a generar.
    :param s: Saturación (0 a 1).
    :param l: Luminosidad (0 a 1).
    :return: Lista de colores en formato hexadecimal.
    """
    if n == 0:
        return []
    hues = np.linspace(0, 1, n, endpoint=False)
    colors = [colorsys.hls_to_rgb(h, l, s) for h in hues]
    colors_hex = ['#%02x%02x%02x' % (int(r*255), int(g*255), int(b*255)) for r, g, b in colors]
    return colors_hex

def main():
    # Directorio que contiene las imágenes
    # Modifica esta ruta según tus necesidades
    image_directory = r"C:\Users\juanse77\Documents\Proyectos\GeoFotos\imgs"

    # Rutas de los archivos de salida
    output_csv = "coordenadas_fotos.csv"
    output_excel = "coordenadas_fotos.xlsx"
    output_map = "mapa_fotos.png"

    # Escanear las imágenes en el directorio
    print(f"Escaneando imágenes en {image_directory}...")
    images = scan_images(image_directory)
    print(f"Se encontraron {len(images)} imágenes.\n")

    if not images:
        print("No se encontraron imágenes para procesar. Saliendo del script.")
        return

    image_data = []
    photo_locations = []

    # Extraer coordenadas y preparar datos
    for img_path in images:
        filename = os.path.basename(img_path)
        print(f"Procesando {filename}...")
        coords = get_gps_coordinates(img_path)
        if coords:
            lat, lon = coords
            latitude_dms = decimal_to_dms(lat, is_lat=True)
            longitude_dms = decimal_to_dms(lon, is_lat=False)
            print(f" - Coordenadas encontradas: Latitud={latitude_dms}, Longitud={longitude_dms}")
            image_data.append({
                'filename': filename,
                'latitude_dms': latitude_dms,
                'longitude_dms': longitude_dms
            })
            photo_locations.append((lat, lon, filename, None))  # Color se asignará luego
        else:
            print(f" - No se encontraron coordenadas GPS en {filename}.\n")

    if not photo_locations:
        print("Ninguna imagen contiene datos GPS. Saliendo del script.")
        return

    # Generar colores únicos basados en la cantidad de imágenes con GPS
    num_photos = len(photo_locations)
    colors_generated = generate_unique_colors(num_photos, s=0.7, l=0.5)

    # Asignar colores a cada punto
    for idx, location in enumerate(photo_locations):
        lat, lon, label, _ = location
        color = colors_generated[idx] if idx < len(colors_generated) else '#000000'  # Negro por defecto
        photo_locations[idx] = (lat, lon, label, color)

    # Generar el mapa
    plot_map_with_contextily(photo_locations, output_map, title="Mapa de Fotos")

    # Generar el archivo CSV
    generate_csv(image_data, output_csv)

    # Generar el archivo Excel
    generate_excel(image_data, output_excel)

    print("Proceso completado exitosamente.")

if __name__ == "__main__":
    main()
