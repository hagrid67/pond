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

        # Build dataframe from features[0].properties.timeseries and index by time.
        ts = data["features"][0]["properties"]["timeSeries"]
        dfW = pd.DataFrame(ts)
        if "time" not in dfW.columns:
            print("ERROR: timeseries does not contain a 'time' field")
            return

        dfW["time"] = pd.to_datetime(dfW["time"], errors="coerce")
        dfW = dfW.set_index("time").sort_index()

        print(f"dfW shape: {dfW.shape}")
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
    out_name = f"pond-{model_run_dt.strftime('%y%m%d-%H%M')}.json"
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
        default="hourly",
        help="The frequency of the timesteps provided in the forecast. The options are hourly, three-hourly or daily",
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

    args = parser.parse_args()

    if args.load:
        load_latest_data()
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

    if timesteps != "hourly" and timesteps != "three-hourly" and timesteps != "daily":
        print("ERROR: The available frequencies for timesteps are hourly, three-hourly or daily.")
        sys.exit() 
    
    retrieve_forecast(base_url, timesteps, requestHeaders, latitude, longitude, excludeMetadata, includeLocation)



