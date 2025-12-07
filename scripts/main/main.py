import folium
import logging

from folium.plugins import MousePosition

from src.config import PATHS
from src.auxiliaries import (
    load_projects_data, process_shape_layers, add_bess_markers
)



    
logging.info("*** Generating Estrategic Map BC Projects ***")

try:
    df_projects = load_projects_data("robustez_escoamento_-_alexandre.xlsx")
except Exception as e:
    logging.critical(f"Fail to load sheet: {e}")

logging.info("\nInicializating base map...")

# focusing on Goiás State
m = folium.Map(
    location=[-16.0, -49.5], 
    zoom_start=7, 
    tiles='CartoDB Positron'
)

logging.info("\nProcessing EPE shape files...")
# read configuration from src.config than draw lines/substations
process_shape_layers(m)

logging.info("\nPloting map and generating popups...")
add_bess_markers(m, df_projects)

# box legend about 70/30 rule
legend_html = '''
     <div style="
     position: fixed; 
     bottom: 50px; left: 50px; width: 250px; height: 130px; 
     border:2px solid grey; z-index:9999; font-size:12px;
     background-color:white; opacity: 0.9;
     padding: 10px; border-radius: 5px; box-shadow: 2px 2px 5px rgba(0,0,0,0.3);
     ">
     <b>Metodologia de Ranking BESS</b><br>
     <hr style="margin:5px 0">
     <b>Peso Margem (2028/29):</b> 70%<br>
     <b>Peso Robustez (SCR):</b> 30%<br>
     <br>
     <i>Quanto maior o score, maior a atratividade do ponto.</i>
     </div>
     '''
m.get_root().html.add_child(folium.Element(legend_html))

# UI controls (finalization)
folium.LayerControl(collapsed=False).add_to(m)  # layer panel opened
MousePosition().add_to(m)   # shows lat/lon when hovering mouse

logging.info("\nSaving the results...")
output_file = PATHS["outputs"] / "LRCAP_BC_map.html"
m.save(str(output_file))

logging.info(f"\n*** SUCSESS ***")
logging.info(f"Map saved in:\n{output_file}")
