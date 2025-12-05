from pathlib import Path
from folium.plugins import MousePosition, MarkerCluster

import sys
import pandas as pd
import geopandas as gpd
import folium
import branca.colormap as cm


# --- 1. SETUP DE IMPORTAÇÃO E INICIALIZAÇÃO ---

# Adiciona a raiz do projeto ao Python Path para importar 'src'
# Estrutura: Root -> scripts -> main -> main.py
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]
sys.path.append(str(PROJECT_ROOT))

# importa os módulos em /src
from src.config import PATHS, SHAPE_FILES_CONFIG, ShapeLayerConfig
