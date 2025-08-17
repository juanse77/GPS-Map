import csv
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point
import numpy as np
import contextily as ctx
import colorsys
import pandas as pd
import os


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

    geometry = [Point(lon, lat) for lat, lon, _, _ in photo_locations]
    gdf = gpd.GeoDataFrame(photo_locations, columns=['Lat', 'Lon', 'Label', 'Color'], geometry=geometry, crs="EPSG:4326")
    print(f"GeoDataFrame de puntos:\n{gdf}\n")

    gdf_3857 = gdf.to_crs(epsg=3857)
    print(f"CRS reproyectado de puntos: {gdf_3857.crs}\n")

    minx, miny, maxx, maxy = gdf_3857.total_bounds
    width = maxx - minx
    height = maxy - miny
    
    if height > width:
        minx = minx - (height - width)/2
        maxx = maxx + (height - width)/2
    else:
        miny = miny - (width - height)/2
        maxy = maxy + (width - height)/2
    
    max_meassure = height if height > width else width 
    buffer = max_meassure * 0.1

    minx_buffered = minx - buffer
    miny_buffered = miny - buffer
    maxx_buffered = maxx + buffer
    maxy_buffered = maxy + buffer
    
    print(f"Límites proyectados con buffer: {minx_buffered}, {miny_buffered}, {maxx_buffered}, {maxy_buffered}\n")

    fig, ax = plt.subplots(figsize=(10,10), dpi=500)

    ax.set_xlim(minx_buffered, maxx_buffered)
    ax.set_ylim(miny_buffered, maxy_buffered)
    
    ax.set_aspect('equal')
    
    print(f"Límites del eje establecidos: x [{minx_buffered}, {maxx_buffered}], y [{miny_buffered}, {maxy_buffered}]\n")

    try:
        ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery, zoom=20)
        print("Basemap añadido correctamente.\n")
    except Exception as e:
        print(f"Error al añadir basemap: {e}\n")

    for idx, row in gdf_3857.iterrows():
        ax.plot(row.geometry.x, row.geometry.y, marker='o', markersize=10, markeredgecolor='black',
                markerfacecolor=row['Color'], zorder=5)
        print(f"Punto '{row['Label']}' ploteado en ({row.geometry.x}, {row.geometry.y}) con color {row['Color']}.")

    print()

    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', label=row[2],
               markerfacecolor=row[3], markersize=10, markeredgecolor='black')
        for row in photo_locations
    ]

    ax.legend(handles=legend_elements, loc='upper left', title="Puntos", fontsize=8, title_fontsize=10)
    print("Leyenda añadida.\n")

    ax.set_axis_off()

    plt.title(title, fontsize=16)
    plt.savefig(output_file, dpi=500, bbox_inches='tight')  # DPI ajustado a 500
    plt.close()
    print(f"Mapa guardado como {output_file}\n")


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

def leer_csv_labels(ruta_csv):
    datos = []
    with open(ruta_csv, newline='', encoding='utf-8') as archivo:
        lector = csv.DictReader(archivo)
        for fila in lector:
            datos.append({
                "label": fila["label"],
                "lat": float(fila["lat"]),
                "long": float(fila["long"])
            })

    return datos

def main():
    input_csv = "tara.csv"
    output_map = "tara.png"

    image_data = []
    photo_locations = []

    datos = leer_csv_labels(input_csv)

    for fila in datos:
        label = fila['label']
        lat =  fila['lat']
        long = fila['long']
        
        latitude_dms = decimal_to_dms(lat, is_lat=True)
        longitude_dms = decimal_to_dms(long, is_lat=False)
        
        image_data.append({
            'latitude_dms': latitude_dms,
            'longitude_dms': longitude_dms
        })
        
        photo_locations.append((lat, long, label))

    if not photo_locations:
        print("Ninguna imagen contiene datos GPS. Saliendo del script.")
        return

    num_photos = len(photo_locations)
    colors_generated = generate_unique_colors(num_photos, s=0.7, l=0.5)

    for idx, location in enumerate(photo_locations):
        lat, long, label = location
        color = colors_generated[idx] if idx < len(colors_generated) else '#000000'
        photo_locations[idx] = (lat, long, label, color)

    plot_map_with_contextily(photo_locations, output_map, title="Mapa de Fotos")
    print("Proceso completado exitosamente.")

if __name__ == "__main__":
    main()
