import folium
import logging

from folium.plugins import MousePosition

from src.config import PATHS
from src.auxiliaries import (
    load_projects_data, process_shape_layers, add_bess_markers
)


def main() -> None:
    
    logging.info("*** Generating Estrategic Map BC Projects ***")
    
    try:
        df_projects = load_projects_data("robustez_escoamento_-_alexandre.xlsx")
    except Exception as e:
        logging.critical(f"Fail to load sheet: {e}")
        return
    
    logging.info("\nInicializating base map...")
    # focusing on Goiás State
    m = folium.Map(
        location=[-16.0, -49.5],
        zoom_start=7,
        tiles="Cartodb Positron"
    )
    
    logging.info("\nProcessing EPE shape files...")
    # read configuration from src.config than draw lines/substations
    process_shape_layers(m)
    
    logging.info("\nPloting map and generating popups...")
    add_bess_markers(m, df_projects)
    
    # UI controls (finalization)
    folium.LayerControl(collapsed=False).add_to(m)  # layer panel opened
    MousePosition().add_to(m)   # shows lat/lon when hovering mouse
    
    logging.info("\nSaving the results...")
    output_file = PATHS["outputs"] / "LRCAP_BC_map.html"
    m.save(str(output_file))
    
    logging.info(f"\n*** SUCSESS ***")
    logging.info(f"Map saved in:\n{output_file}")



if __name__ == "__main__":
    main()
