import pandas as pd
import geopandas as gpd
import folium
import logging
import branca.colormap as cm

from folium import Map
from pathlib import Path

from src.config import PATHS, SHAPE_FILES_CONFIG

def split_robustness(val:str):
    """
    Recebe uma string como "0,921 - 1,041" e retorna uma tupla (min, max).
    Trata casos de erro, nulos e formatação brasileira.

    Args:
        val (str): _description_
    """
    # 1. Casos de Nulo/Vazio
    if pd.isna(val):
        return 0.0, 0.0
    
    s_val = str(val).strip()
    if s_val in ['-', '', 'nan', 'None', 'Não contemplado']:
        return 0.0, 0.0
    
    # 2. Troca vírgula por ponto
    s_val = s_val.replace(',', '.')
    
    try:
        # 3. Caso Range: "0.921 - 1.041"
        if ' - ' in s_val:
            parts = s_val.split(' - ')
            # Retorna (Inferior, Superior)
            return float(parts[0]), float(parts[1])
        
        # 4. Caso Número Único: "4" ou "4.5" -> (4.5, 4.5)
        val_float = float(s_val)
        return val_float, val_float
        
    except ValueError:
        logging.warning(f"\nNão foi possível converter robustez: {val}")
        return 0.0, 0.0


def load_projects_data(filename: str) -> pd.DataFrame:
    """
    Carrega o Excel de projetos, converte coordenadas e calcula o Score.

    Args:
        filename (str): _description_

    Returns:
        pd.DataFrame: _description_
    """
    
    file_path = PATHS["xlsx"] / filename
    if not file_path:
        print("*"*3, "Error", "*"*3)
        raise FileNotFoundError(f"Arquivo xlsx não encontrado: {file_path}")
    
    logging.info(f"\nCarregando projetos de: {file_path}")
    
    df = pd.read_excel(file_path, sheet_name="ÁREAS BC")
    
    # assumir cenário comum: WGS 84 LAT/LON
    df['LAT'] = pd.to_numeric(df['LATITUDE'], errors="coerce")
    df['LON'] = pd.to_numeric(df['LONGITUDE'], errors="coerce")
    df = df.dropna(subset=['LAT', 'LON'])
    
    col_robustez = 'NÍVEL DE ROBUSTEZ' if 'NÍVEL DE ROBUSTEZ' in df.columns else 'POSIÇÃO DA ROBUSTEZ'
    
    # Aplica a função split_robustness e expande para duas colunas novas
    robustez_data = df[col_robustez].apply(split_robustness).tolist()
    df[['ROBUSTEZ_MIN', 'ROBUSTEZ_MAX']] = pd.DataFrame(robustez_data, index=df.index)
    
    # Cálculo do Score e Métricas
    df['MARGEM_ESCOAMENTO'] = pd.to_numeric(df['MARGEM DE ESCOAMENTO 2028/2029'], errors="coerce")
    
    # Normalização
    max_margem = df['MARGEM_ESCOAMENTO'].max()
    max_robust = df['ROBUSTEZ_MAX'].max()   # -> normaliza pelo maior valor possível do dataset
    
    # Proteção div/0
    max_margem = max_margem if max_margem > 0 else 1
    max_robust = max_robust if max_robust > 0 else 1
    
    # Score ponderado (70% escoamento, 30% robustez mínima)
    # utilizando a robustez minima (sendo conservador)
    df['Score'] = (0.7 * (df['MARGEM_ESCOAMENTO'] / max_margem) + \
                    0.3 * (df['ROBUSTEZ_MIN']) / max_robust)
    
    return df


