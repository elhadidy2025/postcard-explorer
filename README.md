
# Postcard Explorer

Postcard Explorer is a visual analytics project for exploring postcard collections through image similarity, metadata filtering, clustering, and route-based exploration.

## Overview
The repository combines:
- a React + Vite frontend for interactive visualization and exploration,
- a Python backend for data processing and serving analysis results,
- notebook-based exploratory analysis and data profiling,
- processed postcard and clustering data for downstream visual analysis.

## Current project goals
- Browse and inspect postcard records visually
- Filter postcards by metadata such as route, topic, or attributes
- Explore clusters and semantic groupings
- Inspect travel-path and topic relationships in the data

## Repository structure
- `backend/` backend application and processing logic
- `frontend/` React frontend application
- `data/` source and processed postcard data assets
- `notebooks/` exploratory analysis notebooks
- `docs/` documentation and project notes
- `scripts/` helper scripts for data preparation and clustering
- `reports/` generated visual audit and cluster analysis reports

## Running the app
### Frontend
From the `frontend/` directory:

```bash
npm install
npm run dev
```

### Backend
Run the Python backend from the project root:

```bash
python backend/main.py
```

## Notes
This project is structured around interactive visual analysis workflows, with the frontend responsible for user-facing exploration and the backend/data pipeline supporting clustering and dataset-driven views.
