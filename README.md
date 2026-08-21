# TestSigma Blast-Radius Engine 🚀
> **Graph-Driven Automated Test Selection & Impact Analysis Agent**

An agentic testing engine that calculates the precise failure propagation path (blast radius) of codebase changes. By constructing a **3-Layer Knowledge Graph** in Neo4j, it maps source-code component dependencies to high-level UI routes, product specifications (PRDs), and Playwright/pytest regression tests. 

Instead of running slow, expensive E2E test suites on every pull request, this engine inspects \git diff\ deltas, traverses the graph to mark impacted entities, executes only the affected test subset, and outputs a non-technical summary report (\latest_report.html\) for product managers and QA leads.

---

## 📸 Key Features

* **3-Layer Knowledge Graph:** Connects Code Components → UI Screens → Business Requirements → Test Scripts.
* **Sub-Millisecond Impact Traversal:** Executes optimized Neo4j Cypher queries to traverse dependency chains up to 3+ hops deep.
* **Visual Graph Mutation:** Automatically labels impacted nodes in red (\:Impacted\, \is_affected = true\) inside Neo4j Browser for instant visual observability.
* **Coverage Gap Detection:** Identifies unlinked UI routes, orphan components, and PRD requirements that lack test coverage.
* **Targeted Execution Engine:** Runs only the necessary \pytest\/Playwright test files mapped to the affected codebase delta.
* **Non-Technical QA Reporting:** Generates a clean \latest_report.html\ build artifact detailing impacted user flows and test pass/fail results.
* **GitHub Actions CI/CD Integration:** Runs automatically on commits, pushes, and pull requests via \.github/workflows/blast_radius.yml\.

---

## 🏗️ System Architecture

\\\
[ Git Delta / PR Changes ]
            │
            ▼
┌─────────────────────────┐
│  AST & File Parser      │ ── Syncs Graph Structure ──► ┌─────────────────────────┐
│  (sync_graph.py)        │                              │  Neo4j Knowledge Graph  │
└─────────────────────────┘                              │  (3-Layer Topology)     │
                                                         └────────────┬────────────┘
                                                                      │
┌─────────────────────────┐                                           │
│  Git Change Inspector   │ ── Modified Component Names ──────────────┤
│  (get_modified_comps)   │                                           │
└─────────────────────────┘                                           ▼
                                                         ┌─────────────────────────┐
                                                         │ calculate_blast_radius  │
                                                         │ (Cypher Traversal Engine)│
                                                         └────────────┬────────────┘
                                                                      │
                                                                      ▼
┌─────────────────────────┐                              ┌─────────────────────────┐
│  pytest / Playwright    │ ◄── Executes Impacted Tests ── │  Impacted Graph Nodes   │
│  Runner Engine          │                              │  (:Impacted Labels Set) │
└────────────┬────────────┘                              └─────────────────────────┘
             │
             ▼
┌─────────────────────────┐
│  latest_report.html     │
│  (Non-Tech QA Report)   │
└─────────────────────────┘
\\\

---

## 📂 Project Structure

\\\
.
├── .github/
│   └── workflows/
│       └── blast_radius.yml      # CI/CD pipeline configuration for GitHub Actions
├── crawler.py                    # Playwright UI route & screen dissector
├── sync_graph.py                 # AST component parser & Neo4j sync engine
├── TestSigma_App.py              # Core blast-radius orchestration driver
├── requirements.txt              # Python dependencies
├── latest_report.html            # Generated non-technical QA report artifact
└── README.md                     # Documentation
\\\

---

## 📊 3-Layer Knowledge Graph Schema

The system models application structure across three operational layers inside Neo4j:

1. **Layer 1 (Code Base):** \(:Component {name, full_path, is_affected})\
2. **Layer 2 (Product & UI):** \(:Screen {route, name, is_affected})\, \(:Requirement {id, title, is_affected})\
3. **Layer 3 (Validation):** \(:TestCase {id, file, is_affected})\

### Graph Relationships
* \(:Component)-[:DEPENDS_ON]->(:Component)\ — Code-level module imports.
* \(:Screen)-[:IMPLEMENTED_BY]->(:Component)\ — UI routes implemented by source files.
* \(:Requirement)-[:EXPECTS_UI]->(:Screen)\ — PRD specifications mapped to UI routes.
* \(:TestCase)-[:VERIFIES]->(:Requirement)\ — Automation test scripts verifying product features.

---

## 🚀 Quickstart & Local Setup

### 1. Prerequisites
* **Python:** \3.11+\
* **Git:** Installed and configured
* **Neo4j Instance:** Neo4j AuraDB (Cloud) or local Neo4j Desktop server

### 2. Installation
Clone the repository and install the dependencies:

\\\ash
git clone https://github.com/Ramsri1411/blastRadius.git
cd blastRadius

# Install dependencies
pip install -r requirements.txt
playwright install --with-deps
\\\

### 3. Environment Variables Setup
Set your Neo4j credentials in your local environment:

**PowerShell (Windows):**
\\\powershell
$env:NEO4J_URI="neo4j+s://<YOUR_DATABASE_ID>.databases.neo4j.io"
$env:NEO4J_USER="neo4j"
$env:NEO4J_PASSWORD="<YOUR_NEO4J_PASSWORD>"
\\\

### 4. Sync Knowledge Graph
Run the graph sync script to parse codebase ASTs, crawl application routes, and populate Neo4j:

\\\ash
python sync_graph.py
\\\

### 5. Execute Blast-Radius Engine
Make a change to any source file or simulate a Git change delta, then run the pipeline:

\\\ash
python TestSigma_App.py
\\\

After execution finishes, open \latest_report.html\ in any browser to inspect the impacted user flows, requirements, and test run outcomes.

---

## ⚙️ CI/CD Integration (GitHub Actions)

This repository includes a pre-configured GitHub Actions workflow located at \.github/workflows/blast_radius.yml\.

### Setting up GitHub Secrets
To allow the GitHub Actions runner to authenticate with your Neo4j instance:

1. Navigate to your repository on **GitHub**.
2. Click **Settings** → **Secrets and variables** → **Actions**.
3. Click **New repository secret** and add the following three environment variables:
   * \NEO4J_URI\
   * \NEO4J_USER\
   * \NEO4J_PASSWORD\

Once configured, every \git push\ or \pull_request\ will automatically trigger the blast-radius calculation, execute impacted tests, and upload \latest_report.html\ as a build artifact.

---

## 📋 Evaluation & Metrics

The system is measured against two primary operational criteria:

* **Determinism Rate (100% Target):** Graph traversals are strictly mathematical and yield identical test execution sets across 100 identical Git diff inputs.
* **Recall (100% Target):** Zero missed regressions—guarantees that every test script touching modified code dependencies is executed.
* **Precision (>85% Target):** Minimizes unnecessary test suite execution by ignoring unrelated components.
