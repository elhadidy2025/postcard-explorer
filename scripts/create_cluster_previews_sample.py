from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "data" / "Images"
PROCESSED_DIR = ROOT / "data" / "processed"
CLUSTERS_PATH = PROCESSED_DIR / "postcards_sample_clusters.csv"
OUTPUT_DIR = PROCESSED_DIR / "cluster_previews_sample"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(CLUSTERS_PATH)

THUMB_SIZE = 140
GRID_COLS = 5
MAX_IMAGES_PER_CLUSTER = 15
LABEL_HEIGHT = 24

for cluster_id in sorted(df["cluster"].unique()):
    cluster_df = df[df["cluster"] == cluster_id].head(MAX_IMAGES_PER_CLUSTER)

    rows = (len(cluster_df) + GRID_COLS - 1) // GRID_COLS
    canvas_width = GRID_COLS * THUMB_SIZE
    canvas_height = rows * (THUMB_SIZE + LABEL_HEIGHT)

    canvas = Image.new("RGB", (canvas_width, canvas_height), "white")
    draw = ImageDraw.Draw(canvas)

    for i, (_, row) in enumerate(cluster_df.iterrows()):
        image_path = IMAGE_DIR / row["name"]

        image = Image.open(image_path).convert("RGB")
        image.thumbnail((THUMB_SIZE, THUMB_SIZE))

        x = (i % GRID_COLS) * THUMB_SIZE
        y = (i // GRID_COLS) * (THUMB_SIZE + LABEL_HEIGHT)

        canvas.paste(image, (x, y))

        draw.text(
            (x + 4, y + THUMB_SIZE + 4),
            str(row["id"]),
            fill="black",
        )

    output_path = OUTPUT_DIR / f"cluster_{cluster_id}.jpg"
    canvas.save(output_path)

    print("Saved:", output_path)