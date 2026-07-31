from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import geonamescache
import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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
CLUSTERS_PATH = ROOT / "data" / "processed" / "postcards_image_clusters.csv"
IMAGE_DIR = ROOT / "data" / "Images"
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")

CLUSTER_NAMES = {
    0: "Landmarks & City Architecture",
    1: "Sunsets, Water & Calm Nature",
    2: "Animals & Wildlife",
    3: "Mixed Travel Postcards",
    4: "Religious Landmarks & Collages",
    5: "Art, Paintings & Illustrations",
    6: "Mountains & Natural Landscapes",
    7: "Decorative Objects & Flowers",
    8: "Uzbekistan Architecture",
    9: "Beaches, Islands & Sea Views",
    10: "People, Culture & Activities",
    11: "Maps, Flags & Graphic Cards",
}

CLUSTER_COLORS = {
    0: "#2563eb",
    1: "#0ea5e9",
    2: "#16a34a",
    3: "#f97316",
    4: "#7c3aed",
    5: "#db2777",
    6: "#22c55e",
    7: "#eab308",
    8: "#0891b2",
    9: "#06b6d4",
    10: "#ef4444",
    11: "#64748b",
}

TOPIC_HIERARCHY = [
    {
        "id": "nature",
        "label": "Nature & Landscape",
        "description": "Water, mountains, animals, flowers, sunsets, and natural views",
        "clusterIds": [1, 2, 6, 7, 9],
        "x": 24,
        "y": 34,
    },
    {
        "id": "architecture",
        "label": "Architecture & Places",
        "description": "Landmarks, city scenes, religious places, and Uzbekistan views",
        "clusterIds": [0, 4, 8],
        "x": 72,
        "y": 32,
    },
    {
        "id": "culture",
        "label": "Art & Culture",
        "description": "Paintings, illustrations, people, culture, and activities",
        "clusterIds": [5, 10],
        "x": 32,
        "y": 72,
    },
    {
        "id": "graphic",
        "label": "Graphic / Maps / Mixed",
        "description": "Maps, flags, graphic cards, and mixed travel postcards",
        "clusterIds": [3, 11],
        "x": 76,
        "y": 72,
    },
]

THEME_ALIASES = {
    "beach": ["beach", "sea", "island", "ocean", "water", "coast"],
    "nature": ["nature", "mountain", "landscape", "forest", "sunset", "flower", "animal"],
    "mountain": ["mountain", "landscape", "nature"],
    "animal": ["animal", "wildlife", "bird"],
    "architecture": ["architecture", "landmark", "city", "building", "religious"],
    "art": ["art", "painting", "illustration"],
    "religion": ["religious", "church", "mosque", "temple"],
    "map": ["map", "flag", "graphic"],
    "people": ["people", "culture", "activity"],
}


def normalize_text(value: Any) -> str:
    return str(value).strip().lower()


def normalize_city(value: Any) -> str:
    return (
        str(value)
        .strip()
        .lower()
        .replace(".", "")
        .replace("-", " ")
        .replace("_", " ")
    )


gc = geonamescache.GeonamesCache()
COUNTRIES = gc.get_countries()
CITIES = gc.get_cities()

CITY_LOOKUP: dict[tuple[str, str], tuple[float, float]] = {}
for city in CITIES.values():
    country_code = str(city.get("countrycode", "")).upper()
    city_name = normalize_city(city.get("name", ""))
    if country_code and city_name:
        CITY_LOOKUP[(country_code, city_name)] = (
            float(city["latitude"]),
            float(city["longitude"]),
        )

COUNTRY_NAME_TO_ISO: dict[str, str] = {}
for iso_code, country in COUNTRIES.items():
    COUNTRY_NAME_TO_ISO[normalize_text(country.get("name", ""))] = iso_code.upper()

COUNTRY_ALIASES = {
    "usa": "US",
    "united states": "US",
    "united states of america": "US",
    "uk": "GB",
    "united kingdom": "GB",
    "russia": "RU",
    "south korea": "KR",
    "north korea": "KP",
    "iran": "IR",
    "vietnam": "VN",
    "czech republic": "CZ",
    "czechia": "CZ",
    "vatican": "VA",
    "vatican city": "VA",
    "taiwan": "TW",
    "moldova": "MD",
    "syria": "SY",
    "laos": "LA",
    "bolivia": "BO",
    "venezuela": "VE",
    "tanzania": "TZ",
}


def get_country_iso(country_name: Any, iso_value: Any = "") -> str:
    iso_value = str(iso_value).strip().upper()
    if iso_value:
        return iso_value

    country_key = normalize_text(country_name)
    if country_key in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[country_key]
    return COUNTRY_NAME_TO_ISO.get(country_key, "")


def get_city_coordinates(city_name: Any, country_iso: Any) -> tuple[float, float] | None:
    country_iso = str(country_iso).strip().upper()
    city_key = normalize_city(city_name)
    if not country_iso or not city_key:
        return None
    return CITY_LOOKUP.get((country_iso, city_key))


def get_country_capital_coordinates(country_iso: Any) -> tuple[float, float] | None:
    country_iso = str(country_iso).strip().upper()
    if not country_iso:
        return None

    country = COUNTRIES.get(country_iso)
    if not country:
        return None

    capital_name = country.get("capital", "")
    if not capital_name:
        return None
    return get_city_coordinates(capital_name, country_iso)


def get_best_coordinates(city_name: Any, country_iso: Any) -> tuple[float, float] | None:
    city_coordinates = get_city_coordinates(city_name, country_iso)
    if city_coordinates:
        return city_coordinates
    return get_country_capital_coordinates(country_iso)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return default
        return value
    except (TypeError, ValueError):
        return default


