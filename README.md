
# Scientific Paper Info Extractor with LangExtract(Google) and Ollama

This tool extracts structured information (Background, Purpose, Methodology, Results) from paper abstracts using Ollama LLMs, generates a knowledge graph, and creates an interactive multi-document visualization dashboard.

## Setup

1. **Install Dependencies:**
   Ensure you have Python installed. The required packages are:

   ```bash
   pip install pandas requests numpy pyyaml tqdm langextract
   ```

   (Note: `langextract` is required for the visualization component.)

2. **Configure:**
   Values are set in `config.yaml`.
   - `input_file`: Path to CSV with abstracts.
   - `ollama.selected_model`: Choose between `local_small`, `cloud_large`, etc.
   - `similarity.enabled`: Toggle graph similarity edges.

## Usage

Run the main script:

```bash
python3 src/main.py
```

Or with a specific config:

```bash
python3 src/main.py --config config.yaml
```

## Output

Results are saved in `Output/generated/`:

- **CSV Files** (for GraphRAG/Database):
  - `papers.csv`: Paper nodes.
  - `research_background.csv`, etc.: Entity nodes.
  - `relations.csv`: Edges (Relationship between Paper-Entity and Entity-Entity similarity).
- **Visualization**:
  - `graph_visualization.html`: **Main Dashboard**. Open this file in a browser to navigate through all papers.
  - `pages/`: Contains individual HTML visualizations for each paper.

## System Logic & Algorithms

### 1. Graph Builder Logic (`src/graph_builder.py`)

The system transforms text into a graph:

- **Node Creation**: Converts Abstracts to `Paper` nodes and extracted fields to `Entity` nodes.
- **Edge Creation**: Links Papers to Entities (`HAS_METHODOLOGY`, etc.).
- **Semantic Similarity Algorithm**:
  - **Purpose**: To connect related research across different papers.
  - **Method**: Calculates Cosine Similarity between embeddings of all extracted entities.
  - **Result**: If similarity > threshold, creates a `RELATED_TO` edge. This reveals hidden connections (e.g., "UAV" and "Drone" are linked).

### 2. Visualizer Logic (`src/visualizer.py`)

The visualizer transforms structured data into an interactive HTML dashboard using `langextract`.

#### A. Text Alignment (The Core Challenge)

LLMs extract text strings, but visualization requires precise **character intervals** (indices) to highlight text in the original abstract.

- **WordAligner**: The system uses `langextract.resolver.WordAligner` to map extracted strings back to the source text.
- **Fuzzy Matching**: It employs both exact matching and fuzzy matching (using `difflib`) to handle minor discrepancies (like whitespace or punctuation changes) between the LLM output and the original text.

#### B. Multi-Document Dashboard Generation

Since the base library only visualizes single documents, the system implements a custom dashboard generator:

1. **Individual Page Generation**: Iterates through all aligned documents and generates a standard `langextract` HTML visualization for each, saving them to `Output/generated/pages/doc_{i}.html`.
2. **Dashboard Construction**: Creates a master `graph_visualization.html` containing:
    - A **Sidebar** listing all 119+ papers with search functionality.
    - An **IFrame** that dynamically loads the individual page corresponding to the selected paper.

<img width="3014" height="1394" alt="image" src="https://github.com/user-attachments/assets/441f785a-c99a-4769-a2fb-f162f3216317" />


## File Structure

```
.
├── Input
│   └── rawdata.csv              # Input CSV containing abstracts
├── Output
│   ├── generated/               # Generated results and visualization
│   │   ├── graph_visualization.html  # <--- OPEN THIS FILE
│   │   ├── pages/               # Individual abstract visualizations
│   │   ├── extraction_results.jsonl
│   │   └── *.csv                # Nodes and Relations
│   └── example/                 # Example output format
├── src
│   ├── main.py                  # Entry point
│   ├── extractor.py             # LLM extraction logic
│   ├── graph_builder.py         # Graph construction & Similarity
│   ├── visualizer.py            # Dashboard & Alignment logic
│   └── ollama_client.py         # Ollama API wrapper
├── config.yaml                  # Configuration
└── README.md
```
