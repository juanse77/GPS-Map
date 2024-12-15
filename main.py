import re
import subprocess
import json
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point
import numpy as np
import contextily as ctx  # Importar contextily
import colorsys  # Importar colorsys para conversión de colores

def dms_to_decimal(dms_str):
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

def get_gps_coordinates(image_path):
    """
    Usa ExifTool para leer metadatos y extraer la latitud y longitud.
    Retorna una tupla (lat, lon) o None si no se encuentran coordenadas.
    """
    # Ejecutar exiftool con opción -n para obtener coordenadas en decimal
    cmd = ['exiftool', '-json', '-n', image_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        data = json.loads(result.stdout)
        if len(data) > 0:
            info = data[0]
            lat = info.get('GPSLatitude')
            lon = info.get('GPSLongitude')
            # No existe GPSLongitudeRef cuando se usa -n, así que asumimos 'W'
            # Aseguramos que las longitudes sean negativas
            if lat is None or lon is None:
                return None

            # Convertir de DMS a decimal si es necesario
            if isinstance(lat, str):
                lat = dms_to_decimal(lat)
            if isinstance(lon, str):
                lon = dms_to_decimal(lon)

            # Asumir 'W' si GPSLongitudeRef no está presente
            lon = -lon  # Porque Gran Canaria está en el hemisferio occidental

            return (lat, lon)
    return None

def generate_unique_colors(n, s=0.7, l=0.5):
    """
    Genera una lista de colores únicos variando el tono equidistantemente.
    :param n: Número de colores a generar.
    :param s: Saturación (0 a 1).
    :param l: Luminosidad (0 a 1).
    :return: Lista de colores en formato hexadecimal.
    """
    hues = np.linspace(0, 1, n, endpoint=False)
    colors = [colorsys.hls_to_rgb(h, l, s) for h in hues]
    colors_hex = ['#%02x%02x%02x' % (int(r*255), int(g*255), int(b*255)) for r, g, b in colors]
    return colors_hex

def plot_map_with_contextily(photo_locations, output_file, title="Mapa"):
    """
    Genera un mapa con GeoPandas y etiquetas numeradas para las ubicaciones GPS usando Contextily.
    :param photo_locations: Lista de tuplas (latitud, longitud, etiqueta, color).
    :param output_file: Nombre del archivo de salida (PNG).
    :param title: Título del mapa.
    """
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
    buffer_x = width * 0.1  # 10% del ancho
    buffer_y = height * 0.1  # 10% del alto
    minx_buffered = minx - buffer_x
    miny_buffered = miny - buffer_y
    maxx_buffered = maxx + buffer_x
    maxy_buffered = maxy + buffer_y
    print(f"Límites proyectados con buffer: {minx_buffered}, {miny_buffered}, {maxx_buffered}, {maxy_buffered}\n")

    # 4. Crear la figura y los ejes con DPI ajustado a 300 para mejor resolución
    fig, ax = plt.subplots(figsize=(10,8), dpi=500)  # DPI ajustado a 300

    # 5. Establecer los límites
    ax.set_xlim(minx_buffered, maxx_buffered)
    ax.set_ylim(miny_buffered, maxy_buffered)
    print(f"Límites del eje establecidos: x [{minx_buffered}, {maxx_buffered}], y [{miny_buffered}, {maxy_buffered}]\n")

    # 6. Añadir el basemap satelital con zoom ajustado a 15
    try:
        ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery, zoom=18)  # Zoom ajustado a 15
        print("Basemap añadido correctamente.\n")
    except Exception as e:
        print(f"Error al añadir basemap: {e}\n")

    # 7. Graficar los puntos reproyectados con menor tamaño y colores específicos
    for idx, row in gdf_3857.iterrows():
        ax.plot(row.geometry.x, row.geometry.y, marker='o', markersize=10, markeredgecolor='black',
                markerfacecolor=row['Color'], zorder=5)
        print(f"Punto '{row['Label']}' ploteado en ({row.geometry.x}, {row.geometry.y}) con color {row['Color']}.")

    print()

    # 9. Crear elementos de la leyenda
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', label=row[2],
               markerfacecolor=row[3], markersize=10, markeredgecolor='black')
        for row in photo_locations
    ]

    # 10. Añadir la leyenda
    ax.legend(handles=legend_elements, loc='upper right', title="Puntos", fontsize=8, title_fontsize=10)
    print("Leyenda añadida.\n")

    # 11. Eliminar los ejes para una apariencia más limpia
    ax.set_axis_off()

    # 12. Ajustar título y guardar el mapa
    plt.title(title, fontsize=16)
    plt.savefig(output_file, dpi=500, bbox_inches='tight')  # DPI ajustado a 300
    plt.close()
    print(f"Mapa guardado como {output_file}\n")

# Ejemplo de uso
if __name__ == "__main__":
    # Puntos originales
    original_points = [
        ("01.jpg", 27.9964365, -15.4178604, "Foto 1"),
    ]

    # Generar 20 nuevos puntos ficticios
    np.random.seed(42)  # Para reproducibilidad
    num_new_points = 20
    new_points = []
    for i in range(1, num_new_points + 1):
        # Desplazamiento aleatorio de hasta ±0.001 grados (~100m)
        delta_lat = np.random.uniform(-0.001, 0.001)
        delta_lon = np.random.uniform(-0.001, 0.001)
        lat = original_points[0][1] + delta_lat
        lon = original_points[0][2] + delta_lon
        label = f"Punto {i}"
        new_points.append((lat, lon, label))

    # Generar colores únicos variando el tono
    colors_generated = generate_unique_colors(num_new_points, s=0.7, l=0.5)

    # Combinar puntos originales y nuevos puntos con colores
    photo_locations = []
    # Agregar puntos originales con colores fijos (por ejemplo, rojo)
    photo_locations.append((original_points[0][1], original_points[0][2], original_points[0][3], 'red'))
    # Agregar nuevos puntos con colores generados
    for idx, point in enumerate(new_points):
        color = colors_generated[idx]
        photo_locations.append((point[0], point[1], point[2], color))

    output_file = "map_satellite_colored.png"
    plot_map_with_contextily(photo_locations, output_file, title="Mapa de Fotos con Múltiples Puntos y Colores Variados")
