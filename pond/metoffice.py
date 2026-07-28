# 2023 (C) Crown Copyright, Met Office. All rights reserved.
#
# This file is part of Weather DataHub and is released under the
# BSD 3-Clause license.
# See LICENSE in the root of the repository for full licensing details.
# (c) Met Office 2023

import requests
import argparse
import time
import sys
import logging as log
import os
import glob
import pandas as pd
import json
from datetime import datetime
import re

BASE_DIR = os.path.join(os.path.expanduser("~"), "projects", "pond")
LOG_DIR = os.path.join(BASE_DIR, "logs")


def resolve_path(path):
    if os.path.isabs(path):
        return path
    return os.path.join(BASE_DIR, path)


os.makedirs(LOG_DIR, exist_ok=True)

log.basicConfig(
    filename=os.path.join(LOG_DIR, "ss_download.log"),
    filemode='w',
    format='%(asctime)s - %(levelname)s - %(message)s'
)

base_url = "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/"

TIMESTEP_CODE_TO_API = {
    "1h": "hourly",
    "3h": "three-hourly",
    "1d": "daily",
}


def parse_timestep_codes(arg_value):
    """Parse a comma-separated list of timestep codes into ordered API timestep names."""
    raw_codes = [part.strip() for part in str(arg_value).split(",") if part.strip()]
    if not raw_codes:
        return None, "No timestep codes provided"

    invalid = [code for code in raw_codes if code not in TIMESTEP_CODE_TO_API]
    if invalid:
        return None, f"Invalid timestep codes: {', '.join(invalid)}"

    # Preserve user order while removing duplicates.
    selected = []
    for code in raw_codes:
        timestep = TIMESTEP_CODE_TO_API[code]
        if timestep not in selected:
            selected.append(timestep)
    return selected, None


def parse_snapshot_metadata_from_filename(file_path):
    """Parse snapshot datetime and suffix from filenames like pond-yymmdd-hhmm[-3h|-1d].json."""
    name = os.path.basename(file_path)
    match = re.match(r"^pond-(\d{6})-(\d{4})(?:-(3h|1d))?\.json$", name)
    if not match:
        return None
    snapshot_dt = pd.to_datetime(f"{match.group(1)}-{match.group(2)}", format="%y%m%d-%H%M", utc=True)
    snapshot_suffix = f"-{match.group(3)}" if match.group(3) else ""
    return snapshot_dt, snapshot_suffix


def parse_snapshot_datetime_from_filename(file_path):
    """Parse snapshot datetime from a forecast filename."""
    metadata = parse_snapshot_metadata_from_filename(file_path)
    if metadata is None:
        return None
    return metadata[0]


def dataframe_from_forecast_json(data):
    """Build a DataFrame indexed by time from forecast JSON."""
    props = data["features"][0]["properties"]
    ts = props.get("timeSeries")
    if ts is None:
        # Accept lowercase variant for robustness.
        ts = props.get("timeseries")
    if ts is None:
        raise KeyError("timeSeries")

    dfW = pd.DataFrame(ts)
    if "time" not in dfW.columns:
        raise KeyError("time")

    dfW["time"] = pd.to_datetime(dfW["time"], errors="coerce", utc=True)
    dfW = dfW.dropna(subset=["time"]).set_index("time").sort_index()
    return dfW


