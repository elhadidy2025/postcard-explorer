from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"

EMBEDDINGS_PATH = PROCESSED_DIR / "image_embeddings_sample.npy"
METADATA_PATH = PROCESSED_DIR / "postcards_sample_metadata.csv"

OUTPUT_PATH = PROCESSED_DIR / "postcards_sample_clusters.csv"

N_CLUSTERS = 8

embeddings = np.load(EMBEDDINGS_PATH)
metadata = pd.read_csv(METADATA_PATH)

print("Embeddings shape:", embeddings.shape)
print("Metadata rows:", len(metadata))

# Reduce dimensions for simple 2D visualization later
pca = PCA(n_components=2, random_state=42)
coords = pca.fit_transform(embeddings)

# Cluster image embeddings
kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=10)
clusters = kmeans.fit_predict(embeddings)

metadata["cluster"] = clusters
metadata["x"] = coords[:, 0]
metadata["y"] = coords[:, 1]

metadata.to_csv(OUTPUT_PATH, index=False)

print("Saved:", OUTPUT_PATH)
print("Cluster counts:")
print(metadata["cluster"].value_counts().sort_index())