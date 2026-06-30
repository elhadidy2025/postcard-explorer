from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "data.json"
IMAGE_DIR = ROOT / "data" / "Images"

df = pd.read_json(DATA_PATH)

print("Rows in data.json:", len(df))
print("Images in folder:", len(list(IMAGE_DIR.glob("*"))))

missing = []

for _, row in df.iterrows():
    image_path = IMAGE_DIR / row["name"]
    if not image_path.exists():
        missing.append(row["name"])

print("Missing images:", len(missing))

if missing:
    print("First missing images:")
    print(missing[:10])
else:
    print("All records have images ✅")