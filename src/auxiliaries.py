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
    df.columns = df.columns.str.strip().str.replace('\n', ' ')
    
    # assumir cenário comum: WGS 84 LAT/LON
    df['LAT'] = pd.to_numeric(df['LATITUDE'], errors="coerce")
    df['LON'] = pd.to_numeric(df['LONGITUDE'], errors="coerce")
    df = df.dropna(subset=['LAT', 'LON'])
    
    col_robustez = 'NÍVEL DE ROBUSTEZ' if 'NÍVEL DE ROBUSTEZ' in df.columns else 'POSIÇÃO DA ROBUSTEZ'
    
    # Aplica a função split_robustness e expande para duas colunas novas
    robustez_data = df[col_robustez].apply(split_robustness).tolist()
    df[['ROBUSTEZ_MIN', 'ROBUSTEZ_MAX']] = pd.DataFrame(robustez_data, index=df.index)
    df['ROBUSTEZ_MED'] = (df['ROBUSTEZ_MIN'] + df['ROBUSTEZ_MAX']) / 2
    
    # Cálculo do Score e Métricas
    df['MARGEM_ESCOAMENTO'] = pd.to_numeric(df['MARGEM DE ESCOAMENTO 2028/2029'], errors="coerce").fillna(0)
    
    # Normalização
    # Score da Margem (Direto: Quanto maior, melhor)
    # Proteção div/0 ao fazer -> else 1
    max_margem = df['MARGEM_ESCOAMENTO'].max() if df['MARGEM_ESCOAMENTO'].max() > 0 else 1
    score_margem = df['MARGEM_ESCOAMENTO'] / max_margem
    
    # Score da Robustez (Inverso: Quanto menor o SCR, melhor para BESS)
    max_robust = df['ROBUSTEZ_MAX'].max() if df['ROBUSTEZ_MAX'].max() > 0 else 1    # -> normaliza pelo maior valor possível do dataset
    
    # Lógica: 1 - (Valor / Max). 
    # Exemplo: Se Max=3.0 e Valor=1.0 -> 1 - 0.33 = 0.66 (Bom)
    # Exemplo: Se Max=3.0 e Valor=3.0 -> 1 - 1.00 = 0.00 (Ruim)
    # Proteção: Se Robustez for 0 (sem dados), Score fica 0.
    df['SCORE_ROBUSTEZ'] = 0.0  # inicializado com 0
    mask_valid = df['ROBUSTEZ_MED'] > 0
    
    if mask_valid.any():
        vals = df.loc[mask_valid, 'ROBUSTEZ_MED']
        # Aplica inversão apenas onde há dados de robustez
        df.loc[mask_valid, 'SCORE_ROBUSTEZ'] = 1 - (vals / max_robust)
    
    
    # Score ponderado (70% escoamento, 30% robustez mínima)
    df['Score'] = (0.7 * score_margem) + (0.3 * df['SCORE_ROBUSTEZ'])
    
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
            
            # converting dates to string...
            # EPE shapefiles might have columns date and folium tries to
            # convert everything to JSON to build map in html...
            # Folium doesn't know how to convert python date/time objects by yourself
            for col in gdf.columns:
                if pd.api.types.is_datetime64_any_dtype(gdf[col]):
                    gdf[col] = gdf[col].astype(str)
            
            # search for names, voltages and concessions (shape columns)
            possible_names = ['Nome', 'NOME', 'NOM_LT', 'NOM_SE', 'nome', 'Name']
            possible_voltages = ['Tensao', 'TENSAO', 'V_NOMINAL', 'VOLTAGEM', 'tensao']
            # Novas variantes para Concessão
            possible_concessions = ['Concession', 'CONCESSION', 'Empresa', 'EMPRESA', 'Proprietario']
            
            col_nome = next(
                (col for col in possible_names if col in gdf.columns), gdf.columns[0]
            )
            col_tensao = next(
                (col for col in possible_voltages if col in gdf.columns), None
            )
            col_concessao = next(
                (col for col in possible_concessions if col in gdf.columns), None
            )
            
            # Tooltip Fields
            tooltip_fields = [col_nome]
            if col_tensao: tooltip_fields.append(col_tensao)
            if col_concessao: tooltip_fields.append(col_concessao)
            
            # Created a FeatureGroup for each layer.
            # It forces substations appear inside the legend
            layer_group = folium.FeatureGroup(name=layer_name)
            
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
                ).add_to(layer_group)
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
                    ).add_to(layer_group)
                    
            layer_group.add_to(m)   # add layer group to the final map
            
        except Exception as e:
            logging.error(f"Erro em {layer_name}: {e}")
            
            
def add_bess_markers(m: Map, df: pd.DataFrame) -> None:
    """
    Adiciona marcadores com popup atualizado mostrando o range de robustez.

    Args:
        m (Map): _description_
        df (pd.DataFrame): _description_
    """
    
    colormap = cm.LinearColormap(colors=['red', 'orange', 'yellow', 'green', 'darkgreen'], 
                                 vmin=df['Score'].min(),
                                 vmax=df['Score'].max(), 
                                 caption='Ranking BESS (Atratividade)')
    colormap.add_to(m)
    
    layer = folium.FeatureGroup(name="Projetos BESS 2026 Grupo BC")
    
    for _, row in df.iterrows():
        # HTML atualizado para mostrar Min e Max
        html = f"""
        <div style='font-family: sans-serif; width: 250px'>
            <h4 style='margin-bottom:0; color:#2C3E50'>{row['MUNICIPIO']}</h4>
            <hr style='margin:5px 0'>
            <b>Potência:</b> {row['POTÊNCIA']} MW<br>
            <b>Margem (2028/29):</b> {row['MARGEM_ESCOAMENTO']} MW<br>
            <b>Robustez (Min-Max):</b> {row['ROBUSTEZ_MIN']:.3f} - {row['ROBUSTEZ_MAX']:.3f}<br>
            <br>
            <b style='font-size:14px'>Score Final: {row['Score']:.3f}</b>
        </div>
        """
        folium.CircleMarker(
            location=[row['LAT'], row['LON']],
            radius=10 + (row['POTÊNCIA'] / 5),
            color='black', # Borda preta fina para destacar no fundo claro
            weight=1,      # Espessura da borda
            fill=True,
            fill_color=colormap(row['Score']),
            fill_opacity=0.8,
            popup=folium.Popup(html, max_width=280),
            tooltip=f"{row['MUNICIPIO']} (Score: {row['Score']:.2f})"
        ).add_to(layer)
        
    layer.add_to(m)