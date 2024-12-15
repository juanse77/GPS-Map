import subprocess
import json
import os
import csv
from typing import Optional, Tuple
import pandas as pd

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

def generate_csv(image_data: list, output_csv: str):
    """
    Genera un archivo CSV con los datos de las imágenes.
    :param image_data: Lista de diccionarios con claves 'filename', 'latitude_dms', 'longitude_dms'.
    :param output_csv: Ruta al archivo CSV de salida.
    """
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

def generate_excel(image_data: list, output_excel: str):
    """
    Genera un archivo Excel (.xlsx) con los datos de las imágenes.
    :param image_data: Lista de diccionarios con claves 'filename', 'latitude_dms', 'longitude_dms'.
    :param output_excel: Ruta al archivo Excel de salida.
    """
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

def main():
    # Directorio que contiene las imágenes
    # Modifica esta ruta según tus necesidades
    image_directory = r"C:\Users\juanse77\Documents\Proyectos\GeoFotos\imgs"

    # Rutas de los archivos de salida
    output_csv = "coordenadas_fotos.csv"
    output_excel = "coordenadas_fotos.xlsx"

    # Escanear las imágenes en el directorio
    print(f"Escaneando imágenes en {image_directory}...")
    images = scan_images(image_directory)
    print(f"Se encontraron {len(images)} imágenes.")

    image_data = []
    for img_path in images:
        filename = os.path.basename(img_path)
        print(f"Procesando {filename}...")
        coords = get_gps_coordinates(img_path)
        if coords:
            lat, lon = coords
            latitude_dms = decimal_to_dms(lat, is_lat=True)
            longitude_dms = decimal_to_dms(lon, is_lat=False)
            print(f" - Coordenadas encontradas: Latitud={latitude_dms}, Longitud={longitude_dms}")
        else:
            latitude_dms, longitude_dms = (None, None)
            print(f" - No se encontraron coordenadas GPS.")
        image_data.append({
            'filename': filename,
            'latitude_dms': latitude_dms,
            'longitude_dms': longitude_dms
        })

    # Generar el archivo CSV
    print(f"Generando archivo CSV en {output_csv}...")
    generate_csv(image_data, output_csv)

    # Generar el archivo Excel
    print(f"Generando archivo Excel en {output_excel}...")
    generate_excel(image_data, output_excel)

    print("Proceso completado exitosamente.")

if __name__ == "__main__":
    main()