def load_merged_recent_data(nDays=7, file_suffix="", verbose=True):
    """Merge forecast data from the last nDays files, preferring newer snapshots.

    file_suffix controls which files are loaded:
    empty string means hourly files, "-3h" means three-hourly files, and "-1d" means daily files.
    """
    data_dir = resolve_path("metoffice-data")
    pattern = os.path.join(data_dir, "pond-*.json")
    files = glob.glob(pattern)

    if not files:
        print("ERROR: No JSON files found in ./metoffice-data/")
        return

    cutoff = pd.Timestamp.now("UTC") - pd.Timedelta(days=nDays)
    recent_files = []

    for file_path in files:
        metadata = parse_snapshot_metadata_from_filename(file_path)
        if metadata is None:
            continue
        file_dt, snapshot_suffix = metadata
        if snapshot_suffix != file_suffix:
            continue
        if file_dt >= cutoff:
            recent_files.append((file_dt, file_path))

    if not recent_files:
        print(f"ERROR: No forecast files found in last {nDays} days")
        return

    recent_files.sort(key=lambda item: item[0])

    frames = []
    for _, file_path in recent_files:
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            frames.append(dataframe_from_forecast_json(data))
        except Exception:
            log.warning("Skipping unreadable/invalid forecast file: %s", file_path, exc_info=True)

    if not frames:
        print("ERROR: No valid forecast dataframes could be loaded")
        return

    # Concatenate oldest -> newest then keep the last duplicate timestamp.
    # This means newer snapshots override older values for the same forecast time.
    dfW = pd.concat(frames)
    dfW = dfW[~dfW.index.duplicated(keep="last")].sort_index()

    if verbose:
        print(f"Merged {len(frames)} forecast files from the last {nDays} days")
        print(f"dfW shape: {dfW.shape}")
        print(dfW.head())
    return dfW

def load_latest_data():
    """Load the most recent pond-*.json file from ./metoffice-data/ and build dfW from timeseries."""
    data_dir = resolve_path("metoffice-data")
    pattern = os.path.join(data_dir, "pond-*.json")
    
    files = glob.glob(pattern)
    
    if not files:
        print("ERROR: No JSON files found in ./metoffice-data/")
        return
    
    latest_file = max(files, key=os.path.getctime)
    
    try:
        with open(latest_file, 'r') as f:
            data = json.load(f)
        print(f"Loaded: {latest_file}")
        dfW = dataframe_from_forecast_json(data)

        print(f"dfW shape: {dfW.shape}")
        print(dfW[["screenTemperature", "uvIndex"]])
        print(dfW.head())
        return dfW

    except Exception as e:
        log.error(f"Error loading file {latest_file}", exc_info=True)
        print(f"ERROR: Could not load {latest_file}")




def retrieve_forecast(baseUrl, timesteps, requestHeaders, latitude, longitude, excludeMetadata, includeLocation):
    
    url = baseUrl + timesteps 
    
    headers = {'accept': "application/json"}
    headers.update(requestHeaders)
    params = {
        'excludeParameterMetadata' : excludeMetadata,
        'includeLocationName' : includeLocation,
        'latitude' : latitude,
        'longitude' : longitude
        }

    success = False
    retries = 5

    while not success and retries >0:
        try:
            req = requests.get(url, headers=headers, params=params)
            success = True
        except Exception as e:
            log.warning("Exception occurred", exc_info=True)
            retries -= 1
            time.sleep(10)
            if retries == 0:
                log.error("Retries exceeded", exc_info=True)
                sys.exit()

    req.encoding = 'utf-8'
    req.raise_for_status()

    try:
        data = req.json()
    except ValueError:
        print("ERROR: Forecast response was not valid JSON")
        log.error("Forecast response was not valid JSON")
        return

    try:
        model_run_str = data["features"][0]["properties"]["modelRunDate"]
    except (KeyError, IndexError, TypeError):
        print("ERROR: Could not find modelRunDate at features/properties/modelRunDate")
        log.error("Missing modelRunDate in forecast response")
        return

    model_run_dt = pd.to_datetime(model_run_str, errors="coerce", utc=True)
    if pd.isna(model_run_dt):
        print(f"ERROR: Could not parse modelRunDate: {model_run_str}")
        log.error("Could not parse modelRunDate: %s", model_run_str)
        return

    out_dir = resolve_path("metoffice-data")
    os.makedirs(out_dir, exist_ok=True)
    timestep_suffix = ""
    if timesteps == "three-hourly":
        timestep_suffix = "-3h"
    elif timesteps == "daily":
        timestep_suffix = "-1d"

    out_name = f"pond-{model_run_dt.strftime('%y%m%d-%H%M')}{timestep_suffix}.json"
    out_path = os.path.join(out_dir, out_name)

    if os.path.exists(out_path):
        print(f"WARNING: Overwriting existing file: {out_path}")
        log.warning("Overwriting existing file: %s", out_path)

    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Saved forecast: {out_path}")




