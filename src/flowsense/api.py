from functools import lru_cache

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .data import ROOT, intersection_meta
from .simulate import kpi_summary, run_comparison

app = FastAPI(title="FlowSense", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

WEB_DIR = ROOT / "web"


@lru_cache(maxsize=1)
def scored_frame() -> pd.DataFrame:
    return run_comparison()


@app.get("/api/health")
def health():
    return {"ok": True, "service": "flowsense"}


@app.get("/api/summary")
def summary():
    return kpi_summary(scored_frame())


@app.get("/api/intersections")
def intersections():
    df = scored_frame()
    meta = intersection_meta(df)
    agg = (
        df.groupby("intersection_id", as_index=False)
        .agg(
            baseline_delay=("baseline_delay_veh_h", "sum"),
            adaptive_delay=("adaptive_delay_veh_h", "sum"),
            baseline_queue=("baseline_queue_m", "mean"),
            adaptive_queue=("adaptive_queue_m", "mean"),
            vehicles=("vehicle_count_15min", "sum"),
        )
    )
    merged = meta.merge(agg, on="intersection_id")
    merged["delay_reduction_pct"] = 100.0 * (merged["baseline_delay"] - merged["adaptive_delay"]) / merged["baseline_delay"]
    return merged.round(3).to_dict(orient="records")


@app.get("/api/timeseries")
def timeseries(intersection_id: str = Query(default="all")):
    df = scored_frame()
    if intersection_id != "all":
        df = df[df["intersection_id"] == intersection_id]
    hourly = (
        df.set_index("timestamp_utc")
        .groupby(pd.Grouper(freq="1h"))
        .agg(
            baseline_delay=("baseline_delay_veh_h", "sum"),
            adaptive_delay=("adaptive_delay_veh_h", "sum"),
            baseline_queue=("baseline_queue_m", "mean"),
            adaptive_queue=("adaptive_queue_m", "mean"),
            vehicles=("vehicle_count_15min", "sum"),
            baseline_speed=("baseline_speed_kmh", "mean"),
            adaptive_speed=("adaptive_speed_kmh", "mean"),
        )
        .dropna(how="all")
        .reset_index()
    )
    hourly["timestamp_utc"] = hourly["timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return hourly.round(3).to_dict(orient="records")


@app.get("/api/sample")
def sample(limit: int = 24):
    cols = [
        "timestamp_utc",
        "intersection_id",
        "approach",
        "vehicle_count_15min",
        "queue_length_m",
        "signal_phase_sec_green",
        "adaptive_green_sec",
        "baseline_delay_veh_h",
        "adaptive_delay_veh_h",
        "weather",
        "is_rush_hour",
    ]
    frame = scored_frame()[cols].head(limit).copy()
    frame["timestamp_utc"] = frame["timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return frame.round(3).to_dict(orient="records")


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
