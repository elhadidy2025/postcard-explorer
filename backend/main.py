from pathlib import Path

import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Postcard Explorer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "data.json"


def load_data():
    df = pd.read_json(DATA_PATH)
    df = df.fillna("")
    return df


@app.get("/")
def home():
    return {"message": "Postcard Explorer API is running"}


@app.get("/stats")
def get_stats():
    df = load_data()

    return {
        "total_postcards": len(df),
        "total_origin_countries": int(df["origin_country"].nunique()),
        "total_receiving_countries": int(df["receiving_country"].nunique()),
        "min_distance": float(df["distance"].min()),
        "max_distance": float(df["distance"].max()),
        "avg_distance": float(df["distance"].mean()),
    }


@app.get("/postcards")
def get_postcards(
    limit: int = 30,
    origin_country: str | None = None,
    receiving_country: str | None = None,
    min_distance: float | None = None,
    max_distance: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
):
    df = load_data()

    if origin_country:
        df = df[
            df["origin_country"].str.strip().str.lower()
            == origin_country.strip().lower()
        ]

    if receiving_country:
        df = df[
            df["receiving_country"].str.strip().str.lower()
            == receiving_country.strip().lower()
        ]

    if min_distance is not None:
        df = df[df["distance"] >= min_distance]

    if max_distance is not None:
        df = df[df["distance"] <= max_distance]

    if start_date:
        df = df[pd.to_datetime(df["date_sent"]) >= pd.to_datetime(start_date)]

    if end_date:
        df = df[pd.to_datetime(df["date_sent"]) <= pd.to_datetime(end_date)]

    if search and search.strip():
        search_columns = [
            "id",
            "name",
            "origin_country",
            "receiving_country",
            "origin_city",
            "receiving_city",
            "origin_region",
            "receiving_region",
            "origin_iso",
            "receiving_iso",
        ]

        searchable_text = (
            df[search_columns]
            .astype(str)
            .agg(" ".join, axis=1)
            .str.lower()
            .str.replace(r"\s+", " ", regex=True)
        )

        search_terms = search.lower().strip().split()

        mask = pd.Series(True, index=df.index)
        for term in search_terms:
            mask = mask & searchable_text.str.contains(term, regex=False, na=False)

        df = df[mask]

    postcards = df.head(limit).to_dict(orient="records")

    return {
        "total_matches": len(df),
        "count": len(postcards),
        "postcards": postcards,
    }

@app.get("/filter-options")
def get_filter_options():
    df = load_data()

    origin_countries = sorted(
        [country for country in df["origin_country"].unique().tolist() if country]
    )

    receiving_countries = sorted(
        [country for country in df["receiving_country"].unique().tolist() if country]
    )

    return {
        "origin_countries": origin_countries,
        "receiving_countries": receiving_countries,
    }