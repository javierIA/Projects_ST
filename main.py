import streamlit as st
import os
import json
import requests
import warnings
from collections import defaultdict, Counter
from datetime import datetime
import base64
import zipfile
import shutil
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

warnings.filterwarnings('ignore', 'Unverified HTTPS request')

class COCOExportAnalyzer:
    def __init__(self):
        self.base_url = "https://teleflexcvat.ia.center"
        user = st.secrets["username"]
        password = st.secrets["password"]
        credentials = credentials = f"{user}:{password}"
        basic_auth = base64.b64encode(credentials.encode()).decode()
        self.headers = {
            'Authorization': f'Basic {basic_auth}',
            'accept': 'application/vnd.cvat+json'
        }

    def export_project(self, project_id: int) -> str:
        try:
            annotations_url = f"{self.base_url}/api/projects/{project_id}/annotations"
            params = {
                'action': 'download',
                'format': 'COCO 1.0',
                'location': 'local',
                'use_default_location': 'true'
            }
            
            with st.spinner('Descargando anotaciones...'):
                response = requests.get(
                    annotations_url,
                    headers=self.headers,
                    params=params,
                    verify=False,
                    stream=True
                )
            
            if response.status_code == 200:
                zip_filename = f'project_{project_id}_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
                with open(zip_filename, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                temp_dir = f'temp_extract_{project_id}'
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                os.makedirs(temp_dir)
                
                with st.spinner('Extrayendo archivos...'):
                    try:
                        with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
                            zip_ref.extractall(temp_dir)
                        
                        json_path = os.path.join(temp_dir, 'annotations', 'instances_default.json')
                        if os.path.exists(json_path):
                            final_json = f'project_{project_id}_annotations_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
                            shutil.copy2(json_path, final_json)
                            shutil.rmtree(temp_dir)
                            os.remove(zip_filename)
                            return final_json
                        else:
                            st.error("No se encontró el archivo JSON en la ruta esperada")
                            return None
                    except zipfile.BadZipFile:
                        st.error("El archivo descargado no es un ZIP válido")
                        return None
            else:
                st.error(f"Error al obtener anotaciones: {response.status_code}")
                return None
        except Exception as e:
            st.error(f"Error durante la exportación: {str(e)}")
            return None

    def analyze_annotations_file(self, filename: str) -> dict:
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            stats = {
                'total_images': len(data.get('images', [])),
                'total_annotations': len(data.get('annotations', [])),
                'total_categories': len(data.get('categories', [])),
                'categories': {},
                'annotations_per_category': defaultdict(int),
                'bbox_areas': [],
                'annotations_per_image': defaultdict(int),
                'category_bbox_sizes': defaultdict(list),
                'image_sizes': [],
                'raw_data': data
            }
            
            # Mapeo de categorías
            category_map = {cat['id']: cat['name'] for cat in data.get('categories', [])}
            stats['categories'] = category_map
            
            # Análisis de imágenes
            for img in data.get('images', []):
                stats['image_sizes'].append({
                    'width': img['width'],
                    'height': img['height'],
                    'area': img['width'] * img['height']
                })
            
            # Análisis de anotaciones
            for ann in data.get('annotations', []):
                cat_id = ann.get('category_id')
                if cat_id in category_map:
                    cat_name = category_map[cat_id]
                    stats['annotations_per_category'][cat_name] += 1
                    
                    # Analizar bbox si existe
                    if 'bbox' in ann:
                        bbox = ann['bbox']
                        area = bbox[2] * bbox[3]  # width * height
                        stats['bbox_areas'].append(area)
                        stats['category_bbox_sizes'][cat_name].append(area)
                
                # Contar anotaciones por imagen
                stats['annotations_per_image'][ann.get('image_id')] += 1
            
            return stats
        except Exception as e:
            st.error(f"Error durante el análisis: {str(e)}")
            return None

def create_category_distribution(stats: dict):
    df = pd.DataFrame([
        {"Categoría": cat_name, "Cantidad": count, "Porcentaje": (count/stats['total_annotations'])*100}
        for cat_name, count in stats['annotations_per_category'].items()
    ])
    
    fig = px.bar(
        df, 
        x="Categoría", 
        y="Cantidad",
        text="Porcentaje",
        title="Distribución de Anotaciones por Categoría"
    )
    fig.update_traces(
        texttemplate='%{text:.1f}%',
        textposition='outside'
    )
    return fig

def create_bbox_size_distribution(stats: dict):
    areas = np.array(stats['bbox_areas'])
    
    fig = px.histogram(
        areas,
        nbins=50,
        title="Distribución de Tamaños de Bounding Boxes",
        labels={'value': 'Área del Bounding Box', 'count': 'Frecuencia'}
    )
    return fig

def create_annotations_per_image(stats: dict):
    counts = list(stats['annotations_per_image'].values())
    
    fig = px.histogram(
        counts,
        title="Distribución de Anotaciones por Imagen",
        labels={'value': 'Número de Anotaciones', 'count': 'Frecuencia'},
        nbins=30
    )
    return fig

def create_bbox_size_by_category(stats: dict):
    data = []
    for cat_name, sizes in stats['category_bbox_sizes'].items():
        data.extend([{'Categoría': cat_name, 'Área': size} for size in sizes])
    
    df = pd.DataFrame(data)
    
    fig = px.box(
        df,
        x='Categoría',
        y='Área',
        title='Distribución de Tamaños de Bounding Box por Categoría'
    )
    return fig

def display_statistics(stats: dict):
    if not stats:
        st.error("No hay estadísticas para mostrar")
        return
    
    # Métricas generales
    st.subheader("📊 Métricas Generales")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Imágenes", stats['total_images'])
    with col2:
        st.metric("Total de Anotaciones", stats['total_annotations'])
    with col3:
        st.metric("Total de Categorías", stats['total_categories'])
    
    # Promedio de anotaciones por imagen
    avg_annotations = stats['total_annotations'] / stats['total_images']
    st.metric("Promedio de Anotaciones por Imagen", f"{avg_annotations:.2f}")
    
    # Distribución de categorías
    st.plotly_chart(create_category_distribution(stats), use_container_width=True)
    
    # Dos gráficos en la misma fila
    col1, col2 = st.columns(2)
    
    with col1:
        st.plotly_chart(create_bbox_size_distribution(stats), use_container_width=True)
    
    with col2:
        st.plotly_chart(create_annotations_per_image(stats), use_container_width=True)
    
    # Distribución de tamaños por categoría
    st.plotly_chart(create_bbox_size_by_category(stats), use_container_width=True)
    
    # Tabla detallada
    st.subheader("📋 Desglose Detallado por Categoría")
    df_details = pd.DataFrame([
        {
            "Categoría": cat_name,
            "Cantidad": count,
            "Porcentaje": (count/stats['total_annotations'])*100,
            "Tamaño Promedio BB": np.mean(stats['category_bbox_sizes'].get(cat_name, [0])),
            "Tamaño Mediano BB": np.median(stats['category_bbox_sizes'].get(cat_name, [0]))
        }
        for cat_name, count in stats['annotations_per_category'].items()
    ])
    
    st.dataframe(df_details.round(2))
    
    # Botón de descarga
    csv = df_details.to_csv(index=False)
    st.download_button(
        "⬇️ Descargar Análisis CSV",
        csv,
        "analisis_anotaciones.csv",
        "text/csv",
        key='download-csv'
    )

def main():
    st.set_page_config(
        page_title="Análisis de Anotaciones CVAT",
        page_icon="📊",
        layout="wide"
    )
    
    st.title("📊 Análisis de Anotaciones CVAT")
    st.markdown("---")
    
    project_id = st.text_input("ID del Proyecto", help="Ingrese el ID numérico del proyecto")
    
    if st.button("🔍 Analizar Proyecto"):
        if project_id and project_id.isdigit():
            analyzer = COCOExportAnalyzer()
            
            with st.spinner('Procesando proyecto...'):
                annotations_file = analyzer.export_project(int(project_id))
                
                if annotations_file:
                    st.success("✅ Archivo exportado exitosamente")
                    stats = analyzer.analyze_annotations_file(annotations_file)
                    
                    if stats:
                        display_statistics(stats)
                        os.remove(annotations_file)
                    else:
                        st.error("❌ No se pudieron analizar las anotaciones")
                else:
                    st.error("❌ No se pudo exportar el proyecto")
        else:
            st.error("⚠️ Por favor ingrese un ID de proyecto válido")

if __name__ == "__main__":
    main()