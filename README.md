# **Scientific Paper Info Extractor & Graph Builder (Advanced)**

This tool extracts structured information (Background, Purpose, Methodology, Results) from paper abstracts using Ollama LLMs, constructs a **Node/Edge Lists of Knowledge Graph** through semantic analysis, and generates an interactive multi-document visualization dashboard.

Recent updates include **Pydantic-based strict data validation**, **Advanced Entity Resolution**, and **Multiprocessing-based high-performance visualization**.

## **Key Features**

1. **Structured Extraction (with Pydantic)**:  
   * Enforces the LLM to strictly adhere to a defined JSON schema using Pydantic.  
   * Prevents common issues like missing fields or malformed JSON, ensuring data integrity.  
2. **Advanced Entity Resolution**:  
   * Goes beyond simple text matching by using **Embeddings** and **LLM Canonicalization** to merge synonyms.  
   * *Example: "CNN", "ConvNet", "Convolutional Neural Network" → Normalized to "Convolutional Neural Network".*  
3. **High-Performance Visualization**:  
   * Implements **Multiprocessing** for the computationally expensive text alignment task, significantly speeding up the processing of large datasets.  
4. **Auto-Thresholding Graph**:  
   * Dynamically adjusts the similarity threshold based on the data distribution to create an optimal network structure (avoiding hairball graphs).

## **Setup**

Requires Python 3.8+. Install the dependencies:

Bash

pip install pandas numpy pyyaml tqdm langextract pydantic networkx ollama

* **Prerequisites**:  
  * [Ollama](https://ollama.com/) must be installed and running (ollama serve).  
  * Pull the required models (e.g., your selected LLM and the embedding model):  
    Bash  
    ollama pull gpt-oss:120b-cloud  
    ollama pull nomic-embed-text

## **Usage**

1. Configuration (config.yaml):  
   Set your input file path, selected models, and similarity thresholds.  
2. **Run**:  
   Bash  
   python3 src/main.py \--config config.yaml

## **Output**

Results are saved in Output/generated/:

* **CSV Files** (for Graph Database/RAG):  
  * papers.csv: Paper nodes.  
  * entities.csv: Canonicalized entity nodes (Background, Methodology, etc.).  
  * relations.csv: Relationships (Paper-Entity and Entity-Entity similarity).  
* **Visualization**:  
  * graph\_visualization.html: **Main Dashboard**. Open this in your browser to explore the papers and graph.  
  * extraction\_results.jsonl: The raw extracted and aligned data.

## **Visualization Example**

![Graph Visualization Example](graph_visualization_example.png)

## **System Logic & Algorithms**

### **1\. Extraction Logic (src/extractor.py)**

* **Schema Enforcement**: Uses Pydantic models to inject a strict JSON schema into the system prompt.  
* **Validation**: Automatically validates the LLM output. If the output violates the schema (e.g., wrong data type), it handles the error to ensure only valid data enters the pipeline.

### **2\. Graph Builder Logic (src/graph\_builder.py)**

This module refines knowledge rather than just connecting text.

* **Entity Resolution**:  
  1. **Embedding**: Calculates vector embeddings for all extracted entities.  
  2. **Semantic Clustering**: Groups semantically similar entities using Cosine Similarity and NetworkX (Connected Components).  
  3. **Canonicalization (LLM)**: Asks the LLM to select or generate the most standard scientific term (Canonical Name) for each cluster.  
  4. **Merge**: Replaces original text with the canonical name in the graph, effectively removing duplicates.  
* **Semantic Relation**:  
  * Connects entities based on semantic similarity, using dynamic thresholding (similarity.mode: "auto") to keep only the top N% of strongest connections.

### **3\. Visualizer Logic (src/visualizer.py)**

* **Parallel Alignment**:  
  * The process of mapping extracted text back to the exact character indices in the source abstract is CPU-intensive.  
  * We use ProcessPoolExecutor to parallelize this task across all available CPU cores, drastically reducing processing time.  
* **Multi-Document Player**:  
  * Generates a unified HTML dashboard with a searchable sidebar and an embedded document viewer using the langextract library.

## **File Structure**

Plaintext

.  
├── Input  
│   └── rawdata.csv              \# Input CSV containing abstracts  
├── Output  
│   └── generated/               \# Generated results (HTML, CSV, JSONL)  
├── src  
│   ├── main.py                  \# Entry point  
│   ├── extractor.py             \# Pydantic-based structured extraction  
│   ├── graph\_builder.py         \# Entity Resolution & Graph Construction  
│   ├── visualizer.py            \# Multiprocessing Visualization Engine  
│   └── ollama\_client.py         \# Ollama API Wrapper  
├── config.yaml                  \# Configuration file  
└── README.md                    \# Documentation

## **License**

MIT License
