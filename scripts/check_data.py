from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "data.json"

df = pd.read_json(DATA_PATH)

print("Rows:", len(df))
print("Columns:")
print(df.columns.tolist())

print("\nFirst 3 rows:")
print(df.head(3))