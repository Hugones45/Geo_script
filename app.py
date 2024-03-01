from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import os
import geopandas as gpd
import matplotlib.pyplot as plt
from io import BytesIO
import base64
import threading

app = Flask(__name__)
CORS(app)

def paths():
    estados = os.getcwd() + "/map_data/municipios.shp"
    aeroportos = os.getcwd() + "/map_data/aeroportos.shp"
    rodovias = os.getcwd() + "/map_data/rodovias.shp"

    return [estados, aeroportos, rodovias]

def read_file():
    return [gpd.read_file(i) for i in paths()]

def filtrar_estados(shapes, state):
    return shapes[shapes['uf'] == state].copy()

def aeroportos(shapes, state):
    gdf_pontos = gpd.sjoin(shapes, state, predicate='within').copy()
    total_aeroportos = gdf_pontos.value_counts('TipoAero')
    total_pavi = gdf_pontos.value_counts('pavimento')
    
    return gdf_pontos, total_aeroportos, total_pavi

def rodovias(shapes, state):
    gdf = gpd.overlay(shapes, state, how="intersection").copy()
    gdf_projetado = gdf.copy()
    gdf_projetado['geometry'] = gdf_projetado['geometry'].to_crs(epsg=5880)
    gdf_projetado['distancia'] = gdf_projetado['geometry'].length / 1000
    
    aggregation_functions = {
        'distancia': 'sum',  
    }
    distancias = gdf_projetado.groupby('nm_tipo_tr').agg(aggregation_functions)

    return gdf, distancias

def generate_map(state_acronym, thread_id):
    
    app = Flask(__name__)
    CORS(app)

    
    plt.switch_backend('agg')

    shapes = read_file()
    municipio_filter = filtrar_estados(shapes[0], state_acronym)
    gdf_pontos_aero, _, _ = aeroportos(shapes[1], municipio_filter)
    gdf_roads, _ = rodovias(shapes[2], municipio_filter)

    municipio_filter['area'] = municipio_filter['geometry'].to_crs(epsg=5880).area / 1000000

    fig, ax = plt.subplots(1, 1, figsize=(10, 10))
    plt.title(f'Map for {state_acronym} (Thread {thread_id})', fontsize=5, y=1.03)

    base = municipio_filter.plot(ax=ax, column='area', cmap='copper_r', k=5, scheme='quantiles', legend=True)

    gdf_roads.plot(ax=base, color='aquamarine', linestyle='dotted', label='Estradas')

    gdf_pontos_aero.plot(ax=base, marker='*', color='red', label='Aeroportos')

    legend_municipio_filter = base.get_legend()

    legend_municipio_filter.set_title('Area in Km2')

    filename = f'map_image_{state_acronym}_{thread_id}.png'
    image_stream = BytesIO()
    plt.savefig(image_stream, format='png', dpi=300, bbox_inches='tight')
    image_stream.seek(0)
    image_base64 = base64.b64encode(image_stream.read()).decode('utf-8')

    plt.close()

    return image_base64

def generate_map_threaded(state_acronym, thread_id):
    with app.app_context():
        image_base64 = generate_map(state_acronym, thread_id)
    return image_base64

@app.route('/')
def index():
    return 'Hello from Flask!'

@app.route('/generate_map', methods=['POST'])
def generate_map_route():
    try:
        state_acronym = request.form.get('state_acronym').upper()
        thread_id = threading.current_thread().ident
        image_base64 = generate_map_threaded(state_acronym, thread_id)
        return jsonify({'image_base64': image_base64})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/map_image/<state_acronym>')
def get_map_image(state_acronym):
    try:
        thread_id = threading.current_thread().ident
        image_base64 = generate_map_threaded(state_acronym, thread_id)
        return send_file(BytesIO(base64.b64decode(image_base64)), mimetype='image/png')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