def normalize_xy(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    min_value = numeric.min()
    max_value = numeric.max()
    if pd.isna(min_value) or pd.isna(max_value) or max_value == min_value:
        return pd.Series([50.0] * len(series), index=series.index)
    return 5 + (numeric - min_value) * 90 / (max_value - min_value)


def load_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        return pd.DataFrame()

    df = pd.read_json(DATA_PATH)
    return df.fillna("")


def add_spatial_layout(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure every postcard has x/y coordinates for the M2 spatial cluster view.

    If the clustering CSV already contains x/y or common embedding column names, those
    are used and normalized to a 0..100 visual canvas. If not, a deterministic fallback
    places postcards around their topic-group cluster center so the UI still has a real
    spatial layout instead of a non-spatial grid.
    """
    if df.empty:
        df["x"] = []
        df["y"] = []
        return df

    df = df.copy()

    x_candidates = ["x", "embedding_x", "umap_x", "tsne_x", "layout_x"]
    y_candidates = ["y", "embedding_y", "umap_y", "tsne_y", "layout_y"]

    x_source = next((col for col in x_candidates if col in df.columns), None)
    y_source = next((col for col in y_candidates if col in df.columns), None)

    if x_source and y_source:
        df["x"] = normalize_xy(df[x_source])
        df["y"] = normalize_xy(df[y_source])
        return df

    topic_centers: dict[int, tuple[float, float]] = {}
    for group in TOPIC_HIERARCHY:
        for cluster_id in group["clusterIds"]:
            topic_centers[int(cluster_id)] = (float(group["x"]), float(group["y"]))

    fallback_centers = [
        (18, 24),
        (38, 20),
        (58, 22),
        (78, 26),
        (22, 48),
        (45, 46),
        (66, 49),
        (82, 52),
        (25, 75),
        (48, 77),
        (68, 75),
        (84, 78),
    ]

    xs = []
    ys = []
    cluster_ordinals: dict[int, int] = {}

    for _, row in df.iterrows():
        cluster_id = int(safe_float(row.get("cluster", 0), 0))
        ordinal = cluster_ordinals.get(cluster_id, 0)
        cluster_ordinals[cluster_id] = ordinal + 1

        center = topic_centers.get(cluster_id)
        if center is None:
            center = fallback_centers[cluster_id % len(fallback_centers)]

        ring = ordinal // 12
        angle = (ordinal % 12) * (2 * math.pi / 12) + ring * 0.35
        radius = min(17, 4 + ring * 3.5)
        jitter_x = math.cos(angle) * radius
        jitter_y = math.sin(angle) * radius

        xs.append(max(3, min(97, center[0] + jitter_x)))
        ys.append(max(3, min(97, center[1] + jitter_y)))

    df["x"] = xs
    df["y"] = ys
    return df


def load_cluster_data() -> pd.DataFrame:
    base_df = load_data()

    if CLUSTERS_PATH.exists():
        cluster_df = pd.read_csv(CLUSTERS_PATH).fillna("")

        if not base_df.empty and "id" in base_df.columns and "id" in cluster_df.columns:
            cluster_columns = [
                col
                for col in cluster_df.columns
                if col == "id" or col not in base_df.columns
            ]
            df = base_df.merge(cluster_df[cluster_columns], on="id", how="left")
        else:
            df = cluster_df.copy()
    else:
        df = base_df.copy()

    if df.empty:
        return df

    if "cluster" not in df.columns:
        df["cluster"] = 0

    df["cluster"] = pd.to_numeric(df["cluster"], errors="coerce").fillna(0).astype(int)
    df["cluster_name"] = df["cluster"].map(CLUSTER_NAMES).fillna(
        df["cluster"].astype(str).map(lambda value: f"Cluster {value}")
    )
    df["cluster_color"] = df["cluster"].map(CLUSTER_COLORS).fillna("#64748b")

    if "name" in df.columns:
        df["image_url"] = "/images/" + df["name"].astype(str)
    elif "image_url" not in df.columns:
        df["image_url"] = ""

    for col in ["distance", "time"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return add_spatial_layout(df.fillna(""))


def parse_cluster_values(cluster: str | int | None) -> list[str]:
    if cluster is None:
        return []
    raw = str(cluster).strip()
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def apply_filters(
    df: pd.DataFrame,
    origin_country: str | None = None,
    receiving_country: str | None = None,
    search: str | None = None,
    min_distance: float | None = None,
    max_distance: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    cluster: str | int | None = None,
) -> pd.DataFrame:
    filtered = df.copy()

    if filtered.empty:
        return filtered

    if origin_country and "origin_country" in filtered.columns:
        filtered = filtered[
            filtered["origin_country"].astype(str).str.strip().str.lower()
            == normalize_text(origin_country)
        ]

    if receiving_country and "receiving_country" in filtered.columns:
        filtered = filtered[
            filtered["receiving_country"].astype(str).str.strip().str.lower()
            == normalize_text(receiving_country)
        ]

    cluster_values = parse_cluster_values(cluster)
    if cluster_values and "cluster" in filtered.columns:
        filtered = filtered[filtered["cluster"].astype(str).isin(cluster_values)]

    if min_distance not in (None, "") and "distance" in filtered.columns:
        filtered = filtered[pd.to_numeric(filtered["distance"], errors="coerce") >= float(min_distance)]

    if max_distance not in (None, "") and "distance" in filtered.columns:
        filtered = filtered[pd.to_numeric(filtered["distance"], errors="coerce") <= float(max_distance)]

    if start_date and "date_sent" in filtered.columns:
        date_sent = pd.to_datetime(filtered["date_sent"], errors="coerce")
        filtered = filtered[date_sent >= pd.to_datetime(start_date)]

    if end_date and "date_sent" in filtered.columns:
        date_sent = pd.to_datetime(filtered["date_sent"], errors="coerce")
        filtered = filtered[date_sent <= pd.to_datetime(end_date)]

    if search and str(search).strip():
        query = str(search).strip().lower()
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
            "cluster_name",
        ]

        mask = pd.Series(False, index=filtered.index)
        for column in search_columns:
            if column in filtered.columns:
                mask = mask | filtered[column].fillna("").astype(str).str.lower().str.contains(
                    query,
                    regex=False,
                    na=False,
                )

        if "cluster" in filtered.columns:
            mask = mask | filtered["cluster"].astype(str).str.contains(query, regex=False, na=False)

        cluster_text = filtered.get(
            "cluster_name",
            pd.Series("", index=filtered.index),
        ).fillna("").astype(str).str.lower()

        for alias, words in THEME_ALIASES.items():
            if query == alias or query in words:
                for word in words:
                    mask = mask | cluster_text.str.contains(word, regex=False, na=False)

        filtered = filtered[mask]

    return filtered


def records(df: pd.DataFrame) -> list[dict[str, Any]]:
    clean = df.where(pd.notna(df), None)
    return clean.to_dict(orient="records")


@app.get("/")
def home():
    return {"message": "Postcard Explorer API is running"}


@app.get("/stats")
def get_stats():
    df = load_data()
    if df.empty:
        return {
            "total_postcards": 0,
            "total_origin_countries": 0,
            "total_receiving_countries": 0,
            "min_distance": 0,
            "max_distance": 0,
            "avg_distance": 0,
        }

    distance = pd.to_numeric(df.get("distance", pd.Series(dtype=float)), errors="coerce")
    return {
        "total_postcards": int(len(df)),
        "total_origin_countries": int(df.get("origin_country", pd.Series(dtype=str)).nunique()),
        "total_receiving_countries": int(df.get("receiving_country", pd.Series(dtype=str)).nunique()),
        "min_distance": float(distance.min()) if not distance.empty else 0,
        "max_distance": float(distance.max()) if not distance.empty else 0,
        "avg_distance": float(distance.mean()) if not distance.empty else 0,
    }


@app.get("/filter-options")
def get_filter_options():
    df = load_data()
    if df.empty:
        return {"origin_countries": [], "receiving_countries": []}

    origin_series = df["origin_country"] if "origin_country" in df.columns else pd.Series(dtype=str)
    receiving_series = df["receiving_country"] if "receiving_country" in df.columns else pd.Series(dtype=str)

    return {
        "origin_countries": sorted([country for country in origin_series.unique().tolist() if country]),
        "receiving_countries": sorted([country for country in receiving_series.unique().tolist() if country]),
    }


@app.get("/topic-hierarchy")
def get_topic_hierarchy(
    origin_country: str | None = None,
    receiving_country: str | None = None,
    search: str | None = None,
    min_distance: float | None = None,
    max_distance: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    df = apply_filters(
        load_cluster_data(),
        origin_country=origin_country,
        receiving_country=receiving_country,
        search=search,
        min_distance=min_distance,
        max_distance=max_distance,
        start_date=start_date,
        end_date=end_date,
    )

    groups = []
    for group in TOPIC_HIERARCHY:
        group_df = df[df["cluster"].isin(group["clusterIds"])] if not df.empty else df
        samples = group_df.head(6)[[col for col in ["id", "name", "image_url"] if col in group_df.columns]]
        groups.append(
            {
                **group,
                "count": int(len(group_df)),
                "samples": records(samples) if not samples.empty else [],
            }
        )

    return {"groups": groups, "total_matches": int(len(df))}


@app.get("/postcards")
def get_postcards(
    limit: int = Query(80, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    origin_country: str | None = None,
    receiving_country: str | None = None,
    min_distance: float | None = None,
    max_distance: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
    cluster: str | None = None,
):
    df = apply_filters(
        load_cluster_data(),
        origin_country=origin_country,
        receiving_country=receiving_country,
        min_distance=min_distance,
        max_distance=max_distance,
        start_date=start_date,
        end_date=end_date,
        search=search,
        cluster=cluster,
    )

    total_matches = len(df)
    page_df = df.iloc[offset : offset + limit]
    return {
        "total_matches": int(total_matches),
        "count": int(len(page_df)),
        "offset": offset,
        "limit": limit,
        "has_previous": offset > 0,
        "has_next": offset + limit < total_matches,
        "postcards": records(page_df),
    }


@app.get("/image-cluster-overview")
def get_image_cluster_overview(
    origin_country: str | None = None,
    receiving_country: str | None = None,
    min_distance: float | None = None,
    max_distance: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
):
    df = apply_filters(
        load_cluster_data(),
        origin_country=origin_country,
        receiving_country=receiving_country,
        min_distance=min_distance,
        max_distance=max_distance,
        start_date=start_date,
        end_date=end_date,
        search=search,
    )

    overview = []
    if not df.empty:
        for cluster_id in sorted(df["cluster"].dropna().astype(int).unique()):
            cluster_df = df[df["cluster"] == cluster_id]
            sample_columns = [
                column
                for column in [
                    "id",
                    "name",
                    "origin_country",
                    "receiving_country",
                    "origin_city",
                    "receiving_city",
                    "image_url",
                ]
                if column in cluster_df.columns
            ]

            overview.append(
                {
                    "cluster": int(cluster_id),
                    "cluster_name": CLUSTER_NAMES.get(int(cluster_id), f"Cluster {cluster_id}"),
                    "cluster_color": CLUSTER_COLORS.get(int(cluster_id), "#64748b"),
                    "count": int(len(cluster_df)),
                    "x": float(pd.to_numeric(cluster_df["x"], errors="coerce").mean()),
                    "y": float(pd.to_numeric(cluster_df["y"], errors="coerce").mean()),
                    "samples": records(cluster_df.head(8)[sample_columns]),
                }
            )

    return {
        "total_matches": int(len(df)),
        "clusters": overview,
        "layout": "embedding_xy_or_deterministic_spatial_fallback",
    }


@app.get("/image-clusters")
def get_image_clusters(
    limit: int = Query(300, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    cluster: str | None = None,
    origin_country: str | None = None,
    receiving_country: str | None = None,
    min_distance: float | None = None,
    max_distance: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
):
    df = apply_filters(
        load_cluster_data(),
        origin_country=origin_country,
        receiving_country=receiving_country,
        min_distance=min_distance,
        max_distance=max_distance,
        start_date=start_date,
        end_date=end_date,
        search=search,
        cluster=cluster,
    )

    total_matches = len(df)
    page_df = df.iloc[offset : offset + limit]
    return {
        "total_matches": int(total_matches),
        "count": int(len(page_df)),
        "offset": offset,
        "limit": limit,
        "has_previous": offset > 0,
        "has_next": offset + limit < total_matches,
        "points": records(page_df),
    }


def build_routes(df: pd.DataFrame, limit: int) -> tuple[int, list[dict[str, Any]]]:
    routes = []
    total_matches = len(df)

    for _, row in df.iterrows():
        if len(routes) >= limit:
            break

        origin_iso = get_country_iso(row.get("origin_country", ""), row.get("origin_iso", ""))
        receiving_iso = get_country_iso(row.get("receiving_country", ""), row.get("receiving_iso", ""))

        origin_coordinates = get_best_coordinates(row.get("origin_city", ""), origin_iso)
        receiving_coordinates = get_best_coordinates(row.get("receiving_city", ""), receiving_iso)

        if not origin_coordinates or not receiving_coordinates:
            continue

        cluster_id = int(safe_float(row.get("cluster", 0), 0))
        routes.append(
            {
                "id": row.get("id", ""),
                "name": row.get("name", ""),
                "origin_country": row.get("origin_country", ""),
                "receiving_country": row.get("receiving_country", ""),
                "origin_city": row.get("origin_city", ""),
                "receiving_city": row.get("receiving_city", ""),
                "origin_iso": origin_iso,
                "receiving_iso": receiving_iso,
                "origin_lat": origin_coordinates[0],
                "origin_lon": origin_coordinates[1],
                "receiving_lat": receiving_coordinates[0],
                "receiving_lon": receiving_coordinates[1],
                "distance": safe_float(row.get("distance", 0)),
                "time": safe_float(row.get("time", 0)),
                "date_sent": row.get("date_sent", ""),
                "date_received": row.get("date_received", ""),
                "cluster": cluster_id,
                "cluster_name": CLUSTER_NAMES.get(cluster_id, "Unknown cluster"),
                "cluster_color": CLUSTER_COLORS.get(cluster_id, "#64748b"),
                "image_url": row.get("image_url", ""),
            }
        )

    return total_matches, routes


@app.get("/routes")
def get_routes(
    limit: int = Query(1200, ge=1, le=10000),
    origin_country: str | None = None,
    receiving_country: str | None = None,
    min_distance: float | None = None,
    max_distance: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
    cluster: str | None = None,
):
    df = apply_filters(
        load_cluster_data(),
        origin_country=origin_country,
        receiving_country=receiving_country,
        min_distance=min_distance,
        max_distance=max_distance,
        start_date=start_date,
        end_date=end_date,
        search=search,
        cluster=cluster,
    )
    total_matches, routes = build_routes(df, limit)
    return {
        "total_matches": int(total_matches),
        "count": int(len(routes)),
        "limit": limit,
        "routes": routes,
    }


@app.get("/route-aggregates")
def get_route_aggregates(
    limit: int = Query(800, ge=1, le=5000),
    origin_country: str | None = None,
    receiving_country: str | None = None,
    min_distance: float | None = None,
    max_distance: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
    cluster: str | None = None,
):
    df = apply_filters(
        load_cluster_data(),
        origin_country=origin_country,
        receiving_country=receiving_country,
        min_distance=min_distance,
        max_distance=max_distance,
        start_date=start_date,
        end_date=end_date,
        search=search,
        cluster=cluster,
    )

    if df.empty:
        return {"total_cards": 0, "count": 0, "aggregates": []}

    rows = []
    for _, row in df.iterrows():
        origin_iso = get_country_iso(row.get("origin_country", ""), row.get("origin_iso", ""))
        receiving_iso = get_country_iso(row.get("receiving_country", ""), row.get("receiving_iso", ""))
        if not origin_iso or not receiving_iso:
            continue

        origin_coordinates = get_country_capital_coordinates(origin_iso) or get_best_coordinates(
            row.get("origin_city", ""),
            origin_iso,
        )
        receiving_coordinates = get_country_capital_coordinates(receiving_iso) or get_best_coordinates(
            row.get("receiving_city", ""),
            receiving_iso,
        )
        if not origin_coordinates or not receiving_coordinates:
            continue

        cluster_id = int(safe_float(row.get("cluster", 0), 0))
        rows.append(
            {
                "cluster": cluster_id,
                "cluster_name": CLUSTER_NAMES.get(cluster_id, "Unknown cluster"),
                "cluster_color": CLUSTER_COLORS.get(cluster_id, "#64748b"),
                "origin_country": row.get("origin_country", ""),
                "receiving_country": row.get("receiving_country", ""),
                "origin_iso": origin_iso,
                "receiving_iso": receiving_iso,
                "origin_lat": origin_coordinates[0],
                "origin_lon": origin_coordinates[1],
                "receiving_lat": receiving_coordinates[0],
                "receiving_lon": receiving_coordinates[1],
                "distance": safe_float(row.get("distance", 0)),
                "time": safe_float(row.get("time", 0)),
                "id": row.get("id", ""),
            }
        )

    route_df = pd.DataFrame(rows)
    if route_df.empty:
        return {"total_cards": int(len(df)), "count": 0, "aggregates": []}

    grouped = (
        route_df.groupby(
            [
                "cluster",
                "cluster_name",
                "cluster_color",
                "origin_country",
                "receiving_country",
                "origin_iso",
                "receiving_iso",
                "origin_lat",
                "origin_lon",
                "receiving_lat",
                "receiving_lon",
            ],
            dropna=False,
        )
        .agg(
            route_count=("id", "count"),
            avg_distance=("distance", "mean"),
            avg_time=("time", "mean"),
        )
        .reset_index()
        .sort_values("route_count", ascending=False)
        .head(limit)
    )

    grouped["id"] = grouped.apply(
        lambda row: f"{row['cluster']}-{row['origin_iso']}-{row['receiving_iso']}",
        axis=1,
    )

    return {
        "total_cards": int(len(df)),
        "count": int(len(grouped)),
        "aggregates": records(grouped),
    }


@app.get("/outliers")
def get_outliers(
    origin_country: str | None = None,
    receiving_country: str | None = None,
    search: str | None = None,
    min_distance: float | None = None,
    max_distance: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    cluster: str | None = None,
    threshold: float = Query(2.0, ge=0.5, le=5.0),
    limit: int = Query(24, ge=1, le=200),
):
    """E2: highlight postcards with exceedingly long arrival time.

    Distance is retained as context, but the outlier trigger is deliberately the
    positive travel-time z-score, matching the requirement wording.
    """
    df = apply_filters(
        load_cluster_data(),
        origin_country=origin_country,
        receiving_country=receiving_country,
        search=search,
        min_distance=min_distance,
        max_distance=max_distance,
        start_date=start_date,
        end_date=end_date,
        cluster=cluster,
    ).copy()

    total_filtered = len(df)
    if df.empty or "time" not in df.columns:
        return {"outliers": [], "count": 0, "total_filtered": int(total_filtered), "threshold": threshold}

    df["time"] = pd.to_numeric(df["time"], errors="coerce")
    df["distance"] = pd.to_numeric(df.get("distance", 0), errors="coerce")
    df = df.dropna(subset=["time"]).copy()

    if df.empty:
        return {"outliers": [], "count": 0, "total_filtered": int(total_filtered), "threshold": threshold}

    time_mean = df["time"].mean()
    time_std = df["time"].std()
    if pd.isna(time_std) or time_std == 0:
        time_std = 1

    distance_mean = df["distance"].mean()
    distance_std = df["distance"].std()
    if pd.isna(distance_std) or distance_std == 0:
        distance_std = 1

    df["time_z"] = (df["time"] - time_mean) / time_std
    df["distance_z"] = (df["distance"] - distance_mean) / distance_std
    df["outlier_score"] = df["time_z"]
    df["outlier_reason"] = df["time"].round().astype(int).astype(str) + " days: exceedingly long arrival time"

    outliers = df[df["time_z"] >= threshold].sort_values("time_z", ascending=False).head(limit)
    result_columns = [
        "id",
        "name",
        "origin_country",
        "receiving_country",
        "origin_city",
        "receiving_city",
        "distance",
        "time",
        "date_sent",
        "date_received",
        "cluster",
        "cluster_name",
        "cluster_color",
        "image_url",
        "distance_z",
        "time_z",
        "outlier_score",
        "outlier_reason",
    ]
    existing_columns = [col for col in result_columns if col in outliers.columns]

    return {
        "outliers": records(outliers[existing_columns]),
        "count": int(len(outliers)),
        "total_filtered": int(total_filtered),
        "threshold": threshold,
    }


# === EOE CLEAN DRILLDOWN MAP START ===
# Final clean backend patch.
# Purpose:
# - Never show 10k+ routes immediately.
# - Provide clean drill-down data:
#   topics -> clusters -> country-pair flows -> individual cards.
# - Uses real data from data.json + processed postcard clusters.
# - Does not depend on old broken stacked EOE patches.

from fastapi import Query as _EOE_Query


_EOE_TOPIC_HIERARCHY = [
    {
        "id": "nature",
        "label": "Nature & Landscape",
        "description": "Water, mountains, animals, flowers, sunsets, and natural views",
        "clusterIds": [1, 2, 6, 7, 9],
        "color": "#16a34a",
        "lat": 42.0,
        "lon": -28.0,
    },
    {
        "id": "architecture",
        "label": "Architecture & Places",
        "description": "Landmarks, cities, religious places, and Uzbekistan views",
        "clusterIds": [0, 4, 8],
        "color": "#2563eb",
        "lat": 44.0,
        "lon": 36.0,
    },
    {
        "id": "culture",
        "label": "Art & Culture",
        "description": "Paintings, illustrations, people, culture, and activities",
        "clusterIds": [5, 10],
        "color": "#db2777",
        "lat": 8.0,
        "lon": -12.0,
    },
    {
        "id": "graphic",
        "label": "Graphic / Maps / Mixed",
        "description": "Maps, flags, graphic cards, and mixed travel postcards",
        "clusterIds": [3, 11],
        "color": "#64748b",
        "lat": 6.0,
        "lon": 52.0,
    },
]

_EOE_CLUSTER_POSITIONS = {
    0: (52.0, 5.0),
    1: (48.0, -58.0),
    2: (32.0, -78.0),
    3: (-3.0, 68.0),
    4: (41.0, 42.0),
    5: (12.0, -42.0),
    6: (45.0, -92.0),
    7: (28.0, -25.0),
    8: (40.0, 68.0),
    9: (5.0, -70.0),
    10: (2.0, 8.0),
    11: (-18.0, 82.0),
}

_EOE_CLUSTER_NAMES = {
    0: "Landmarks & City Architecture",
    1: "Sunsets, Water & Calm Nature",
    2: "Animals & Wildlife",
    3: "Mixed Travel Postcards",
    4: "Religious Landmarks & Collages",
    5: "Art, Paintings & Illustrations",
    6: "Mountains & Natural Landscapes",
    7: "Decorative Objects & Flowers",
    8: "Uzbekistan Architecture",
    9: "Beaches, Islands & Sea Views",
    10: "People, Culture & Activities",
    11: "Maps, Flags & Graphic Cards",
}

_EOE_CLUSTER_COLORS = {
    0: "#2563eb",
    1: "#0ea5e9",
    2: "#16a34a",
    3: "#f97316",
    4: "#7c3aed",
    5: "#db2777",
    6: "#22c55e",
    7: "#eab308",
    8: "#0891b2",
    9: "#06b6d4",
    10: "#ef4444",
    11: "#64748b",
}


def _eoe_remove_get_routes(*paths):
    app.router.routes[:] = [
        route
        for route in app.router.routes
        if not (
            getattr(route, "path", None) in paths
            and "GET" in getattr(route, "methods", set())
        )
    ]


def _eoe_safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return default
        value = float(value)
        if pd.isna(value):
            return default
        return value
    except Exception:
        return default


def _eoe_records(df):
    if df is None or len(df) == 0:
        return []

    clean = df.copy()
    clean = clean.where(pd.notna(clean), None)

    records = clean.to_dict(orient="records")

    for record in records:
        for key, value in list(record.items()):
            if hasattr(value, "item"):
                try:
                    record[key] = value.item()
                except Exception:
                    pass

    return records


def _eoe_topic_for_cluster(cluster_id):
    cluster_id = int(_eoe_safe_float(cluster_id, 0))

    for topic in _EOE_TOPIC_HIERARCHY:
        if cluster_id in topic["clusterIds"]:
            return topic

    return {
        "id": "mixed",
        "label": "Mixed / Other",
        "description": "Other postcard topics",
        "clusterIds": [cluster_id],
        "color": "#334155",
        "lat": 0.0,
        "lon": 0.0,
    }


def _eoe_read_metadata():
    if not DATA_PATH.exists():
        return pd.DataFrame()

    df = pd.read_json(DATA_PATH)
    df = df.fillna("")

    return df


def _eoe_read_clusters():
    if not CLUSTERS_PATH.exists():
        return pd.DataFrame()

    df = pd.read_csv(CLUSTERS_PATH)
    df = df.fillna("")

    return df


def load_cluster_data():
    meta_df = _eoe_read_metadata()
    cluster_df = _eoe_read_clusters()

    if meta_df.empty and cluster_df.empty:
        return pd.DataFrame()

    if meta_df.empty:
        df = cluster_df.copy()
    elif cluster_df.empty:
        df = meta_df.copy()
    else:
        join_key = None

        if "id" in meta_df.columns and "id" in cluster_df.columns:
            join_key = "id"
        elif "name" in meta_df.columns and "name" in cluster_df.columns:
            join_key = "name"

        if join_key:
            extra_cols = [
                col for col in cluster_df.columns
                if col == join_key or col not in meta_df.columns
            ]
            df = meta_df.merge(cluster_df[extra_cols], on=join_key, how="left")
        else:
            df = cluster_df.copy()

    df = df.fillna("")

    if "id" not in df.columns:
        df["id"] = [f"card-{i}" for i in range(len(df))]

    if "name" not in df.columns:
        df["name"] = df["id"].astype(str)

    if "cluster" not in df.columns:
        df["cluster"] = [i % 12 for i in range(len(df))]

    df["cluster"] = pd.to_numeric(df["cluster"], errors="coerce").fillna(0).astype(int)

    df["cluster_name"] = df["cluster"].map(_EOE_CLUSTER_NAMES).fillna("Unknown cluster")
    df["cluster_color"] = df["cluster"].map(_EOE_CLUSTER_COLORS).fillna("#64748b")

    if "image_url" not in df.columns:
        df["image_url"] = "/images/" + df["name"].astype(str)
    else:
        df["image_url"] = df["image_url"].replace("", pd.NA)
        df["image_url"] = df["image_url"].fillna("/images/" + df["name"].astype(str))

    topic_ids = []
    topic_names = []
    topic_colors = []

    for cluster_id in df["cluster"]:
        topic = _eoe_topic_for_cluster(cluster_id)
        topic_ids.append(topic["id"])
        topic_names.append(topic["label"])
        topic_colors.append(topic["color"])

    df["topic_group_id"] = topic_ids
    df["topic_group_name"] = topic_names
    df["topic_group_color"] = topic_colors

    numeric_columns = ["distance", "time"]
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        else:
            df[col] = 0

    for col in [
        "origin_country",
        "receiving_country",
        "origin_city",
        "receiving_city",
        "origin_iso",
        "receiving_iso",
        "date_sent",
        "date_received",
    ]:
        if col not in df.columns:
            df[col] = ""

    return df


def apply_filters(
    df,
    origin_country=None,
    receiving_country=None,
    search=None,
    min_distance=None,
    max_distance=None,
    start_date=None,
    end_date=None,
    cluster=None,
):
    filtered = df.copy()

    if origin_country:
        filtered = filtered[
            filtered["origin_country"].astype(str).str.strip().str.lower()
            == str(origin_country).strip().lower()
        ]

    if receiving_country:
        filtered = filtered[
            filtered["receiving_country"].astype(str).str.strip().str.lower()
            == str(receiving_country).strip().lower()
        ]

    if cluster is not None and str(cluster).strip() != "":
        values = [v.strip() for v in str(cluster).split(",") if v.strip()]
        filtered = filtered[filtered["cluster"].astype(str).isin(values)]

    if min_distance not in (None, ""):
        filtered = filtered[pd.to_numeric(filtered["distance"], errors="coerce") >= float(min_distance)]

    if max_distance not in (None, ""):
        filtered = filtered[pd.to_numeric(filtered["distance"], errors="coerce") <= float(max_distance)]

    if start_date:
        filtered = filtered[
            pd.to_datetime(filtered["date_sent"], errors="coerce")
            >= pd.to_datetime(start_date)
        ]

    if end_date:
        filtered = filtered[
            pd.to_datetime(filtered["date_sent"], errors="coerce")
            <= pd.to_datetime(end_date)
        ]

    if search and str(search).strip():
        q = str(search).strip().lower()

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
            "cluster_name",
            "topic_group_name",
        ]

        mask = pd.Series(False, index=filtered.index)

        for col in search_columns:
            if col in filtered.columns:
                mask = mask | filtered[col].fillna("").astype(str).str.lower().str.contains(q, regex=False)

        filtered = filtered[mask]

    return filtered


def _eoe_get_iso(row, side):
    country_col = f"{side}_country"
    iso_col = f"{side}_iso"

    return get_country_iso(row.get(country_col, ""), row.get(iso_col, ""))


def _eoe_get_coords(row, side):
    iso = _eoe_get_iso(row, side)
    city = row.get(f"{side}_city", "")

    coords = get_best_coordinates(city, iso)

    if coords:
        return coords

    return get_country_capital_coordinates(iso)


def _eoe_cluster_node(cluster_id, cluster_df):
    cluster_id = int(cluster_id)
    lat, lon = _EOE_CLUSTER_POSITIONS.get(cluster_id, (0.0, 0.0))
    topic = _eoe_topic_for_cluster(cluster_id)

    samples = []
    sample_cols = [col for col in ["id", "name", "image_url"] if col in cluster_df.columns]

    if sample_cols:
        samples = _eoe_records(cluster_df.head(5)[sample_cols])

    return {
        "id": f"cluster-{cluster_id}",
        "type": "cluster",
        "cluster": cluster_id,
        "label": _EOE_CLUSTER_NAMES.get(cluster_id, f"Cluster {cluster_id}"),
        "color": _EOE_CLUSTER_COLORS.get(cluster_id, "#64748b"),
        "topic_group_id": topic["id"],
        "topic_group_name": topic["label"],
        "count": int(len(cluster_df)),
        "lat": lat,
        "lon": lon,
        "samples": samples,
    }


_eoe_remove_get_routes(
    "/postcards",
    "/image-cluster-overview",
    "/image-clusters",
    "/outliers",
    "/map-drilldown",
)


@app.get("/postcards")
def get_postcards(
    limit: int = _EOE_Query(36, ge=1, le=1000),
    offset: int = _EOE_Query(0, ge=0),
    origin_country: str | None = None,
    receiving_country: str | None = None,
    min_distance: float | None = None,
    max_distance: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
    cluster: str | None = None,
):
    df = apply_filters(
        load_cluster_data(),
        origin_country=origin_country,
        receiving_country=receiving_country,
        min_distance=min_distance,
        max_distance=max_distance,
        start_date=start_date,
        end_date=end_date,
        search=search,
        cluster=cluster,
    )

    total = len(df)
    page = df.iloc[offset: offset + limit]

    return {
        "total_matches": int(total),
        "count": int(len(page)),
        "offset": int(offset),
        "limit": int(limit),
        "postcards": _eoe_records(page),
    }


@app.get("/map-drilldown")
def get_map_drilldown(
    level: str = _EOE_Query("topics", pattern="^(topics|clusters|pairs|cards)$"),
    topic_id: str | None = None,
    cluster: int | None = None,
    origin_iso: str | None = None,
    receiving_iso: str | None = None,
    limit: int = _EOE_Query(80, ge=1, le=500),
    origin_country: str | None = None,
    receiving_country: str | None = None,
    search: str | None = None,
    min_distance: float | None = None,
    max_distance: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    df = apply_filters(
        load_cluster_data(),
        origin_country=origin_country,
        receiving_country=receiving_country,
        search=search,
        min_distance=min_distance,
        max_distance=max_distance,
        start_date=start_date,
        end_date=end_date,
    )

    if topic_id:
        topic = next((t for t in _EOE_TOPIC_HIERARCHY if t["id"] == topic_id), None)
        if topic:
            df = df[df["cluster"].isin(topic["clusterIds"])]

    if cluster is not None:
        df = df[df["cluster"] == int(cluster)]

    total_cards = int(len(df))

    if level == "topics":
        nodes = []

        for topic in _EOE_TOPIC_HIERARCHY:
            topic_df = df[df["cluster"].isin(topic["clusterIds"])]

            if topic_df.empty:
                continue

            nodes.append(
                {
                    "id": topic["id"],
                    "type": "topic",
                    "label": topic["label"],
                    "description": topic["description"],
                    "color": topic["color"],
                    "count": int(len(topic_df)),
                    "lat": topic["lat"],
                    "lon": topic["lon"],
                    "clusterIds": topic["clusterIds"],
                }
            )

        return {
            "level": "topics",
            "total_cards": total_cards,
            "breadcrumb": [],
            "nodes": sorted(nodes, key=lambda n: n["count"], reverse=True),
            "flows": [],
            "cards": [],
        }

    if level == "clusters":
        nodes = []

        for cluster_id in sorted(df["cluster"].unique()):
            cluster_df = df[df["cluster"] == cluster_id]
            nodes.append(_eoe_cluster_node(cluster_id, cluster_df))

        return {
            "level": "clusters",
            "total_cards": total_cards,
            "breadcrumb": [],
            "nodes": sorted(nodes, key=lambda n: n["count"], reverse=True),
            "flows": [],
            "cards": [],
        }

    route_rows = []

    for _, row in df.iterrows():
        row_origin_iso = _eoe_get_iso(row, "origin")
        row_receiving_iso = _eoe_get_iso(row, "receiving")

        if origin_iso and row_origin_iso != origin_iso:
            continue

        if receiving_iso and row_receiving_iso != receiving_iso:
            continue

        origin_coords = _eoe_get_coords(row, "origin")
        receiving_coords = _eoe_get_coords(row, "receiving")

        if not origin_coords or not receiving_coords:
            continue

        route_rows.append(
            {
                "id": row.get("id", ""),
                "name": row.get("name", ""),
                "origin_country": row.get("origin_country", ""),
                "receiving_country": row.get("receiving_country", ""),
                "origin_city": row.get("origin_city", ""),
                "receiving_city": row.get("receiving_city", ""),
                "origin_iso": row_origin_iso,
                "receiving_iso": row_receiving_iso,
                "origin_lat": float(origin_coords[0]),
                "origin_lon": float(origin_coords[1]),
                "receiving_lat": float(receiving_coords[0]),
                "receiving_lon": float(receiving_coords[1]),
                "distance": _eoe_safe_float(row.get("distance", 0)),
                "time": _eoe_safe_float(row.get("time", 0)),
                "date_sent": row.get("date_sent", ""),
                "date_received": row.get("date_received", ""),
                "cluster": int(row.get("cluster", 0)),
                "cluster_name": row.get("cluster_name", ""),
                "cluster_color": row.get("cluster_color", "#64748b"),
                "topic_group_id": row.get("topic_group_id", ""),
                "topic_group_name": row.get("topic_group_name", ""),
                "topic_group_color": row.get("topic_group_color", "#64748b"),
                "image_url": row.get("image_url", ""),
            }
        )

    route_df = pd.DataFrame(route_rows)

    if level == "pairs":
        if route_df.empty:
            flows = pd.DataFrame()
        else:
            flows = (
                route_df.groupby(
                    [
                        "origin_country",
                        "receiving_country",
                        "origin_iso",
                        "receiving_iso",
                        "origin_lat",
                        "origin_lon",
                        "receiving_lat",
                        "receiving_lon",
                        "cluster",
                        "cluster_name",
                        "cluster_color",
                        "topic_group_id",
                        "topic_group_name",
                        "topic_group_color",
                    ],
                    dropna=False,
                )
                .agg(
                    route_count=("id", "count"),
                    avg_distance=("distance", "mean"),
                    avg_time=("time", "mean"),
                )
                .reset_index()
                .sort_values("route_count", ascending=False)
                .head(limit)
            )

            flows["id"] = flows.apply(
                lambda r: f"pair-{r['cluster']}-{r['origin_iso']}-{r['receiving_iso']}",
                axis=1,
            )

        return {
            "level": "pairs",
            "total_cards": total_cards,
            "breadcrumb": [],
            "nodes": [],
            "flows": _eoe_records(flows),
            "cards": [],
        }

    if level == "cards":
        cards = route_df.sort_values("time", ascending=False).head(limit) if not route_df.empty else pd.DataFrame()

        return {
            "level": "cards",
            "total_cards": int(len(route_df)),
            "breadcrumb": [],
            "nodes": [],
            "flows": [],
            "cards": _eoe_records(cards),
        }

    return {
        "level": level,
        "total_cards": total_cards,
        "breadcrumb": [],
        "nodes": [],
        "flows": [],
        "cards": [],
    }


@app.get("/outliers")
def get_outliers(
    origin_country: str | None = None,
    receiving_country: str | None = None,
    search: str | None = None,
    min_distance: float | None = None,
    max_distance: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    cluster: str | None = None,
    threshold: float = _EOE_Query(2.0, ge=0.5, le=5.0),
    limit: int = _EOE_Query(24, ge=1, le=200),
):
    df = apply_filters(
        load_cluster_data(),
        origin_country=origin_country,
        receiving_country=receiving_country,
        search=search,
        min_distance=min_distance,
        max_distance=max_distance,
        start_date=start_date,
        end_date=end_date,
        cluster=cluster,
    ).copy()

    total_filtered = len(df)

    if df.empty:
        return {
            "outliers": [],
            "count": 0,
            "total_filtered": int(total_filtered),
            "threshold": threshold,
        }

    df["time"] = pd.to_numeric(df["time"], errors="coerce")
    df["distance"] = pd.to_numeric(df["distance"], errors="coerce")
    df = df.dropna(subset=["time"]).copy()

    if df.empty:
        return {
            "outliers": [],
            "count": 0,
            "total_filtered": int(total_filtered),
            "threshold": threshold,
        }

    time_mean = df["time"].mean()
    time_std = df["time"].std()

    if pd.isna(time_std) or time_std == 0:
        time_std = 1

    distance_mean = df["distance"].mean()
    distance_std = df["distance"].std()

    if pd.isna(distance_std) or distance_std == 0:
        distance_std = 1

    df["time_z"] = (df["time"] - time_mean) / time_std
    df["distance_z"] = (df["distance"] - distance_mean) / distance_std
    df["outlier_score"] = df["time_z"]
    df["outlier_reason"] = df["time"].round().astype(int).astype(str) + " days: exceedingly long arrival time"

    outliers = df[df["time_z"] >= threshold].sort_values("time_z", ascending=False).head(limit)

    return {
        "outliers": _eoe_records(outliers),
        "count": int(len(outliers)),
        "total_filtered": int(total_filtered),
        "threshold": threshold,
    }


# === EOE CLEAN DRILLDOWN MAP END ===


# === EOE MAP DRILLDOWN ENDPOINT START ===
# Fix 1:
# Adds /map-drilldown endpoint required by the current App.tsx.
# Frontend expects:
# topics -> clusters -> pairs -> cards

from fastapi import Query as _EOE_Query

_EOE_TOPIC_HIERARCHY = [
    {
        "id": "nature",
        "label": "Nature & Landscape",
        "description": "Water, mountains, animals, flowers, sunsets, and natural views",
        "clusterIds": [1, 2, 6, 7, 9],
        "color": "#16a34a",
        "lat": 42.0,
        "lon": -28.0,
    },
    {
        "id": "architecture",
        "label": "Architecture & Places",
        "description": "Landmarks, cities, religious places, and Uzbekistan views",
        "clusterIds": [0, 4, 8],
        "color": "#2563eb",
        "lat": 44.0,
        "lon": 36.0,
    },
    {
        "id": "culture",
        "label": "Art & Culture",
        "description": "Paintings, illustrations, people, culture, and activities",
        "clusterIds": [5, 10],
        "color": "#db2777",
        "lat": 8.0,
        "lon": -12.0,
    },
    {
        "id": "graphic",
        "label": "Graphic / Maps / Mixed",
        "description": "Maps, flags, graphic cards, and mixed travel postcards",
        "clusterIds": [3, 11],
        "color": "#64748b",
        "lat": 6.0,
        "lon": 52.0,
    },
]

_EOE_CLUSTER_POSITIONS = {
    0: (52.0, 5.0),
    1: (48.0, -58.0),
    2: (32.0, -78.0),
    3: (-3.0, 68.0),
    4: (41.0, 42.0),
    5: (12.0, -42.0),
    6: (45.0, -92.0),
    7: (28.0, -25.0),
    8: (40.0, 68.0),
    9: (5.0, -70.0),
    10: (2.0, 8.0),
    11: (-18.0, 82.0),
}


def _eoe_remove_get_route(path_name):
    app.router.routes[:] = [
        route for route in app.router.routes
        if not (
            getattr(route, "path", None) == path_name
            and "GET" in getattr(route, "methods", set())
        )
    ]


def _eoe_safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return default
        value = float(value)
        if pd.isna(value):
            return default
        return value
    except Exception:
        return default


def _eoe_clean_records(df):
    if df is None or len(df) == 0:
        return []

    clean = df.copy()
    clean = clean.where(pd.notna(clean), None)
    records = clean.to_dict(orient="records")

    for row in records:
        for key, value in list(row.items()):
            if hasattr(value, "item"):
                try:
                    row[key] = value.item()
                except Exception:
                    pass

    return records


def _eoe_topic_for_cluster(cluster_id):
    cluster_id = int(_eoe_safe_float(cluster_id, 0))

    for topic in _EOE_TOPIC_HIERARCHY:
        if cluster_id in topic["clusterIds"]:
            return topic

    return {
        "id": "mixed",
        "label": "Mixed / Other",
        "description": "Other postcard topics",
        "clusterIds": [cluster_id],
        "color": "#334155",
        "lat": 0.0,
        "lon": 0.0,
    }


def _eoe_enrich_cluster_data():
    df = load_cluster_data().copy()

    if df.empty:
        return df

    if "cluster" not in df.columns:
        df["cluster"] = 0

    df["cluster"] = pd.to_numeric(df["cluster"], errors="coerce").fillna(0).astype(int)

    if "cluster_name" not in df.columns:
        df["cluster_name"] = df["cluster"].map(CLUSTER_NAMES).fillna("Unknown cluster")
    else:
        df["cluster_name"] = df["cluster_name"].replace("", pd.NA)
        df["cluster_name"] = df["cluster_name"].fillna(df["cluster"].map(CLUSTER_NAMES)).fillna("Unknown cluster")

    if "cluster_color" not in df.columns:
        df["cluster_color"] = df["cluster"].map(CLUSTER_COLORS).fillna("#64748b")
    else:
        df["cluster_color"] = df["cluster_color"].replace("", pd.NA)
        df["cluster_color"] = df["cluster_color"].fillna(df["cluster"].map(CLUSTER_COLORS)).fillna("#64748b")

    if "image_url" not in df.columns:
        df["image_url"] = "/images/" + df["name"].astype(str)

    topic_ids = []
    topic_names = []
    topic_colors = []

    for cluster_id in df["cluster"]:
        topic = _eoe_topic_for_cluster(cluster_id)
        topic_ids.append(topic["id"])
        topic_names.append(topic["label"])
        topic_colors.append(topic["color"])

    df["topic_group_id"] = topic_ids
    df["topic_group_name"] = topic_names
    df["topic_group_color"] = topic_colors

    return df


def _eoe_get_iso(row, side):
    return get_country_iso(
        row.get(f"{side}_country", ""),
        row.get(f"{side}_iso", ""),
    )


def _eoe_get_coords(row, side):
    iso = _eoe_get_iso(row, side)
    city = row.get(f"{side}_city", "")

    coords = get_best_coordinates(city, iso)
    if coords:
        return coords

    return get_country_capital_coordinates(iso)


def _eoe_cluster_node(cluster_id, cluster_df):
    cluster_id = int(cluster_id)
    lat, lon = _EOE_CLUSTER_POSITIONS.get(cluster_id, (0.0, 0.0))
    topic = _eoe_topic_for_cluster(cluster_id)

    sample_cols = [col for col in ["id", "name", "image_url"] if col in cluster_df.columns]
    samples = _eoe_clean_records(cluster_df.head(5)[sample_cols]) if sample_cols else []

    return {
        "id": f"cluster-{cluster_id}",
        "type": "cluster",
        "cluster": cluster_id,
        "label": CLUSTER_NAMES.get(cluster_id, f"Cluster {cluster_id}"),
        "color": CLUSTER_COLORS.get(cluster_id, "#64748b"),
        "topic_group_id": topic["id"],
        "topic_group_name": topic["label"],
        "count": int(len(cluster_df)),
        "lat": lat,
        "lon": lon,
        "samples": samples,
    }


_eoe_remove_get_route("/map-drilldown")


@app.get("/map-drilldown")
def get_map_drilldown(
    level: str = _EOE_Query("topics", pattern="^(topics|clusters|pairs|cards)$"),
    topic_id: str | None = None,
    cluster: int | None = None,
    origin_iso: str | None = None,
    receiving_iso: str | None = None,
    limit: int = _EOE_Query(80, ge=1, le=500),
    origin_country: str | None = None,
    receiving_country: str | None = None,
    search: str | None = None,
    min_distance: float | None = None,
    max_distance: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    df = _eoe_enrich_cluster_data()

    df = apply_filters(
        df,
        origin_country=origin_country,
        receiving_country=receiving_country,
        search=search,
        min_distance=min_distance,
        max_distance=max_distance,
        start_date=start_date,
        end_date=end_date,
    )

    if topic_id:
        topic = next((item for item in _EOE_TOPIC_HIERARCHY if item["id"] == topic_id), None)
        if topic:
            df = df[df["cluster"].isin(topic["clusterIds"])]

    if cluster is not None:
        df = df[df["cluster"] == int(cluster)]

    total_cards = int(len(df))

    if level == "topics":
        nodes = []

        for topic in _EOE_TOPIC_HIERARCHY:
            topic_df = df[df["cluster"].isin(topic["clusterIds"])]

            if topic_df.empty:
                continue

            nodes.append(
                {
                    "id": topic["id"],
                    "type": "topic",
                    "label": topic["label"],
                    "description": topic["description"],
                    "color": topic["color"],
                    "count": int(len(topic_df)),
                    "lat": topic["lat"],
                    "lon": topic["lon"],
                    "clusterIds": topic["clusterIds"],
                }
            )

        return {
            "level": "topics",
            "total_cards": total_cards,
            "breadcrumb": [],
            "nodes": sorted(nodes, key=lambda item: item["count"], reverse=True),
            "flows": [],
            "cards": [],
        }

    if level == "clusters":
        nodes = []

        for cluster_id in sorted(df["cluster"].unique()):
            cluster_df = df[df["cluster"] == cluster_id]
            nodes.append(_eoe_cluster_node(cluster_id, cluster_df))

        return {
            "level": "clusters",
            "total_cards": total_cards,
            "breadcrumb": [],
            "nodes": sorted(nodes, key=lambda item: item["count"], reverse=True),
            "flows": [],
            "cards": [],
        }

    route_rows = []

    for _, row in df.iterrows():
        row_origin_iso = _eoe_get_iso(row, "origin")
        row_receiving_iso = _eoe_get_iso(row, "receiving")

        if origin_iso and row_origin_iso != origin_iso:
            continue

        if receiving_iso and row_receiving_iso != receiving_iso:
            continue

        origin_coords = _eoe_get_coords(row, "origin")
        receiving_coords = _eoe_get_coords(row, "receiving")

        if not origin_coords or not receiving_coords:
            continue

        cluster_id = int(row.get("cluster", 0))

        route_rows.append(
            {
                "id": row.get("id", ""),
                "name": row.get("name", ""),
                "origin_country": row.get("origin_country", ""),
                "receiving_country": row.get("receiving_country", ""),
                "origin_city": row.get("origin_city", ""),
                "receiving_city": row.get("receiving_city", ""),
                "origin_iso": row_origin_iso,
                "receiving_iso": row_receiving_iso,
                "origin_lat": float(origin_coords[0]),
                "origin_lon": float(origin_coords[1]),
                "receiving_lat": float(receiving_coords[0]),
                "receiving_lon": float(receiving_coords[1]),
                "distance": _eoe_safe_float(row.get("distance", 0)),
                "time": _eoe_safe_float(row.get("time", 0)),
                "date_sent": row.get("date_sent", ""),
                "date_received": row.get("date_received", ""),
                "cluster": cluster_id,
                "cluster_name": CLUSTER_NAMES.get(cluster_id, "Unknown cluster"),
                "cluster_color": CLUSTER_COLORS.get(cluster_id, "#64748b"),
                "topic_group_id": row.get("topic_group_id", ""),
                "topic_group_name": row.get("topic_group_name", ""),
                "topic_group_color": row.get("topic_group_color", "#64748b"),
                "image_url": row.get("image_url", ""),
            }
        )

    route_df = pd.DataFrame(route_rows)

    if level == "pairs":
        if route_df.empty:
            flows = pd.DataFrame()
        else:
            flows = (
                route_df.groupby(
                    [
                        "origin_country",
                        "receiving_country",
                        "origin_iso",
                        "receiving_iso",
                        "origin_lat",
                        "origin_lon",
                        "receiving_lat",
                        "receiving_lon",
                        "cluster",
                        "cluster_name",
                        "cluster_color",
                        "topic_group_id",
                        "topic_group_name",
                        "topic_group_color",
                    ],
                    dropna=False,
                )
                .agg(
                    route_count=("id", "count"),
                    avg_distance=("distance", "mean"),
                    avg_time=("time", "mean"),
                )
                .reset_index()
                .sort_values("route_count", ascending=False)
                .head(limit)
            )

            flows["id"] = flows.apply(
                lambda row: f"pair-{row['cluster']}-{row['origin_iso']}-{row['receiving_iso']}",
                axis=1,
            )

        return {
            "level": "pairs",
            "total_cards": total_cards,
            "breadcrumb": [],
            "nodes": [],
            "flows": _eoe_clean_records(flows),
            "cards": [],
        }

    if level == "cards":
        cards = (
            route_df.sort_values("time", ascending=False).head(limit)
            if not route_df.empty
            else pd.DataFrame()
        )

        return {
            "level": "cards",
            "total_cards": int(len(route_df)),
            "breadcrumb": [],
            "nodes": [],
            "flows": [],
            "cards": _eoe_clean_records(cards),
        }

    return {
        "level": level,
        "total_cards": total_cards,
        "breadcrumb": [],
        "nodes": [],
        "flows": [],
        "cards": [],
    }


# === EOE MAP DRILLDOWN ENDPOINT END ===


# === EOE T1 T2 POSTCARDS FIX START ===
# Fixes:
# T1 / M1: /postcards now supports offset + limit pagination.
# T2 / E4: /postcards now accepts cluster as string, including comma-separated clusters:
# Example: cluster=1,2,6,7,9

from fastapi import Query as _EOE_POSTCARDS_Query


def _eoe_remove_get_route_by_path(path_name: str):
    app.router.routes[:] = [
        route
        for route in app.router.routes
        if not (
            getattr(route, "path", None) == path_name
            and "GET" in getattr(route, "methods", set())
        )
    ]


def _eoe_safe_records(df):
    if df is None or len(df) == 0:
        return []

    clean = df.copy()
    clean = clean.where(pd.notna(clean), None)

    records = clean.to_dict(orient="records")

    for record in records:
        for key, value in list(record.items()):
            if hasattr(value, "item"):
                try:
                    record[key] = value.item()
                except Exception:
                    pass

    return records


def _eoe_get_postcard_dataframe():
    df = load_cluster_data().copy()

    if "cluster" in df.columns:
        df["cluster"] = pd.to_numeric(df["cluster"], errors="coerce").fillna(0).astype(int)

    if "cluster_name" not in df.columns and "cluster" in df.columns:
        df["cluster_name"] = df["cluster"].map(CLUSTER_NAMES).fillna("Unknown cluster")

    if "cluster_color" not in df.columns and "cluster" in df.columns:
        df["cluster_color"] = df["cluster"].map(CLUSTER_COLORS).fillna("#64748b")

    if "image_url" not in df.columns and "name" in df.columns:
        df["image_url"] = "/images/" + df["name"].astype(str)

    return df


_eoe_remove_get_route_by_path("/postcards")


@app.get("/postcards")
def get_postcards(
    limit: int = _EOE_POSTCARDS_Query(36, ge=1, le=1000),
    offset: int = _EOE_POSTCARDS_Query(0, ge=0),
    origin_country: str | None = None,
    receiving_country: str | None = None,
    min_distance: float | None = None,
    max_distance: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
    cluster: str | None = None,
):
    df = _eoe_get_postcard_dataframe()

    df = apply_filters(
        df,
        origin_country=origin_country,
        receiving_country=receiving_country,
        min_distance=min_distance,
        max_distance=max_distance,
        start_date=start_date,
        end_date=end_date,
        search=search,
        cluster=cluster,
    )

    total_matches = int(len(df))

    page_df = df.iloc[offset: offset + limit]

    return {
        "total_matches": total_matches,
        "count": int(len(page_df)),
        "offset": int(offset),
        "limit": int(limit),
        "has_previous": offset > 0,
        "has_next": offset + limit < total_matches,
        "postcards": _eoe_safe_records(page_df),
    }


# === EOE T1 T2 POSTCARDS FIX END ===


# === EOE T3 LONG ARRIVAL OUTLIERS START ===
# Fixes E2:
# Outliers must be postcards with exceedingly long arrival time.
# This version uses only positive time_z, not distance anomalies and not short-time anomalies.

from fastapi import Query as _EOE_OUTLIERS_Query


def _eoe_remove_get_route_outliers(path_name: str):
    app.router.routes[:] = [
        route
        for route in app.router.routes
        if not (
            getattr(route, "path", None) == path_name
            and "GET" in getattr(route, "methods", set())
        )
    ]


def _eoe_outlier_records(df):
    if df is None or len(df) == 0:
        return []

    clean = df.copy()
    clean = clean.where(pd.notna(clean), None)
    records = clean.to_dict(orient="records")

    for record in records:
        for key, value in list(record.items()):
            if hasattr(value, "item"):
                try:
                    record[key] = value.item()
                except Exception:
                    pass

    return records


def _eoe_outlier_dataframe():
    # Use the fixed dataframe helper if T1/T2 patch already exists.
    if "_eoe_get_postcard_dataframe" in globals():
        return _eoe_get_postcard_dataframe().copy()

    df = load_cluster_data().copy()

    if "cluster" in df.columns:
        df["cluster"] = pd.to_numeric(df["cluster"], errors="coerce").fillna(0).astype(int)

    if "cluster_name" not in df.columns and "cluster" in df.columns:
        df["cluster_name"] = df["cluster"].map(CLUSTER_NAMES).fillna("Unknown cluster")

    if "cluster_color" not in df.columns and "cluster" in df.columns:
        df["cluster_color"] = df["cluster"].map(CLUSTER_COLORS).fillna("#64748b")

    if "image_url" not in df.columns and "name" in df.columns:
        df["image_url"] = "/images/" + df["name"].astype(str)

    return df


_eoe_remove_get_route_outliers("/outliers")


@app.get("/outliers")
def get_outliers(
    origin_country: str | None = None,
    receiving_country: str | None = None,
    search: str | None = None,
    min_distance: float | None = None,
    max_distance: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    cluster: str | None = None,
    threshold: float = _EOE_OUTLIERS_Query(2.0, ge=0.5, le=5.0),
    limit: int = _EOE_OUTLIERS_Query(24, ge=1, le=200),
):
    df = _eoe_outlier_dataframe()

    df = apply_filters(
        df,
        origin_country=origin_country,
        receiving_country=receiving_country,
        search=search,
        min_distance=min_distance,
        max_distance=max_distance,
        start_date=start_date,
        end_date=end_date,
        cluster=cluster,
    ).copy()

    total_filtered = int(len(df))

    if df.empty or "time" not in df.columns:
        return {
            "outliers": [],
            "count": 0,
            "total_filtered": total_filtered,
            "threshold": threshold,
        }

    df["time"] = pd.to_numeric(df["time"], errors="coerce")
    df["distance"] = pd.to_numeric(df.get("distance", 0), errors="coerce")
    df = df.dropna(subset=["time"]).copy()

    if df.empty:
        return {
            "outliers": [],
            "count": 0,
            "total_filtered": total_filtered,
            "threshold": threshold,
        }

    time_mean = df["time"].mean()
    time_std = df["time"].std()

    if pd.isna(time_std) or time_std == 0:
        time_std = 1

    distance_mean = df["distance"].mean()
    distance_std = df["distance"].std()

    if pd.isna(distance_std) or distance_std == 0:
        distance_std = 1

    df["time_z"] = (df["time"] - time_mean) / time_std
    df["distance_z"] = (df["distance"] - distance_mean) / distance_std

    # Important: only positive time_z means long arrival.
    df["outlier_score"] = df["time_z"]
    df["outlier_reason"] = (
        df["time"].round().astype(int).astype(str)
        + " days: exceedingly long arrival time"
    )

    outliers = (
        df[df["time_z"] >= threshold]
        .sort_values("time_z", ascending=False)
        .head(limit)
    )

    keep_columns = [
        "id",
        "name",
        "origin_country",
        "receiving_country",
        "origin_city",
        "receiving_city",
        "distance",
        "time",
        "date_sent",
        "date_received",
        "cluster",
        "cluster_name",
        "cluster_color",
        "image_url",
        "distance_z",
        "time_z",
        "outlier_score",
        "outlier_reason",
    ]

    existing_columns = [col for col in keep_columns if col in outliers.columns]

    return {
        "outliers": _eoe_outlier_records(outliers[existing_columns]),
        "count": int(len(outliers)),
        "total_filtered": total_filtered,
        "threshold": threshold,
    }


# === EOE T3 LONG ARRIVAL OUTLIERS END ===


# === EOE T4 SELECTED POSTCARD ROUTE START ===
# Adds exact route lookup for one selected postcard.
# Used by the frontend when the user clicks one postcard image.

def _eoe_remove_get_selected_route(path_name: str):
    app.router.routes[:] = [
        route
        for route in app.router.routes
        if not (
            getattr(route, "path", None) == path_name
            and "GET" in getattr(route, "methods", set())
        )
    ]


def _eoe_selected_route_float(value, default=0.0):
    try:
        if value in (None, ""):
            return default
        value = float(value)
        if pd.isna(value):
            return default
        return value
    except Exception:
        return default


def _eoe_selected_route_dataframe():
    if "_eoe_get_postcard_dataframe" in globals():
        return _eoe_get_postcard_dataframe().copy()

    if "_eoe_enrich_cluster_data" in globals():
        return _eoe_enrich_cluster_data().copy()

    return load_cluster_data().copy()


def _eoe_one_route_record(row):
    origin_iso = get_country_iso(
        row.get("origin_country", ""),
        row.get("origin_iso", ""),
    )

    receiving_iso = get_country_iso(
        row.get("receiving_country", ""),
        row.get("receiving_iso", ""),
    )

    origin_coordinates = get_best_coordinates(
        row.get("origin_city", ""),
        origin_iso,
    )

    if not origin_coordinates:
        origin_coordinates = get_country_capital_coordinates(origin_iso)

    receiving_coordinates = get_best_coordinates(
        row.get("receiving_city", ""),
        receiving_iso,
    )

    if not receiving_coordinates:
        receiving_coordinates = get_country_capital_coordinates(receiving_iso)

    if not origin_coordinates or not receiving_coordinates:
        return None

    cluster_id = int(_eoe_selected_route_float(row.get("cluster", 0), 0))

    return {
        "id": row.get("id", ""),
        "name": row.get("name", ""),
        "origin_country": row.get("origin_country", ""),
        "receiving_country": row.get("receiving_country", ""),
        "origin_city": row.get("origin_city", ""),
        "receiving_city": row.get("receiving_city", ""),
        "origin_iso": origin_iso,
        "receiving_iso": receiving_iso,
        "origin_lat": float(origin_coordinates[0]),
        "origin_lon": float(origin_coordinates[1]),
        "receiving_lat": float(receiving_coordinates[0]),
        "receiving_lon": float(receiving_coordinates[1]),
        "distance": _eoe_selected_route_float(row.get("distance", 0)),
        "time": _eoe_selected_route_float(row.get("time", 0)),
        "date_sent": row.get("date_sent", ""),
        "date_received": row.get("date_received", ""),
        "cluster": cluster_id,
        "cluster_name": row.get("cluster_name", CLUSTER_NAMES.get(cluster_id, "Unknown cluster")),
        "cluster_color": row.get("cluster_color", CLUSTER_COLORS.get(cluster_id, "#64748b")),
        "image_url": row.get("image_url", ""),
    }


_eoe_remove_get_selected_route("/postcard-route/{postcard_id}")


@app.get("/postcard-route/{postcard_id}")
def get_postcard_route(postcard_id: str):
    df = _eoe_selected_route_dataframe()

    if df.empty or "id" not in df.columns:
        return {
            "found": False,
            "route": None,
        }

    match = df[df["id"].astype(str) == str(postcard_id)]

    if match.empty:
        return {
            "found": False,
            "route": None,
        }

    route = _eoe_one_route_record(match.iloc[0])

    return {
        "found": route is not None,
        "route": route,
    }


# === EOE T4 SELECTED POSTCARD ROUTE END ===


# === EOE T8 DYNAMIC TOPIC HIERARCHY START ===
# E4 improvement:
# Generates topic hierarchy dynamically from currently filtered postcards.
# Frontend can use this instead of only hard-coded static topic groups.

def _eoe_remove_get_topic_hierarchy(path_name: str):
    app.router.routes[:] = [
        route
        for route in app.router.routes
        if not (
            getattr(route, "path", None) == path_name
            and "GET" in getattr(route, "methods", set())
        )
    ]


def _eoe_topic_hierarchy_source():
    if "_EOE_TOPIC_HIERARCHY" in globals():
        return _EOE_TOPIC_HIERARCHY

    return [
        {
            "id": "nature",
            "label": "Nature & Landscape",
            "description": "Water, mountains, animals, flowers, sunsets, and natural views",
            "clusterIds": [1, 2, 6, 7, 9],
            "color": "#16a34a",
            "x": 29,
            "y": 36,
        },
        {
            "id": "architecture",
            "label": "Architecture & Places",
            "description": "Landmarks, cities, religious places, and Uzbekistan views",
            "clusterIds": [0, 4, 8],
            "color": "#2563eb",
            "x": 70,
            "y": 34,
        },
        {
            "id": "culture",
            "label": "Art & Culture",
            "description": "Paintings, illustrations, people, culture, and activities",
            "clusterIds": [5, 10],
            "color": "#db2777",
            "x": 34,
            "y": 73,
        },
        {
            "id": "graphic",
            "label": "Graphic / Maps / Mixed",
            "description": "Maps, flags, graphic cards, and mixed travel postcards",
            "clusterIds": [3, 11],
            "color": "#64748b",
            "x": 76,
            "y": 71,
        },
    ]


def _eoe_topic_hierarchy_df():
    if "_eoe_enrich_cluster_data" in globals():
        return _eoe_enrich_cluster_data().copy()

    if "_eoe_get_postcard_dataframe" in globals():
        df = _eoe_get_postcard_dataframe().copy()
    else:
        df = load_cluster_data().copy()

    if "cluster" in df.columns:
        df["cluster"] = pd.to_numeric(df["cluster"], errors="coerce").fillna(0).astype(int)

    if "cluster_name" not in df.columns and "cluster" in df.columns:
        df["cluster_name"] = df["cluster"].map(CLUSTER_NAMES).fillna("Unknown cluster")

    if "cluster_color" not in df.columns and "cluster" in df.columns:
        df["cluster_color"] = df["cluster"].map(CLUSTER_COLORS).fillna("#64748b")

    if "image_url" not in df.columns and "name" in df.columns:
        df["image_url"] = "/images/" + df["name"].astype(str)

    return df


def _eoe_topic_records(df):
    if df is None or len(df) == 0:
        return []

    clean = df.copy()
    clean = clean.where(pd.notna(clean), None)
    records = clean.to_dict(orient="records")

    for record in records:
        for key, value in list(record.items()):
            if hasattr(value, "item"):
                try:
                    record[key] = value.item()
                except Exception:
                    pass

    return records


_eoe_remove_get_topic_hierarchy("/topic-hierarchy")


@app.get("/topic-hierarchy")
def get_topic_hierarchy(
    origin_country: str | None = None,
    receiving_country: str | None = None,
    search: str | None = None,
    min_distance: float | None = None,
    max_distance: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    df = _eoe_topic_hierarchy_df()

    df = apply_filters(
        df,
        origin_country=origin_country,
        receiving_country=receiving_country,
        search=search,
        min_distance=min_distance,
        max_distance=max_distance,
        start_date=start_date,
        end_date=end_date,
    ).copy()

    topics = []

    for topic in _eoe_topic_hierarchy_source():
        cluster_ids = topic.get("clusterIds", [])
        topic_df = df[df["cluster"].isin(cluster_ids)] if "cluster" in df.columns else df.iloc[0:0]

        clusters = []

        for cluster_id in cluster_ids:
            cluster_df = topic_df[topic_df["cluster"] == cluster_id]

            if cluster_df.empty:
                continue

            sample_cols = [
                col for col in ["id", "name", "image_url", "origin_country", "receiving_country"]
                if col in cluster_df.columns
            ]

            clusters.append(
                {
                    "cluster": int(cluster_id),
                    "cluster_name": CLUSTER_NAMES.get(int(cluster_id), f"Cluster {cluster_id}"),
                    "cluster_color": CLUSTER_COLORS.get(int(cluster_id), "#64748b"),
                    "count": int(len(cluster_df)),
                    "samples": _eoe_topic_records(cluster_df.head(4)[sample_cols]) if sample_cols else [],
                }
            )

        topics.append(
            {
                "id": topic["id"],
                "label": topic["label"],
                "description": topic.get("description", ""),
                "clusterIds": cluster_ids,
                "color": topic.get("color", "#64748b"),
                "x": topic.get("x", 50),
                "y": topic.get("y", 50),
                "count": int(len(topic_df)),
                "clusters": sorted(clusters, key=lambda item: item["count"], reverse=True),
            }
        )

    return {
        "total_matches": int(len(df)),
        "topics": sorted(topics, key=lambda item: item["count"], reverse=True),
    }


# === EOE T8 DYNAMIC TOPIC HIERARCHY END ===


# === T4 POSTCARDS PAGINATION FIX START ===
# Fixes:
# - /postcards now supports offset + limit.
# - /postcards now supports cluster as string, including "1,2,6,7,9".
# - Uses metadata + cluster CSV safely, so postcard list keeps country/date/distance fields.

from fastapi import Query as _T4_Query


def _t4_remove_get_route(path_name: str):
    app.router.routes[:] = [
        route
        for route in app.router.routes
        if not (
            getattr(route, "path", None) == path_name
            and "GET" in getattr(route, "methods", set())
        )
    ]


def _t4_safe_records(df):
    if df is None or len(df) == 0:
        return []

    clean = df.copy()
    clean = clean.where(pd.notna(clean), None)
    records = clean.to_dict(orient="records")

    for record in records:
        for key, value in list(record.items()):
            if hasattr(value, "item"):
                try:
                    record[key] = value.item()
                except Exception:
                    pass

    return records


def _t4_postcards_dataframe():
    """
    Build a safe full postcard dataframe.

    Why:
    - data/data.json has metadata.
    - postcards_image_clusters.csv may contain either full data or only id/name/cluster/x/y.
    - This helper merges them safely.
    """
    base = load_data().copy()

    try:
        clusters = pd.read_csv(CLUSTERS_PATH).fillna("")
    except Exception:
        clusters = pd.DataFrame()

    if not clusters.empty:
        merge_key = None

        if "id" in base.columns and "id" in clusters.columns:
            merge_key = "id"
        elif "name" in base.columns and "name" in clusters.columns:
            merge_key = "name"

        if merge_key:
            extra_cols = [
                col for col in clusters.columns
                if col == merge_key or col not in base.columns or col in ["cluster", "x", "y"]
            ]

            base = base.merge(
                clusters[extra_cols],
                on=merge_key,
                how="left",
                suffixes=("", "_cluster"),
            )

    if "cluster" not in base.columns:
        base["cluster"] = 0

    base["cluster"] = pd.to_numeric(base["cluster"], errors="coerce").fillna(0).astype(int)

    base["cluster_name"] = base["cluster"].map(CLUSTER_NAMES).fillna("Unknown cluster")
    base["cluster_color"] = base["cluster"].map(CLUSTER_COLORS).fillna("#64748b")

    if "image_url" not in base.columns and "name" in base.columns:
        base["image_url"] = "/images/" + base["name"].astype(str)

    return base


_t4_remove_get_route("/postcards")


@app.get("/postcards")
def get_postcards(
    limit: int = _T4_Query(36, ge=1, le=1000),
    offset: int = _T4_Query(0, ge=0),
    origin_country: str | None = None,
    receiving_country: str | None = None,
    min_distance: float | None = None,
    max_distance: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
    cluster: str | None = None,
):
    df = _t4_postcards_dataframe()

    df = apply_filters(
        df,
        origin_country=origin_country,
        receiving_country=receiving_country,
        min_distance=min_distance,
        max_distance=max_distance,
        start_date=start_date,
        end_date=end_date,
        search=search,
        cluster=cluster,
    ).copy()

    total_matches = int(len(df))
    page_df = df.iloc[offset: offset + limit]

    return {
        "total_matches": total_matches,
        "count": int(len(page_df)),
        "offset": int(offset),
        "limit": int(limit),
        "has_previous": offset > 0,
        "has_next": offset + limit < total_matches,
        "postcards": _t4_safe_records(page_df),
    }


# === T4 POSTCARDS PAGINATION FIX END ===


# === T10 MAP DRILLDOWN ENDPOINT START ===
# Adds the backend endpoint required by the React map:
# /map-drilldown?level=topics|clusters|pairs|cards

from fastapi import Query as _T10_Query


_T10_TOPICS = [
    {
        "id": "nature",
        "label": "Nature & Landscape",
        "description": "Water, mountains, animals, flowers, sunsets, and natural views",
        "clusterIds": [1, 2, 6, 7, 9],
        "color": "#16a34a",
        "lat": 28.0,
        "lon": -62.0,
    },
    {
        "id": "architecture",
        "label": "Architecture & Places",
        "description": "Landmarks, cities, religious places, and Uzbekistan views",
        "clusterIds": [0, 4, 8],
        "color": "#2563eb",
        "lat": 47.0,
        "lon": 18.0,
    },
    {
        "id": "culture",
        "label": "Art & Culture",
        "description": "Paintings, illustrations, people, culture, and activities",
        "clusterIds": [5, 10],
        "color": "#db2777",
        "lat": 12.0,
        "lon": 58.0,
    },
    {
        "id": "graphic",
        "label": "Graphic / Maps / Mixed",
        "description": "Maps, flags, graphic cards, and mixed travel postcards",
        "clusterIds": [3, 11],
        "color": "#64748b",
        "lat": -8.0,
        "lon": 112.0,
    },
]

_T10_TOPIC_BY_ID = {topic["id"]: topic for topic in _T10_TOPICS}

_T10_CLUSTER_OFFSETS = {
    0: (-4, -6),
    1: (3, -7),
    2: (-5, 1),
    3: (2, -5),
    4: (5, 4),
    5: (-4, -4),
    6: (7, 3),
    7: (-8, 7),
    8: (-7, 6),
    9: (5, 9),
    10: (6, 4),
    11: (-6, 7),
}


def _t10_remove_get_route(path_name: str):
    app.router.routes[:] = [
        route
        for route in app.router.routes
        if not (
            getattr(route, "path", None) == path_name
            and "GET" in getattr(route, "methods", set())
        )
    ]


def _t10_safe_float(value, default=0.0):
    try:
        if value is None:
            return default

        value = float(value)

        if pd.isna(value):
            return default

        return value
    except Exception:
        return default


def _t10_safe_int(value, default=0):
    try:
        if value is None or pd.isna(value):
            return default

        return int(float(value))
    except Exception:
        return default


def _t10_topic_for_cluster(cluster_id: int):
    for topic in _T10_TOPICS:
        if int(cluster_id) in topic["clusterIds"]:
            return topic

    return {
        "id": "unknown",
        "label": "Unknown topic",
        "description": "Unmapped visual cluster",
        "clusterIds": [],
        "color": "#64748b",
        "lat": 0.0,
        "lon": 0.0,
    }


def _t10_postcards_dataframe():
    if "_t4_postcards_dataframe" in globals():
        return _t4_postcards_dataframe()

    if "load_cluster_data" in globals():
        df = load_cluster_data().copy()
    else:
        df = load_data().copy()

    if "cluster" not in df.columns:
        df["cluster"] = 0

    df["cluster"] = pd.to_numeric(df["cluster"], errors="coerce").fillna(0).astype(int)
    df["cluster_name"] = df["cluster"].map(CLUSTER_NAMES).fillna("Unknown cluster")
    df["cluster_color"] = df["cluster"].map(CLUSTER_COLORS).fillna("#64748b")

    if "image_url" not in df.columns and "name" in df.columns:
        df["image_url"] = "/images/" + df["name"].astype(str)

    return df


def _t10_add_topic_columns(df):
    df = df.copy()

    topic_ids = []
    topic_names = []
    topic_colors = []

    for value in df.get("cluster", pd.Series([0] * len(df))):
        cluster_id = _t10_safe_int(value)
        topic = _t10_topic_for_cluster(cluster_id)
        topic_ids.append(topic["id"])
        topic_names.append(topic["label"])
        topic_colors.append(topic["color"])

    df["topic_group_id"] = topic_ids
    df["topic_group_name"] = topic_names
    df["topic_group_color"] = topic_colors

    return df


def _t10_cluster_list(topic_id: str | None = None):
    if topic_id and topic_id in _T10_TOPIC_BY_ID:
        return _T10_TOPIC_BY_ID[topic_id]["clusterIds"]

    all_clusters = []

    for topic in _T10_TOPICS:
        all_clusters.extend(topic["clusterIds"])

    return all_clusters


def _t10_sample_cards(df, cluster_id: int, limit: int = 4):
    subset = df[df["cluster"] == cluster_id].head(limit)

    samples = []

    for _, row in subset.iterrows():
        samples.append(
            {
                "id": str(row.get("id", "")),
                "name": str(row.get("name", "")),
                "image_url": str(row.get("image_url", "")),
            }
        )

    return samples


def _t10_topic_nodes(df):
    nodes = []

    for topic in _T10_TOPICS:
        cluster_ids = topic["clusterIds"]
        count = int(df[df["cluster"].isin(cluster_ids)].shape[0])

        nodes.append(
            {
                "id": topic["id"],
                "type": "topic",
                "label": topic["label"],
                "description": topic["description"],
                "color": topic["color"],
                "count": count,
                "lat": topic["lat"],
                "lon": topic["lon"],
                "clusterIds": cluster_ids,
            }
        )

    return nodes


def _t10_cluster_nodes(df, topic_id: str | None = None):
    nodes = []
    cluster_ids = _t10_cluster_list(topic_id)

    for cluster_id in cluster_ids:
        subset = df[df["cluster"] == cluster_id]

        if len(subset) == 0:
            continue

        topic = _t10_topic_for_cluster(cluster_id)
        offset_lat, offset_lon = _T10_CLUSTER_OFFSETS.get(cluster_id, (0, 0))

        nodes.append(
            {
                "id": f"cluster-{cluster_id}",
                "type": "cluster",
                "label": CLUSTER_NAMES.get(cluster_id, f"Cluster {cluster_id}"),
                "description": topic["label"],
                "color": CLUSTER_COLORS.get(cluster_id, topic["color"]),
                "count": int(len(subset)),
                "lat": float(topic["lat"] + offset_lat),
                "lon": float(topic["lon"] + offset_lon),
                "cluster": int(cluster_id),
                "topic_group_id": topic["id"],
                "topic_group_name": topic["label"],
                "samples": _t10_sample_cards(df, cluster_id, 4),
            }
        )

    return nodes


def _t10_route_from_row(row):
    origin_iso = get_country_iso(
        row.get("origin_country", ""),
        row.get("origin_iso", ""),
    )

    receiving_iso = get_country_iso(
        row.get("receiving_country", ""),
        row.get("receiving_iso", ""),
    )

    origin_coordinates = get_best_coordinates(
        row.get("origin_city", ""),
        origin_iso,
    )

    receiving_coordinates = get_best_coordinates(
        row.get("receiving_city", ""),
        receiving_iso,
    )

    if not origin_coordinates or not receiving_coordinates:
        return None

    origin_lat, origin_lon = origin_coordinates
    receiving_lat, receiving_lon = receiving_coordinates

    cluster_id = _t10_safe_int(row.get("cluster", 0))
    topic = _t10_topic_for_cluster(cluster_id)

    return {
        "id": str(row.get("id", "")),
        "name": str(row.get("name", "")),
        "origin_country": str(row.get("origin_country", "")),
        "receiving_country": str(row.get("receiving_country", "")),
        "origin_city": str(row.get("origin_city", "")),
        "receiving_city": str(row.get("receiving_city", "")),
        "origin_iso": origin_iso,
        "receiving_iso": receiving_iso,
        "origin_lat": float(origin_lat),
        "origin_lon": float(origin_lon),
        "receiving_lat": float(receiving_lat),
        "receiving_lon": float(receiving_lon),
        "distance": _t10_safe_float(row.get("distance", 0)),
        "time": _t10_safe_float(row.get("time", 0)),
        "date_sent": str(row.get("date_sent", "")),
        "date_received": str(row.get("date_received", "")),
        "cluster": int(cluster_id),
        "cluster_name": CLUSTER_NAMES.get(cluster_id, f"Cluster {cluster_id}"),
        "cluster_color": CLUSTER_COLORS.get(cluster_id, topic["color"]),
        "topic_group_id": topic["id"],
        "topic_group_name": topic["label"],
        "topic_group_color": topic["color"],
        "image_url": str(row.get("image_url", "")),
    }


def _t10_routes(df, limit: int | None = None):
    routes = []

    for _, row in df.iterrows():
        route = _t10_route_from_row(row)

        if route is None:
            continue

        routes.append(route)

        if limit is not None and len(routes) >= limit:
            break

    return routes


def _t10_pair_flows(df, limit: int = 80):
    routes = _t10_routes(df, None)

    if not routes:
        return []

    grouped = {}

    for route in routes:
        key = (
            route["origin_iso"],
            route["receiving_iso"],
            route["cluster"],
        )

        if key not in grouped:
            grouped[key] = {
                **route,
                "route_count": 0,
                "distance_total": 0.0,
                "time_total": 0.0,
            }

        grouped[key]["route_count"] += 1
        grouped[key]["distance_total"] += route["distance"]
        grouped[key]["time_total"] += route["time"]

    flows = []

    for key, value in grouped.items():
        count = max(1, value["route_count"])

        flows.append(
            {
                "id": f"{value['origin_iso']}-{value['receiving_iso']}-cluster-{value['cluster']}",
                "route_count": int(value["route_count"]),
                "avg_distance": float(value["distance_total"] / count),
                "avg_time": float(value["time_total"] / count),
                "origin_country": value["origin_country"],
                "receiving_country": value["receiving_country"],
                "origin_iso": value["origin_iso"],
                "receiving_iso": value["receiving_iso"],
                "origin_lat": value["origin_lat"],
                "origin_lon": value["origin_lon"],
                "receiving_lat": value["receiving_lat"],
                "receiving_lon": value["receiving_lon"],
                "cluster": value["cluster"],
                "cluster_name": value["cluster_name"],
                "cluster_color": value["cluster_color"],
                "topic_group_id": value["topic_group_id"],
                "topic_group_name": value["topic_group_name"],
                "topic_group_color": value["topic_group_color"],
            }
        )

    flows.sort(key=lambda item: item["route_count"], reverse=True)

    return flows[:limit]


def _t10_filter_by_pair_routes(routes, origin_iso: str | None, receiving_iso: str | None):
    if not origin_iso or not receiving_iso:
        return routes

    origin_iso = str(origin_iso).upper()
    receiving_iso = str(receiving_iso).upper()

    return [
        route
        for route in routes
        if route["origin_iso"].upper() == origin_iso
        and route["receiving_iso"].upper() == receiving_iso
    ]


def _t10_breadcrumb(level, topic_id=None, cluster=None, origin_iso=None, receiving_iso=None):
    crumbs = [{"level": "topics", "label": "Topics"}]

    if topic_id:
        topic = _T10_TOPIC_BY_ID.get(topic_id)
        crumbs.append({"level": "clusters", "label": topic["label"] if topic else "Topic"})

    if cluster is not None:
        cluster_id = _t10_safe_int(cluster)
        crumbs.append({"level": "pairs", "label": CLUSTER_NAMES.get(cluster_id, f"Cluster {cluster_id}")})

    if origin_iso and receiving_iso:
        crumbs.append({"level": "cards", "label": f"{origin_iso} → {receiving_iso}"})

    if level == "cards" and not origin_iso:
        crumbs.append({"level": "cards", "label": "Cards"})

    return crumbs


_t10_remove_get_route("/map-drilldown")


@app.get("/map-drilldown")
def get_map_drilldown(
    level: str = "topics",
    limit: int = _T10_Query(80, ge=1, le=500),
    origin_country: str | None = None,
    receiving_country: str | None = None,
    min_distance: float | None = None,
    max_distance: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
    topic_id: str | None = None,
    cluster: str | None = None,
    origin_iso: str | None = None,
    receiving_iso: str | None = None,
):
    level = level if level in {"topics", "clusters", "pairs", "cards"} else "topics"

    df = _t10_postcards_dataframe()

    df = apply_filters(
        df,
        origin_country=origin_country,
        receiving_country=receiving_country,
        min_distance=min_distance,
        max_distance=max_distance,
        start_date=start_date,
        end_date=end_date,
        search=search,
        cluster=cluster,
    ).copy()

    df = _t10_add_topic_columns(df)

    if topic_id and topic_id in _T10_TOPIC_BY_ID and not cluster:
        df = df[df["cluster"].isin(_T10_TOPIC_BY_ID[topic_id]["clusterIds"])]

    total_cards = int(len(df))

    if level == "topics":
        return {
            "level": "topics",
            "total_cards": total_cards,
            "breadcrumb": _t10_breadcrumb(level),
            "nodes": _t10_topic_nodes(df),
            "flows": [],
            "cards": [],
        }

    if level == "clusters":
        return {
            "level": "clusters",
            "total_cards": total_cards,
            "breadcrumb": _t10_breadcrumb(level, topic_id=topic_id),
            "nodes": _t10_cluster_nodes(df, topic_id=topic_id),
            "flows": [],
            "cards": [],
        }

    if level == "pairs":
        return {
            "level": "pairs",
            "total_cards": total_cards,
            "breadcrumb": _t10_breadcrumb(level, topic_id=topic_id, cluster=cluster),
            "nodes": [],
            "flows": _t10_pair_flows(df, limit),
            "cards": [],
        }

    routes = _t10_routes(df, None)
    routes = _t10_filter_by_pair_routes(routes, origin_iso, receiving_iso)
    routes = routes[:limit]

    return {
        "level": "cards",
        "total_cards": total_cards,
        "breadcrumb": _t10_breadcrumb(
            level,
            topic_id=topic_id,
            cluster=cluster,
            origin_iso=origin_iso,
            receiving_iso=receiving_iso,
        ),
        "nodes": [],
        "flows": [],
        "cards": routes,
    }


# === T10 MAP DRILLDOWN ENDPOINT END ===


# === T15 LONG ARRIVAL OUTLIERS START ===
# Fixes /outliers:
# - Only long arrival time is treated as an outlier.
# - Distance is kept as metadata, not used for outlier decision.
# - No "short time", no "short distance", no "long distance" outliers.

from fastapi import Query as _T15_Query


def _t15_remove_get_route(path_name: str):
    app.router.routes[:] = [
        route
        for route in app.router.routes
        if not (
            getattr(route, "path", None) == path_name
            and "GET" in getattr(route, "methods", set())
        )
    ]


def _t15_safe_float(value, default=0.0):
    try:
        if value is None:
            return default

        value = float(value)

        if pd.isna(value):
            return default

        return value
    except Exception:
        return default


def _t15_safe_int(value, default=0):
    try:
        if value is None or pd.isna(value):
            return default

        return int(float(value))
    except Exception:
        return default


def _t15_records(df):
    if df is None or len(df) == 0:
        return []

    clean = df.copy()
    clean = clean.where(pd.notna(clean), None)
    records = clean.to_dict(orient="records")

    for record in records:
        for key, value in list(record.items()):
            if hasattr(value, "item"):
                try:
                    record[key] = value.item()
                except Exception:
                    pass

    return records


def _t15_postcards_dataframe():
    if "_t10_postcards_dataframe" in globals():
        df = _t10_postcards_dataframe().copy()
    elif "_t4_postcards_dataframe" in globals():
        df = _t4_postcards_dataframe().copy()
    elif "load_cluster_data" in globals():
        df = load_cluster_data().copy()
    else:
        df = load_data().copy()

    if "cluster" not in df.columns:
        df["cluster"] = 0

    df["cluster"] = pd.to_numeric(df["cluster"], errors="coerce").fillna(0).astype(int)
    df["cluster_name"] = df["cluster"].map(CLUSTER_NAMES).fillna("Unknown cluster")
    df["cluster_color"] = df["cluster"].map(CLUSTER_COLORS).fillna("#64748b")

    if "image_url" not in df.columns and "name" in df.columns:
        df["image_url"] = "/images/" + df["name"].astype(str)

    if "_t10_topic_for_cluster" in globals():
        topic_ids = []
        topic_names = []
        topic_colors = []

        for cluster_value in df["cluster"]:
            topic = _t10_topic_for_cluster(_t15_safe_int(cluster_value))
            topic_ids.append(topic["id"])
            topic_names.append(topic["label"])
            topic_colors.append(topic["color"])

        df["topic_group_id"] = topic_ids
        df["topic_group_name"] = topic_names
        df["topic_group_color"] = topic_colors

    return df


_t15_remove_get_route("/outliers")


@app.get("/outliers")
def get_outliers(
    threshold: float = _T15_Query(2.0, ge=0.5, le=6.0),
    limit: int = _T15_Query(24, ge=1, le=200),
    origin_country: str | None = None,
    receiving_country: str | None = None,
    min_distance: float | None = None,
    max_distance: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
    cluster: str | None = None,
):
    df = _t15_postcards_dataframe()

    df = apply_filters(
        df,
        origin_country=origin_country,
        receiving_country=receiving_country,
        min_distance=min_distance,
        max_distance=max_distance,
        start_date=start_date,
        end_date=end_date,
        search=search,
        cluster=cluster,
    ).copy()

    if len(df) == 0 or "time" not in df.columns:
        return {
            "count": 0,
            "threshold": float(threshold),
            "logic": "long-arrival-only",
            "outliers": [],
        }

    df["time"] = pd.to_numeric(df["time"], errors="coerce")
    df["distance"] = pd.to_numeric(df.get("distance", 0), errors="coerce")

    time_mean = df["time"].mean()
    time_std = df["time"].std(ddof=0)

    if pd.isna(time_std) or time_std == 0:
        return {
            "count": 0,
            "threshold": float(threshold),
            "logic": "long-arrival-only",
            "outliers": [],
        }

    distance_mean = df["distance"].mean()
    distance_std = df["distance"].std(ddof=0)

    if pd.isna(distance_std) or distance_std == 0:
        distance_std = 1.0

    df["time_z"] = (df["time"] - time_mean) / time_std
    df["distance_z"] = (df["distance"] - distance_mean) / distance_std

    # Important: only positive high time_z is an outlier.
    outliers = df[df["time_z"] >= float(threshold)].copy()

    outliers["outlier_score"] = outliers["time_z"]
    outliers["outlier_reason"] = outliers["time"].round(0).astype(int).astype(str) + " days: unusually long arrival time"

    outliers = outliers.sort_values("outlier_score", ascending=False).head(limit)

    return {
        "count": int(len(outliers)),
        "threshold": float(threshold),
        "logic": "long-arrival-only",
        "outliers": _t15_records(outliers),
    }


# === T15 LONG ARRIVAL OUTLIERS END ===


# === T18 TOPIC HIERARCHY START ===
# Adds:
# - /topic-hierarchy dynamic backend endpoint.
# - robust apply_filters override that supports cluster="1,2,6,7,9".
# This is required for parent-topic filtering.

_T18_TOPICS = [
    {
        "id": "nature",
        "label": "Nature & Landscape",
        "description": "Water, mountains, animals, flowers, sunsets, and natural views",
        "clusterIds": [1, 2, 6, 7, 9],
        "color": "#16a34a",
        "x": 29,
        "y": 36,
    },
    {
        "id": "architecture",
        "label": "Architecture & Places",
        "description": "Landmarks, cities, religious places, and Uzbekistan views",
        "clusterIds": [0, 4, 8],
        "color": "#2563eb",
        "x": 70,
        "y": 34,
    },
    {
        "id": "culture",
        "label": "Art & Culture",
        "description": "Paintings, illustrations, people, culture, and activities",
        "clusterIds": [5, 10],
        "color": "#db2777",
        "x": 34,
        "y": 73,
    },
    {
        "id": "graphic",
        "label": "Graphic / Maps / Mixed",
        "description": "Maps, flags, graphic cards, and mixed travel postcards",
        "clusterIds": [3, 11],
        "color": "#64748b",
        "x": 76,
        "y": 71,
    },
]


def _t18_remove_get_route(path_name: str):
    app.router.routes[:] = [
        route
        for route in app.router.routes
        if not (
            getattr(route, "path", None) == path_name
            and "GET" in getattr(route, "methods", set())
        )
    ]


def _t18_norm(value):
    try:
        return normalize_text(value)
    except Exception:
        return str(value or "").strip().lower()


def _t18_parse_cluster_param(cluster):
    if cluster is None or str(cluster).strip() == "":
        return []

    output = []

    for part in str(cluster).split(","):
        part = part.strip()

        if not part:
            continue

        try:
            output.append(int(float(part)))
        except Exception:
            pass

    return sorted(set(output))


def _t18_topic_for_cluster(cluster_id: int):
    for topic in _T18_TOPICS:
        if int(cluster_id) in topic["clusterIds"]:
            return topic

    return {
        "id": "unknown",
        "label": "Unknown topic",
        "description": "Unmapped visual cluster",
        "clusterIds": [],
        "color": "#64748b",
        "x": 50,
        "y": 50,
    }


def _t18_postcards_dataframe():
    if "_t10_postcards_dataframe" in globals():
        df = _t10_postcards_dataframe().copy()
    elif "_t4_postcards_dataframe" in globals():
        df = _t4_postcards_dataframe().copy()
    elif "load_cluster_data" in globals():
        df = load_cluster_data().copy()
    else:
        df = load_data().copy()

    if "cluster" not in df.columns:
        df["cluster"] = 0

    df["cluster"] = pd.to_numeric(df["cluster"], errors="coerce").fillna(0).astype(int)
    df["cluster_name"] = df["cluster"].map(CLUSTER_NAMES).fillna("Unknown cluster")
    df["cluster_color"] = df["cluster"].map(CLUSTER_COLORS).fillna("#64748b")

    if "image_url" not in df.columns and "name" in df.columns:
        df["image_url"] = "/images/" + df["name"].astype(str)

    topic_ids = []
    topic_names = []
    topic_colors = []

    for value in df["cluster"]:
        topic = _t18_topic_for_cluster(int(value))
        topic_ids.append(topic["id"])
        topic_names.append(topic["label"])
        topic_colors.append(topic["color"])

    df["topic_group_id"] = topic_ids
    df["topic_group_name"] = topic_names
    df["topic_group_color"] = topic_colors

    return df


def apply_filters(
    df,
    origin_country=None,
    receiving_country=None,
    search=None,
    min_distance=None,
    max_distance=None,
    start_date=None,
    end_date=None,
    cluster=None,
):
    """
    Shared project filter.

    Supports:
    - normal filters
    - global search
    - cluster="9"
    - parent topic cluster list: cluster="1,2,6,7,9"
    """
    filtered = df.copy()

    if origin_country and "origin_country" in filtered.columns:
        filtered = filtered[
            filtered["origin_country"].astype(str).map(_t18_norm)
            == _t18_norm(origin_country)
        ]

    if receiving_country and "receiving_country" in filtered.columns:
        filtered = filtered[
            filtered["receiving_country"].astype(str).map(_t18_norm)
            == _t18_norm(receiving_country)
        ]

    if min_distance not in [None, ""] and "distance" in filtered.columns:
        filtered = filtered[pd.to_numeric(filtered["distance"], errors="coerce") >= float(min_distance)]

    if max_distance not in [None, ""] and "distance" in filtered.columns:
        filtered = filtered[pd.to_numeric(filtered["distance"], errors="coerce") <= float(max_distance)]

    if start_date not in [None, ""] and "date_sent" in filtered.columns:
        filtered = filtered[pd.to_datetime(filtered["date_sent"], errors="coerce") >= pd.to_datetime(start_date)]

    if end_date not in [None, ""] and "date_sent" in filtered.columns:
        filtered = filtered[pd.to_datetime(filtered["date_sent"], errors="coerce") <= pd.to_datetime(end_date)]

    cluster_ids = _t18_parse_cluster_param(cluster)

    if cluster_ids and "cluster" in filtered.columns:
        filtered = filtered[
            pd.to_numeric(filtered["cluster"], errors="coerce").fillna(-1).astype(int).isin(cluster_ids)
        ]

    if search:
        query = _t18_norm(search)

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
            "cluster_name",
            "topic_group_id",
            "topic_group_name",
        ]

        mask = pd.Series(False, index=filtered.index)

        for column in search_columns:
            if column in filtered.columns:
                mask |= filtered[column].astype(str).map(_t18_norm).str.contains(query, na=False)

        # useful semantic aliases for quick searches
        alias_clusters = {
            "nature": [1, 2, 6, 7, 9],
            "landscape": [1, 6, 7, 9],
            "mountain": [1, 6, 7],
            "animal": [2],
            "flower": [7],
            "beach": [9, 1],
            "water": [1, 9],
            "architecture": [0, 4, 8],
            "building": [0, 8],
            "city": [0, 8],
            "religion": [4],
            "art": [5, 10],
            "culture": [5, 10],
            "people": [10],
            "graphic": [3, 11],
            "map": [3, 11],
            "mixed": [3, 11],
        }

        for alias, ids in alias_clusters.items():
            if alias in query and "cluster" in filtered.columns:
                mask |= pd.to_numeric(filtered["cluster"], errors="coerce").fillna(-1).astype(int).isin(ids)

        filtered = filtered[mask]

    return filtered


def _t18_sample_cards(df, cluster_id: int, limit: int = 4):
    subset = df[df["cluster"] == cluster_id].head(limit)

    samples = []

    for _, row in subset.iterrows():
        samples.append(
            {
                "id": str(row.get("id", "")),
                "name": str(row.get("name", "")),
                "image_url": str(row.get("image_url", "")),
            }
        )

    return samples


_t18_remove_get_route("/topic-hierarchy")


@app.get("/topic-hierarchy")
def get_topic_hierarchy(
    origin_country: str | None = None,
    receiving_country: str | None = None,
    min_distance: float | None = None,
    max_distance: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
):
    df = _t18_postcards_dataframe()

    df = apply_filters(
        df,
        origin_country=origin_country,
        receiving_country=receiving_country,
        min_distance=min_distance,
        max_distance=max_distance,
        start_date=start_date,
        end_date=end_date,
        search=search,
    ).copy()

    topics = []

    for topic in _T18_TOPICS:
        topic_df = df[df["cluster"].isin(topic["clusterIds"])]

        clusters = []

        for cluster_id in topic["clusterIds"]:
            cluster_df = topic_df[topic_df["cluster"] == cluster_id]

            clusters.append(
                {
                    "cluster": int(cluster_id),
                    "cluster_name": CLUSTER_NAMES.get(cluster_id, f"Cluster {cluster_id}"),
                    "cluster_color": CLUSTER_COLORS.get(cluster_id, topic["color"]),
                    "count": int(len(cluster_df)),
                    "samples": _t18_sample_cards(df, cluster_id, 4),
                }
            )

        topics.append(
            {
                "id": topic["id"],
                "label": topic["label"],
                "description": topic["description"],
                "clusterIds": topic["clusterIds"],
                "color": topic["color"],
                "x": topic["x"],
                "y": topic["y"],
                "count": int(len(topic_df)),
                "clusters": clusters,
            }
        )

    return {
        "total_matches": int(len(df)),
        "topics": topics,
    }


# === T18 TOPIC HIERARCHY END ===


# === FINAL AUDITED TOPIC SYNC START ===
# Final sync between backend and frontend topic hierarchy.
# This overrides older experimental topic names such as "nature".

CLUSTER_NAMES = {
    0: "Mixed Light Travel & Nature Cards",
    1: "White Graphic, Stamps & Illustration Cards",
    2: "Dark Nature, Wildlife & Travel Views",
    3: "Warm Mixed Travel Postcards",
    4: "Architecture, Landmarks & Official Cards",
    5: "Blue Coasts, Islands & Seascapes",
    6: "Dark / Night Landscapes & Landmarks",
    7: "Pastel Illustrations, Animals & Flowers",
    8: "General Landscapes, Culture & Nature",
    9: "Travel Collages, Beaches & Mixed Views",
    10: "People, Culture & Dark Graphic Cards",
    11: "General Travel, Nature & Landmark Cards",
}

_PROJECT_TOPIC_GROUPS = [
    {
        "id": "blue_nature",
        "label": "Blue Nature & Wildlife",
        "description": "Water, sea, wildlife, coasts, landscapes, and broad nature postcards",
        "clusterIds": [2, 5, 6, 9, 11],
        "color": "#0ea5e9",
        "x": 29,
        "y": 36,
    },
    {
        "id": "architecture_landmarks",
        "label": "Architecture & Landmarks",
        "description": "Buildings, landmarks, cities, official places, and landscape/place views",
        "clusterIds": [4, 8],
        "color": "#2563eb",
        "x": 70,
        "y": 34,
    },
    {
        "id": "illustrations_culture",
        "label": "Illustrations & Culture",
        "description": "Graphic cards, stamps, illustrated cards, people, culture, and decorative subjects",
        "clusterIds": [1, 7, 10],
        "color": "#db2777",
        "x": 34,
        "y": 73,
    },
    {
        "id": "mixed_travel",
        "label": "Mixed Travel Views",
        "description": "Broad mixed travel postcards with light/warm visual style",
        "clusterIds": [0, 3],
        "color": "#f97316",
        "x": 76,
        "y": 71,
    },
]

TOPIC_HIERARCHY = _PROJECT_TOPIC_GROUPS
_T18_TOPICS = _PROJECT_TOPIC_GROUPS

if "_T10_TOPICS" in globals():
    _T10_TOPICS = _PROJECT_TOPIC_GROUPS

def _audited_topic_for_cluster(cluster_id: int):
    for topic in _PROJECT_TOPIC_GROUPS:
        if int(cluster_id) in topic["clusterIds"]:
            return topic
    return {
        "id": "unknown",
        "label": "Unknown topic",
        "description": "Unmapped visual cluster",
        "clusterIds": [],
        "color": "#64748b",
        "x": 50,
        "y": 50,
    }

_t18_topic_for_cluster = _audited_topic_for_cluster

if "_t10_topic_for_cluster" in globals():
    _t10_topic_for_cluster = _audited_topic_for_cluster

if "_t12_topic_for_cluster" in globals():
    _t12_topic_for_cluster = _audited_topic_for_cluster


def apply_filters(
    df,
    origin_country=None,
    receiving_country=None,
    search=None,
    min_distance=None,
    max_distance=None,
    start_date=None,
    end_date=None,
    cluster=None,
):
    filtered = df.copy()

    if origin_country and "origin_country" in filtered.columns:
        filtered = filtered[
            filtered["origin_country"].astype(str).map(_t18_norm)
            == _t18_norm(origin_country)
        ]

    if receiving_country and "receiving_country" in filtered.columns:
        filtered = filtered[
            filtered["receiving_country"].astype(str).map(_t18_norm)
            == _t18_norm(receiving_country)
        ]

    cluster_ids = _t18_parse_cluster_param(cluster)
    if cluster_ids and "cluster" in filtered.columns:
        filtered = filtered[
            pd.to_numeric(filtered["cluster"], errors="coerce")
            .fillna(-1)
            .astype(int)
            .isin(cluster_ids)
        ]

    if min_distance not in [None, ""] and "distance" in filtered.columns:
        filtered = filtered[
            pd.to_numeric(filtered["distance"], errors="coerce") >= float(min_distance)
        ]

    if max_distance not in [None, ""] and "distance" in filtered.columns:
        filtered = filtered[
            pd.to_numeric(filtered["distance"], errors="coerce") <= float(max_distance)
        ]

    if start_date not in [None, ""] and "date_sent" in filtered.columns:
        filtered = filtered[
            pd.to_datetime(filtered["date_sent"], errors="coerce") >= pd.to_datetime(start_date)
        ]

    if end_date not in [None, ""] and "date_sent" in filtered.columns:
        filtered = filtered[
            pd.to_datetime(filtered["date_sent"], errors="coerce") <= pd.to_datetime(end_date)
        ]

    if search:
        query = _t18_norm(search)

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
            "cluster_name",
            "topic_group_id",
            "topic_group_name",
        ]

        mask = pd.Series(False, index=filtered.index)

        for column in search_columns:
            if column in filtered.columns:
                mask |= filtered[column].astype(str).map(_t18_norm).str.contains(
                    query,
                    regex=False,
                    na=False,
                )

        alias_clusters = {
            "blue": [2, 5, 6, 9, 11],
            "nature": [2, 5, 6, 9, 11],
            "wildlife": [2, 11],
            "animal": [2, 7, 11],
            "sea": [5, 9],
            "beach": [5, 9],
            "water": [5, 9],
            "coast": [5, 9],
            "architecture": [4, 8],
            "landmark": [4, 8],
            "building": [4, 8],
            "city": [4, 8],
            "illustration": [1, 7, 10],
            "graphic": [1, 10],
            "stamp": [1],
            "culture": [7, 10],
            "people": [10],
            "mixed": [0, 3],
            "travel": [0, 3, 9, 11],
        }

        for alias, ids in alias_clusters.items():
            if alias in query and "cluster" in filtered.columns:
                mask |= (
                    pd.to_numeric(filtered["cluster"], errors="coerce")
                    .fillna(-1)
                    .astype(int)
                    .isin(ids)
                )

        filtered = filtered[mask]

    return filtered

# === FINAL AUDITED TOPIC SYNC END ===

# === FINAL MAP TOPIC LATLON FIX START ===
# T10 map drilldown requires lat/lon for every topic.
# The frontend uses x/y for semantic layout, but the map uses lat/lon.

_TOPIC_LATLON = {
    "blue_nature": (28.0, -20.0),
    "architecture_landmarks": (46.0, 42.0),
    "illustrations_culture": (12.0, 55.0),
    "mixed_travel": (-8.0, 12.0),
}

for _topic in _PROJECT_TOPIC_GROUPS:
    _lat, _lon = _TOPIC_LATLON.get(_topic["id"], (20.0, 0.0))
    _topic["lat"] = _lat
    _topic["lon"] = _lon

TOPIC_HIERARCHY = _PROJECT_TOPIC_GROUPS
_T18_TOPICS = _PROJECT_TOPIC_GROUPS

if "_T10_TOPICS" in globals():
    _T10_TOPICS = _PROJECT_TOPIC_GROUPS

if "_T10_TOPIC_BY_ID" in globals():
    _T10_TOPIC_BY_ID = {topic["id"]: topic for topic in _PROJECT_TOPIC_GROUPS}

# === FINAL MAP TOPIC LATLON FIX END ===

# === E5 JOURNEY ANIMATION START ===
# Elective E5:
# Animate postcard journeys over time.
# Backend returns time frames with active travelling postcard routes.

def _e5_period_start(value, period: str):
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None

    if period == "year":
        return pd.Timestamp(year=ts.year, month=1, day=1)

    return pd.Timestamp(year=ts.year, month=ts.month, day=1)


def _e5_period_end(start, period: str):
    if period == "year":
        return start + pd.offsets.YearEnd(0)
    return start + pd.offsets.MonthEnd(0)


def _e5_make_periods(min_date, max_date, period: str, max_frames: int):
    start = _e5_period_start(min_date, period)
    end = _e5_period_start(max_date, period)

    if start is None or end is None:
        return []

    freq = "YS" if period == "year" else "MS"
    periods = list(pd.date_range(start=start, end=end, freq=freq))

    if len(periods) > max_frames:
        periods = periods[-max_frames:]

    return periods


def _e5_topic_for_cluster(cluster_id: int):
    if "_audited_topic_for_cluster" in globals():
        return _audited_topic_for_cluster(cluster_id)
    if "_t18_topic_for_cluster" in globals():
        return _t18_topic_for_cluster(cluster_id)
    if "_t10_topic_for_cluster" in globals():
        return _t10_topic_for_cluster(cluster_id)

    return {
        "id": "unknown",
        "label": "Unknown topic",
        "color": "#64748b",
    }


def _e5_route_from_row(row, frame_start, frame_end):
    origin_iso = get_country_iso(
        row.get("origin_country", ""),
        row.get("origin_iso", ""),
    )
    receiving_iso = get_country_iso(
        row.get("receiving_country", ""),
        row.get("receiving_iso", ""),
    )

    origin_coordinates = get_best_coordinates(row.get("origin_city", ""), origin_iso)
    receiving_coordinates = get_best_coordinates(row.get("receiving_city", ""), receiving_iso)

    if not origin_coordinates or not receiving_coordinates:
        return None

    cluster_id = int(pd.to_numeric(row.get("cluster", 0), errors="coerce"))
    topic = _e5_topic_for_cluster(cluster_id)

    sent = pd.to_datetime(row.get("date_sent", ""), errors="coerce")
    received = pd.to_datetime(row.get("date_received", ""), errors="coerce")

    progress = 0.0
    if not pd.isna(sent) and not pd.isna(received) and received >= sent:
        frame_mid = frame_start + (frame_end - frame_start) / 2
        total_days = max((received - sent).days, 1)
        elapsed_days = (frame_mid - sent).days
        progress = max(0.0, min(1.0, elapsed_days / total_days))

    return {
        "id": str(row.get("id", "")),
        "name": str(row.get("name", "")),
        "origin_country": str(row.get("origin_country", "")),
        "receiving_country": str(row.get("receiving_country", "")),
        "origin_city": str(row.get("origin_city", "")),
        "receiving_city": str(row.get("receiving_city", "")),
        "origin_iso": origin_iso,
        "receiving_iso": receiving_iso,
        "origin_lat": float(origin_coordinates[0]),
        "origin_lon": float(origin_coordinates[1]),
        "receiving_lat": float(receiving_coordinates[0]),
        "receiving_lon": float(receiving_coordinates[1]),
        "date_sent": str(row.get("date_sent", "")),
        "date_received": str(row.get("date_received", "")),
        "progress": float(progress),
        "cluster": cluster_id,
        "cluster_name": CLUSTER_NAMES.get(cluster_id, f"Cluster {cluster_id}"),
        "cluster_color": CLUSTER_COLORS.get(cluster_id, "#64748b"),
        "topic_group_id": topic.get("id", "unknown"),
        "topic_group_name": topic.get("label", "Unknown topic"),
        "topic_group_color": topic.get("color", "#64748b"),
        "image_url": str(row.get("image_url", "")),
    }


@app.get("/journey-animation")
def get_journey_animation(
    period: str = Query("month", pattern="^(month|year)$"),
    max_frames: int = Query(72, ge=1, le=240),
    routes_per_frame: int = Query(120, ge=1, le=500),
    origin_country: str | None = None,
    receiving_country: str | None = None,
    min_distance: float | None = None,
    max_distance: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
    cluster: str | None = None,
):
    if "_t18_postcards_dataframe" in globals():
        df = _t18_postcards_dataframe()
    elif "_t10_postcards_dataframe" in globals():
        df = _t10_postcards_dataframe()
    elif "load_cluster_data" in globals():
        df = load_cluster_data()
    else:
        df = load_data()

    df = apply_filters(
        df,
        origin_country=origin_country,
        receiving_country=receiving_country,
        min_distance=min_distance,
        max_distance=max_distance,
        start_date=start_date,
        end_date=end_date,
        search=search,
        cluster=cluster,
    ).copy()

    if df.empty or "date_sent" not in df.columns or "date_received" not in df.columns:
        return {
            "period": period,
            "total_cards": 0,
            "frames": [],
        }

    df["date_sent_dt"] = pd.to_datetime(df["date_sent"], errors="coerce")
    df["date_received_dt"] = pd.to_datetime(df["date_received"], errors="coerce")
    df = df.dropna(subset=["date_sent_dt", "date_received_dt"])

    if df.empty:
        return {
            "period": period,
            "total_cards": 0,
            "frames": [],
        }

    periods = _e5_make_periods(
        df["date_sent_dt"].min(),
        df["date_received_dt"].max(),
        period,
        max_frames,
    )

    frames = []

    for frame_start in periods:
        frame_end = _e5_period_end(frame_start, period)

        active_mask = (
            (df["date_sent_dt"] <= frame_end)
            & (df["date_received_dt"] >= frame_start)
        )

        sent_mask = (
            (df["date_sent_dt"] >= frame_start)
            & (df["date_sent_dt"] <= frame_end)
        )

        received_mask = (
            (df["date_received_dt"] >= frame_start)
            & (df["date_received_dt"] <= frame_end)
        )

        active_df = df[active_mask].copy()
        active_df = active_df.sort_values("date_sent_dt", ascending=False)

        routes = []
        for _, row in active_df.head(routes_per_frame).iterrows():
            route = _e5_route_from_row(row, frame_start, frame_end)
            if route:
                routes.append(route)

        label = (
            str(frame_start.year)
            if period == "year"
            else f"{frame_start.year}-{frame_start.month:02d}"
        )

        frames.append(
            {
                "period": label,
                "start_date": frame_start.date().isoformat(),
                "end_date": frame_end.date().isoformat(),
                "active_count": int(active_mask.sum()),
                "sent_count": int(sent_mask.sum()),
                "received_count": int(received_mask.sum()),
                "shown_routes": int(len(routes)),
                "routes": routes,
            }
        )

    max_active = max([frame["active_count"] for frame in frames], default=0)

    return {
        "period": period,
        "total_cards": int(len(df)),
        "frame_count": int(len(frames)),
        "max_active": int(max_active),
        "routes_per_frame": int(routes_per_frame),
        "frames": frames,
    }

# === E5 JOURNEY ANIMATION END ===

# === FINAL NEUTRAL CLUSTER AUDIT PATCH START ===
# Final visual-audit naming:
# These labels are intentionally broad and neutral.
# The clusters are visual/exploratory groups, not perfect semantic ground truth.

CLUSTER_NAMES = {
    0: "Visual 0 — Mixed Travel, Art & Scenic Cards",
    1: "Visual 1 — Light Graphic Cards, Maps & Illustrations",
    2: "Visual 2 — Green Nature, Wildlife & Mixed Views",
    3: "Visual 3 — Warm Sunsets, Travel & Cultural Scenes",
    4: "Visual 4 — Architecture, Heritage & Monument Views",
    5: "Visual 5 — Blue Coasts, Islands & Landmark Views",
    6: "Visual 6 — Dark / Night Travel, Nature & Culture",
    7: "Visual 7 — Light Travel Sketches, Maps & Illustrated Cards",
    8: "Visual 8 — Mixed Scenic Travel, Culture & Nature",
    9: "Visual 9 — Landmarks, Culture & Scenic Views",
    10: "Visual 10 — High-Contrast Posters, Flags & Symbols",
    11: "Visual 11 — Green Landscapes, Coasts & Landmark Views",
}

_PROJECT_TOPIC_GROUPS = [
    {
        "id": "nature_scenic",
        "label": "Nature, Coasts & Scenic Views",
        "description": "Broad visual group for nature, coastal scenes, wildlife, landscapes, and mixed scenic postcards",
        "clusterIds": [2, 5, 8, 11],
        "color": "#0ea5e9",
        "x": 30,
        "y": 36,
        "lat": 22.0,
        "lon": -25.0,
    },
    {
        "id": "architecture_heritage",
        "label": "Architecture & Heritage Views",
        "description": "Broad visual group for buildings, monuments, historic places, religious landmarks, and city views",
        "clusterIds": [4, 9],
        "color": "#2563eb",
        "x": 70,
        "y": 34,
        "lat": 46.0,
        "lon": 42.0,
    },
    {
        "id": "graphics_illustrations",
        "label": "Graphics, Maps & Illustrations",
        "description": "Broad visual group for illustrated cards, maps, stamps, posters, symbols, and graphic designs",
        "clusterIds": [1, 7, 10],
        "color": "#db2777",
        "x": 35,
        "y": 73,
        "lat": 10.0,
        "lon": 55.0,
    },
    {
        "id": "mixed_travel_dark_warm",
        "label": "Mixed Travel, Warm & Dark Views",
        "description": "Broad visual group for mixed travel postcards, warm sunsets, dark/night scenes, and cultural views",
        "clusterIds": [0, 3, 6],
        "color": "#f97316",
        "x": 76,
        "y": 71,
        "lat": -8.0,
        "lon": 12.0,
    },
]

TOPIC_HIERARCHY = _PROJECT_TOPIC_GROUPS
_T18_TOPICS = _PROJECT_TOPIC_GROUPS

if "_T10_TOPICS" in globals():
    _T10_TOPICS = _PROJECT_TOPIC_GROUPS

if "_T10_TOPIC_BY_ID" in globals():
    _T10_TOPIC_BY_ID = {topic["id"]: topic for topic in _PROJECT_TOPIC_GROUPS}

def _audited_topic_for_cluster(cluster_id: int):
    for topic in _PROJECT_TOPIC_GROUPS:
        if int(cluster_id) in topic["clusterIds"]:
            return topic
    return {
        "id": "unknown",
        "label": "Unknown visual group",
        "description": "Unmapped visual cluster",
        "clusterIds": [],
        "color": "#64748b",
        "x": 50,
        "y": 50,
        "lat": 20.0,
        "lon": 0.0,
    }

_t18_topic_for_cluster = _audited_topic_for_cluster

if "_t10_topic_for_cluster" in globals():
    _t10_topic_for_cluster = _audited_topic_for_cluster

if "_t12_topic_for_cluster" in globals():
    _t12_topic_for_cluster = _audited_topic_for_cluster

def _neutral_norm(value):
    return str(value).strip().lower()

def _neutral_parse_cluster_param(cluster):
    if cluster in [None, ""]:
        return []

    ids = []
    for part in str(cluster).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(float(part)))
        except Exception:
            pass
    return ids

def apply_filters(
    df,
    origin_country=None,
    receiving_country=None,
    search=None,
    min_distance=None,
    max_distance=None,
    start_date=None,
    end_date=None,
    cluster=None,
):
    filtered = df.copy()

    if filtered.empty:
        return filtered

    if origin_country and "origin_country" in filtered.columns:
        filtered = filtered[
            filtered["origin_country"].astype(str).map(_neutral_norm)
            == _neutral_norm(origin_country)
        ]

    if receiving_country and "receiving_country" in filtered.columns:
        filtered = filtered[
            filtered["receiving_country"].astype(str).map(_neutral_norm)
            == _neutral_norm(receiving_country)
        ]

    cluster_ids = _neutral_parse_cluster_param(cluster)
    if cluster_ids and "cluster" in filtered.columns:
        filtered = filtered[
            pd.to_numeric(filtered["cluster"], errors="coerce")
            .fillna(-1)
            .astype(int)
            .isin(cluster_ids)
        ]

    if min_distance not in [None, ""] and "distance" in filtered.columns:
        filtered = filtered[
            pd.to_numeric(filtered["distance"], errors="coerce") >= float(min_distance)
        ]

    if max_distance not in [None, ""] and "distance" in filtered.columns:
        filtered = filtered[
            pd.to_numeric(filtered["distance"], errors="coerce") <= float(max_distance)
        ]

    if start_date not in [None, ""] and "date_sent" in filtered.columns:
        filtered = filtered[
            pd.to_datetime(filtered["date_sent"], errors="coerce") >= pd.to_datetime(start_date)
        ]

    if end_date not in [None, ""] and "date_sent" in filtered.columns:
        filtered = filtered[
            pd.to_datetime(filtered["date_sent"], errors="coerce") <= pd.to_datetime(end_date)
        ]

    if search:
        query = _neutral_norm(search)

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
            "cluster_name",
            "topic_group_id",
            "topic_group_name",
        ]

        mask = pd.Series(False, index=filtered.index)

        for column in search_columns:
            if column in filtered.columns:
                mask |= filtered[column].astype(str).map(_neutral_norm).str.contains(
                    query,
                    regex=False,
                    na=False,
                )

        alias_clusters = {
            "nature": [2, 5, 8, 11],
            "natural": [2, 5, 8, 11],
            "landscape": [2, 4, 8, 9, 11],
            "landscapes": [2, 4, 8, 9, 11],
            "mountain": [4, 8, 9, 11],
            "mountains": [4, 8, 9, 11],
            "forest": [2, 8, 11],
            "wildlife": [2, 8, 11],
            "animal": [2, 8, 11],
            "animals": [2, 8, 11],
            "sea": [5, 8, 11],
            "beach": [5, 8, 11],
            "coast": [5, 8, 11],
            "island": [5, 8, 11],
            "water": [5, 8, 11],
            "architecture": [4, 9],
            "building": [4, 9],
            "buildings": [4, 9],
            "landmark": [4, 9],
            "landmarks": [4, 9],
            "heritage": [4, 9],
            "city": [4, 9],
            "vatican": [4, 5, 9, 11],
            "uzbekistan": [4, 7, 8, 9],
            "graphic": [1, 7, 10],
            "graphics": [1, 7, 10],
            "illustration": [1, 7, 10],
            "illustrations": [1, 7, 10],
            "map": [1, 7, 10],
            "maps": [1, 7, 10],
            "stamp": [1, 7, 10],
            "poster": [10],
            "flag": [10],
            "symbol": [10],
            "culture": [3, 6, 8, 9],
            "people": [3, 6, 8, 9],
            "sunset": [3, 6, 10],
            "night": [6, 10],
            "dark": [6, 10],
            "travel": list(range(12)),
            "mixed": list(range(12)),
        }

        for alias, ids in alias_clusters.items():
            if alias in query and "cluster" in filtered.columns:
                mask |= (
                    pd.to_numeric(filtered["cluster"], errors="coerce")
                    .fillna(-1)
                    .astype(int)
                    .isin(ids)
                )

        filtered = filtered[mask]

    return filtered

# === FINAL NEUTRAL CLUSTER AUDIT PATCH END ===

# === E6 TOPIC EVOLUTION START ===
# Elective E6:
# Topic evolution over time.
# Returns topic/cluster counts per time period and optional country comparison.

def _e6_period_start(value, period: str):
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None

    if period == "year":
        return pd.Timestamp(year=ts.year, month=1, day=1)

    return pd.Timestamp(year=ts.year, month=ts.month, day=1)


def _e6_period_label(ts, period: str):
    if period == "year":
        return str(ts.year)
    return f"{ts.year}-{ts.month:02d}"


def _e6_get_dataframe():
    if "_t18_postcards_dataframe" in globals():
        df = _t18_postcards_dataframe()
    elif "load_cluster_data" in globals():
        df = load_cluster_data()
    else:
        df = load_data()

    df = df.copy()

    if "cluster" not in df.columns:
        df["cluster"] = 0

    df["cluster"] = pd.to_numeric(df["cluster"], errors="coerce").fillna(0).astype(int)

    if "cluster_name" not in df.columns:
        df["cluster_name"] = df["cluster"].map(CLUSTER_NAMES).fillna(
            df["cluster"].astype(str).map(lambda value: f"Cluster {value}")
        )

    topic_ids = []
    topic_names = []
    topic_colors = []

    for cluster_id in df["cluster"].tolist():
        topic = _audited_topic_for_cluster(int(cluster_id)) if "_audited_topic_for_cluster" in globals() else {
            "id": f"cluster_{cluster_id}",
            "label": f"Cluster {cluster_id}",
            "color": "#64748b",
        }

        topic_ids.append(topic.get("id", "unknown"))
        topic_names.append(topic.get("label", "Unknown topic"))
        topic_colors.append(topic.get("color", "#64748b"))

    df["topic_group_id"] = topic_ids
    df["topic_group_name"] = topic_names
    df["topic_group_color"] = topic_colors

    return df


@app.get("/topic-evolution")
def get_topic_evolution(
    period: str = Query("year", pattern="^(month|year)$"),
    abstraction: str = Query("topic", pattern="^(topic|cluster)$"),
    country_role: str = Query("receiving", pattern="^(origin|receiving)$"),
    country_a: str | None = None,
    country_b: str | None = None,
    origin_country: str | None = None,
    receiving_country: str | None = None,
    min_distance: float | None = None,
    max_distance: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
    cluster: str | None = None,
):
    df = _e6_get_dataframe()

    df = apply_filters(
        df,
        origin_country=origin_country,
        receiving_country=receiving_country,
        min_distance=min_distance,
        max_distance=max_distance,
        start_date=start_date,
        end_date=end_date,
        search=search,
        cluster=cluster,
    ).copy()

    if df.empty or "date_sent" not in df.columns:
        return {
            "period": period,
            "abstraction": abstraction,
            "country_role": country_role,
            "periods": [],
            "series": [],
            "total_cards": 0,
        }

    df["date_sent_dt"] = pd.to_datetime(df["date_sent"], errors="coerce")
    df = df.dropna(subset=["date_sent_dt"])

    if df.empty:
        return {
            "period": period,
            "abstraction": abstraction,
            "country_role": country_role,
            "periods": [],
            "series": [],
            "total_cards": 0,
        }

    df["period_start"] = df["date_sent_dt"].map(lambda value: _e6_period_start(value, period))
    df["period_label"] = df["period_start"].map(lambda value: _e6_period_label(value, period))

    if abstraction == "cluster":
        df["group_id"] = df["cluster"].map(lambda value: f"cluster_{int(value)}")
        df["group_label"] = df["cluster_name"]
        df["group_color"] = df["cluster"].map(CLUSTER_COLORS).fillna("#64748b")
    else:
        df["group_id"] = df["topic_group_id"]
        df["group_label"] = df["topic_group_name"]
        df["group_color"] = df["topic_group_color"]

    country_col = "origin_country" if country_role == "origin" else "receiving_country"

    periods = sorted(df["period_label"].dropna().unique().tolist())

    groups = (
        df[["group_id", "group_label", "group_color"]]
        .drop_duplicates()
        .sort_values("group_label")
        .to_dict(orient="records")
    )

    series = []

    for group in groups:
        group_df = df[df["group_id"] == group["group_id"]]

        values = []
        for label in periods:
            period_df = group_df[group_df["period_label"] == label]

            country_a_count = 0
            country_b_count = 0

            if country_a and country_col in period_df.columns:
                country_a_count = int(
                    (period_df[country_col].astype(str).str.lower() == str(country_a).lower()).sum()
                )

            if country_b and country_col in period_df.columns:
                country_b_count = int(
                    (period_df[country_col].astype(str).str.lower() == str(country_b).lower()).sum()
                )

            values.append(
                {
                    "period": label,
                    "count": int(len(period_df)),
                    "country_a_count": country_a_count,
                    "country_b_count": country_b_count,
                }
            )

        total = sum(item["count"] for item in values)

        if total > 0:
            series.append(
                {
                    "id": str(group["group_id"]),
                    "label": str(group["group_label"]),
                    "color": str(group["group_color"]),
                    "total": int(total),
                    "values": values,
                }
            )

    series = sorted(series, key=lambda item: item["total"], reverse=True)

    return {
        "period": period,
        "abstraction": abstraction,
        "country_role": country_role,
        "country_a": country_a or "",
        "country_b": country_b or "",
        "periods": periods,
        "series": series,
        "total_cards": int(len(df)),
    }

# === E6 TOPIC EVOLUTION END ===


# === EOE PRESENTATION VISUAL POLISH START ===
# Final presentation-ready labels.
# Short labels keep the topic space and map readable.

CLUSTER_NAMES = {
    0: "Mixed Travel",
    1: "Light Graphics",
    2: "Nature & Wildlife",
    3: "Warm Travel",
    4: "Heritage Views",
    5: "Coasts & Landmarks",
    6: "Night Travel",
    7: "Travel Sketches",
    8: "Scenic Culture",
    9: "Landmarks & Scenic",
    10: "Posters & Symbols",
    11: "Green Landscapes",
}

_PROJECT_TOPIC_GROUPS = [
    {
        "id": "nature_scenic",
        "label": "Nature & Scenic",
        "description": "Coasts, wildlife, landscapes, and scenic postcards",
        "clusterIds": [2, 5, 8, 11],
        "color": "#0ea5e9",
        "x": 30,
        "y": 36,
        "lat": 22,
        "lon": -25,
    },
    {
        "id": "architecture_heritage",
        "label": "Architecture",
        "description": "Buildings, monuments, heritage sites, and landmarks",
        "clusterIds": [4, 9],
        "color": "#2563eb",
        "x": 70,
        "y": 34,
        "lat": 46,
        "lon": 42,
    },
    {
        "id": "graphics_illustrations",
        "label": "Graphics & Maps",
        "description": "Illustrations, maps, posters, flags, and symbols",
        "clusterIds": [1, 7, 10],
        "color": "#db2777",
        "x": 35,
        "y": 73,
        "lat": 10,
        "lon": 55,
    },
    {
        "id": "mixed_travel_dark_warm",
        "label": "Mixed Travel",
        "description": "Warm scenes, night views, travel, and cultural postcards",
        "clusterIds": [0, 3, 6],
        "color": "#f97316",
        "x": 76,
        "y": 71,
        "lat": -8,
        "lon": 12,
    },
]

TOPIC_HIERARCHY = _PROJECT_TOPIC_GROUPS
_T18_TOPICS = _PROJECT_TOPIC_GROUPS
_T10_TOPICS = _PROJECT_TOPIC_GROUPS
_T10_TOPIC_BY_ID = {topic["id"]: topic for topic in _PROJECT_TOPIC_GROUPS}

def _audited_topic_for_cluster(cluster_id: int) -> dict:
    for topic in _PROJECT_TOPIC_GROUPS:
        if int(cluster_id) in topic["clusterIds"]:
            return topic
    return _PROJECT_TOPIC_GROUPS[-1]

def _t18_topic_for_cluster(cluster_id: int) -> dict:
    return _audited_topic_for_cluster(cluster_id)

def _t10_topic_for_cluster(cluster_id: int) -> dict:
    return _audited_topic_for_cluster(cluster_id)

def _t12_topic_for_cluster(cluster_id: int) -> dict:
    return _audited_topic_for_cluster(cluster_id)

# === EOE PRESENTATION VISUAL POLISH END ===

# === EOE E6 GLOBAL FILTER BRIDGE BACKEND START ===
# Allow Topic Evolution comparison countries to become global filters.
# The frontend sends comma-separated countries, e.g.:
#   receiving_country=Germany,Barbados
# This override keeps all old filters working and adds OR logic for countries.

_EOE_PRE_E6_APPLY_FILTERS = apply_filters

def _eoe_norm_country(value):
    if "_neutral_norm" in globals():
        return _neutral_norm(value)
    return str(value).strip().lower()

def _eoe_country_values(value):
    if value in [None, ""]:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_values = value
    else:
        raw_values = str(value).split(",")

    values = []
    for item in raw_values:
        cleaned = str(item).strip()
        if cleaned:
            values.append(_eoe_norm_country(cleaned))
    return list(dict.fromkeys(values))

def _eoe_apply_country_or_filter(df, column_name, value):
    if df.empty or column_name not in df.columns:
        return df

    values = _eoe_country_values(value)
    if not values:
        return df

    return df[df[column_name].astype(str).map(_eoe_norm_country).isin(values)]

def apply_filters(
    df,
    origin_country=None,
    receiving_country=None,
    search=None,
    min_distance=None,
    max_distance=None,
    start_date=None,
    end_date=None,
    cluster=None,
):
    # First apply all non-country filters using the previous project logic.
    filtered = _EOE_PRE_E6_APPLY_FILTERS(
        df,
        origin_country=None,
        receiving_country=None,
        search=search,
        min_distance=min_distance,
        max_distance=max_distance,
        start_date=start_date,
        end_date=end_date,
        cluster=cluster,
    )

    # Then apply country filters with support for comma-separated OR values.
    filtered = _eoe_apply_country_or_filter(filtered, "origin_country", origin_country)
    filtered = _eoe_apply_country_or_filter(filtered, "receiving_country", receiving_country)

    return filtered

# === EOE E6 GLOBAL FILTER BRIDGE BACKEND END ===
