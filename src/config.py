from dataclasses import dataclass
from typing import Optional, Literal, Dict
from pathlib import Path
import os


# --- GERENCIAMENTO CENTRALIZADO DE CAMINHOS ---

ROOT_DIR = Path(__file__).resolve().parents[1]
PATHS = {
    "shapes": ROOT_DIR / "data" / "epe_shapes" / "brasil",
    "xlsx": ROOT_DIR / "data" / "xlsx_data",
    "outputs": ROOT_DIR / "outputs"
}
# Garante que a pasta de output existe
PATHS["outputs"].mkdir(parents=True, exist_ok=True)



# --- DEFINIÇÃO DA ESTRUTURA DE DADOS (DATACLASS) ---

@dataclass
class ShapeLayerConfig:
    """Regras de plotagem e leitura para cada arquivo Shapefile
    """
    file        : str
    type        : Literal['line', 'point']
    color       : str
    dash_array  : Optional[str] = None
    weight      : int = 2
    radius      : int = 3
    opacity     : float = 0.7
    
    
# --- CONFIGURAÇÃO DOS ARQUIVOS ---

SHAPE_FILES_CONFIG: Dict[str, ShapeLayerConfig] = {
    "LT Existente": ShapeLayerConfig(
        file="Linhas_de_Transmissão_-_Base_Existente.shp",
        type='line',
        color='#4A4A4A',
        weight=1.5,
        opacity=0.8
    ),
    "LT Planejada": ShapeLayerConfig(
        file="Linhas_de_Transmissão_-_Expansão_Planejada.shp",
        type='line',
        color='#D35400',
        dash_array='5, 5',
        weight=2,
        opacity=1.0
    ),
    "SE Existente": ShapeLayerConfig(
        file="Subestações_-_Base_Existente.shp",
        type="point",
        color='#2C3E50',
        radius=3,
        opacity=0.9
    ),
    "SE Planejada": ShapeLayerConfig(
        file="Subestações_-_Expansão_Planejada.shp",
        type="point",
        color='#E67E22',
        radius=4,
        opacity=1.0
    )
}