def process_shape_layers(m: Map) -> None:
    """_summary_

    Args:
        m (Map): _description_
    """
    
    for layer_name, config in SHAPE_FILES_CONFIG.items():
        shape_paths = PATHS['shapes'] / config.file
        if not shape_paths.exists(): 
            raise FileNotFoundError(f'\nArquivos shapes não encontrados em: {shape_paths}')
        
        try:
            gdf = gpd.read_file(shape_paths)
            
            # faz o recorte do mapa somente para goias (o que interessa)
            
            # arquivos do setor elétrico não costumam ter padrão de nomeclatura
            # shapes de 2023 a coluna estado chama `UF`, de 2024 chama-se `ESTADO`
            # as vezes chama-se `sg_uf`
            
            # next coleta a primeira coluna que der certo e insere em col_estado
            col_estado = next(
                (col for col in ['UF', 'ESTADO', 'NOM_UF', 'sg_uf'] 
                if col in gdf.columns), None
            )
            if col_estado: gdf = gdf[gdf[col_estado] == 'GO']
            # corte espacial - "forca bruta"
            # se os arquivos shapefile não tiver coluna de estado:
                # solução é usar `.cx`, indexador espacial do Geopandas
                # defini-se um bounding box aproximada para Goiás usando
                # coordenadas geográficas
            else: gdf = gdf.cx[-53.5:-46.0, -19.5:-12.5]
            
            if gdf.empty:
                logging.warning(f'\ngdf para Goiás não encontrado em columas do shape ou recorte `.cx`')
            if gdf.crs != 'EPSG:4326': gdf = gdf.to_crs('EPSG:4326')
            
            
            col_nome = next(
                (col for col in ['NOME', 'NOM_LT', 'NOM_SE', 'nome'] 
                if col in gdf.columns), 'ID'
            )
            col_tensao = next(
                (col for col in ['TENSAO', 'V_NOMINAL', 'VOLTAGEM', 'tensao'] 
                if col in gdf.columns), ''
            )
            
            tooltip_fields = [col_nome] + ([col_tensao] if col_tensao else [])
            
            if config.type == 'line':
                folium.GeoJson(
                    gdf,
                    name=layer_name,
                    # atenção:
                        # aqui lambda recebe 2 argumentos: 'x' e 'cfg'
                        # sendo que 'cfg' é um argumento com valor padrão 'config'
                        # sintaxe da lambda:
                            # lambda sem valor padrão para os argumentos:
                                # lambda var1, var2, ...: returns;
                            # lambda com valor padrão para os argumentos:
                                # lambda var1, var2=valor_padrao: returns
                    style_function=lambda x, cfg=config: {
                                                            'color': cfg.color,
                                                            'weight': cfg.weight,
                                                            'dashArray': cfg.dash_array,
                                                            'opacity': cfg.opacity
                                                        },
                    tooltip=folium.GeoJsonTooltip(fields=tooltip_fields,
                                                  localize=True)
                ).add_to(m)
            elif config.type == 'point':
                for _, row in gdf.iterrows():
                    nome = row[col_nome] if col_nome in row else "SE"
                    tensao = f"{row[col_tensao]} kV" if col_tensao and col_tensao in row else ""
                    folium.CircleMarker(
                        location=[row.geometry.y, row.geometry.x],
                        radius=config.radius,
                        color=config.color,
                        fill=True,
                        fill_color=config.color,
                        fill_opacity=1,
                        popup=f"<b>{layer_name}</b><br>{nome}<br>{tensao}",
                        tooltip=f"{nome} {tensao}"
                    ).add_to(m)
            
        except Exception as e:
            logging.error(f"Erro em {layer_name}: {e}")
            
            
def add_bess_markers(m: Map, df: pd.DataFrame) -> None:
    """
    Adiciona marcadores com popup atualizado mostrando o range de robustez.

    Args:
        m (Map): _description_
        df (pd.DataFrame): _description_
    """
    
    colormap = cm.LinearColormap(colors=['blue', 'yellow', 'red'], 
                                 vmin=df['Score'].min(), vmax=df['Score'].max(), 
                                 caption='Ranking BESS')
    colormap.add_to(m)
    
    layer = folium.FeatureGroup(name="Projetos LRCAP 2025 Grupo BC")
    
    for _, row in df.iterrows():
        # HTML atualizado para mostrar Min e Max
        html = f"""
        <div style='font-family: sans-serif; width: 220px'>
            <h4 style='margin-bottom:0'>{row['MUNICIPIO']}</h4>
            <hr style='margin:5px 0'>
            <b>Potência:</b> {row['POTÊNCIA']} MW<br>
            <b>Margem Escoamento:</b> {row['MARGEM_ESCOAMENTO']} MW<br>
            <b>Robustez (Min-Max):</b> {row['ROBUSTEZ_MIN']:.3f} - {row['ROBUSTEZ_MAX']:.3f}<br>
            <br>
            <b>Score Final:</b> {row['Score']:.3f}
        </div>
        """
        folium.CircleMarker(
            location=[row['LAT'], row['LON']],
            radius=10 + (row['POTÊNCIA'] / 5),
            color=colormap(row['Score']),
            fill=True,
            fill_color=colormap(row['Score']),
            fill_opacity=0.8,
            popup=folium.Popup(html, max_width=260),
            tooltip=f"{row['MUNICIPIO']}"
        ).add_to(layer)
        
    layer.add_to(m)