if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Retrieve the site-specific forecast for a single location"
    )
    parser.add_argument(
        "-t",
        "--timesteps",
        action="store",
        dest="timesteps",
        default="1h,3h",
        help="Comma-separated timestep codes to fetch. Supported values: 1h (hourly), 3h (three-hourly), 1d (daily). Default: 1h,3h",
    )
    parser.add_argument(
        "-m",
        "--metadata",
        action="store",
        dest="excludeMetadata",
        default="FALSE",
        help="Provide a boolean value for whether parameter metadata should be excluded."
    )
    parser.add_argument(
        "-n",
        "--name",
        action="store",
        dest="includeLocation",
        default="TRUE",
        help="Provide a boolean value for whether the location name should be included."
    )
    parser.add_argument(
        "-y",
        "--latitude",
        action="store",
        dest="latitude",
        default="51.56",
        help="Provide the latitude of the location you wish to retrieve the forecast for. Default: 51.56 (Highgate Men's Bathing Pond)."
    )
    parser.add_argument(
        "-x",
        "--longitude",
        action="store",
        dest="longitude",
        default="-0.178",
        help="Provide the longitude of the location you wish to retrieve the forecast for. Default: -0.178 (Highgate Men's Bathing Pond)."
    )
    parser.add_argument(
        "-k",
        "--key",
        "--apikey",
        action="store",
        dest="key",
        default="",
        help="WDH API key. Overrides --keyfile when provided."
    )
    parser.add_argument(
        "--keyfile",
        action="store",
        dest="keyfile",
        default="keys/met-office.txt",
        help="Path to a file containing the WDH API key. Relative paths are resolved from ~/projects/pond."
    )
    parser.add_argument(
        "--load",
        action="store_true",
        dest="load",
        help="Load and display the most recent pond data JSON file."
    )
    parser.add_argument(
        "--load-merged",
        action="store_true",
        dest="load_merged",
        help="Load and merge recent forecast JSON files. Newer snapshots override older values for the same forecast time."
    )
    parser.add_argument(
        "--days",
        action="store",
        dest="days",
        type=int,
        default=7,
        help="Number of recent days of forecast snapshots to include with --load-merged (default: 7)."
    )

    args = parser.parse_args()

    if args.load:
        load_latest_data()
        sys.exit()

    if args.load_merged:
        if args.days < 1:
            print("ERROR: --days must be >= 1")
            sys.exit()
        load_merged_recent_data(nDays=args.days)
        sys.exit()

    timesteps = args.timesteps
    includeLocation = args.includeLocation
    excludeMetadata = args.excludeMetadata
    latitude = args.latitude
    longitude = args.longitude
    key = args.key
    keyfile = args.keyfile

    # API key can be provided directly (--key) or loaded from --keyfile.
    if key.strip() == "":
        key_path = resolve_path(keyfile)
        try:
            with open(key_path, "r") as f:
                key = f.read().strip()
        except OSError:
            print(f"ERROR: Could not read key file: {key_path}")
            sys.exit()

    if key == "":
        print("ERROR: API credentials must be supplied via --key or --keyfile.")
        sys.exit()

    requestHeaders = {"apikey": key}

    if latitude == "" or longitude == "":
        print("ERROR: Latitude and longitude must be supplied")
        sys.exit()

    selected_timesteps, parse_error = parse_timestep_codes(timesteps)
    if parse_error is not None:
        print(f"ERROR: {parse_error}")
        print("ERROR: Use --timesteps with comma-separated codes: 1h,3h,1d")
        sys.exit() 

    if selected_timesteps is None:
        print("ERROR: Could not parse timestep codes")
        sys.exit()

    for timestep in selected_timesteps:
        retrieve_forecast(base_url, timestep, requestHeaders, latitude, longitude, excludeMetadata, includeLocation)



