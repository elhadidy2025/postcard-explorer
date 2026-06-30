from pathlib import Path

import numpy as np
import pandas as pd
import torch
import open_clip
from PIL import Image
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "data.json"
IMAGE_DIR = ROOT / "data" / "Images"
OUTPUT_DIR = ROOT / "data" / "processed"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BATCH_SIZE = 32

if torch.backends.mps.is_available():
    device = "mps"
elif torch.cuda.is_available():
    device = "cuda"
else:
    device = "cpu"

print("Using device:", device)

df = pd.read_json(DATA_PATH)

model, _, preprocess = open_clip.create_model_and_transforms(
    "ViT-B-32",
    pretrained="laion2b_s34b_b79k",
)

model = model.to(device)
model.eval()

embeddings = []
valid_rows = []

with torch.no_grad():
    for start in tqdm(range(0, len(df), BATCH_SIZE)):
        batch_df = df.iloc[start : start + BATCH_SIZE]

        images = []
        batch_rows = []

        for _, row in batch_df.iterrows():
            image_path = IMAGE_DIR / row["name"]

            try:
                image = Image.open(image_path).convert("RGB")
                image_tensor = preprocess(image)
                images.append(image_tensor)
                batch_rows.append(row)
            except Exception as e:
                print("Failed image:", image_path, e)

        if not images:
            continue

        image_batch = torch.stack(images).to(device)

        image_features = model.encode_image(image_batch)
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)

        embeddings.append(image_features.cpu().numpy())
        valid_rows.extend(batch_rows)

embeddings_array = np.vstack(embeddings)

np.save(OUTPUT_DIR / "image_embeddings.npy", embeddings_array)

pd.DataFrame(valid_rows).to_csv(
    OUTPUT_DIR / "postcards_metadata_with_images.csv",
    index=False,
)

print("Saved embeddings:", embeddings_array.shape)
print("Saved metadata rows:", len(valid_rows))
print("Output folder:", OUTPUT_DIR)