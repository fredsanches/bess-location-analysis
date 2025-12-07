from dataclasses import dataclass
from typing import Optional, Literal, Dict
from pathlib import Path
import os


# --- GERENCIAMENTO CENTRALIZADO DE CAMINHOS ---

ROOT_DIR = Path(__file__).resolve().parents[1]
PATHS = {
    "shapes": ROOT_DIR / "data" / "epe_shapes" / "goias",
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
        color='#555555',
        weight=2
    ),
    "LT Planejada": ShapeLayerConfig(
        file="Linhas_de_Transmissão_-_Expansão_Planejada.shp",
        type='line',
        color='#FF8C00',
        dash_array='5, 5',
        weight=2
    ),
    "SE Existente": ShapeLayerConfig(
        file="Subestações_-_Base_Existente.shp",
        type="point",
        color='gray',
        radius=3
    ),
    "SE Planejada": ShapeLayerConfig(
        file="Subestações_-_Expansão_Planejada.shp",
        type="point",
        color="orange",
        radius=4
    )
}