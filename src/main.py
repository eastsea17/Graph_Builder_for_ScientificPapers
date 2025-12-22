
import yaml
import os
import argparse
import logging
from extractor import Extractor
from graph_builder import GraphBuilder
from visualizer import Visualizer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_config(config_path="config.yaml"):
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logging.error(f"Config file not found at {config_path}")
        return None
    except Exception as e:
        logging.error(f"Error loading config: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Language Extraction and Graph Building")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    args = parser.parse_args()

    config = load_config(args.config)
    if not config:
        return

    logging.info("Starting extraction pipeline...")
    logging.info(f"Using model: {config['ollama']['selected_model']}")

    # 1. Extraction
    extractor = Extractor(config)
    results = extractor.process_csv(config['input_file'])
    
    if not results:
        logging.warning("No results extracted. Check input file or LLM connection.")
        return

    logging.info(f"Extracted data for {len(results)} papers.")

    # 2. Graph Building
    builder = GraphBuilder(config)
    builder.build_graph(results)
    
    # 3. Visualization
    vis = Visualizer(config)
    vis.create_visualization(results)
    
    logging.info("Pipeline completed successfully.")

if __name__ == "__main__":
    main()
