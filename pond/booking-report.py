from __future__ import annotations

import argparse
import csv
import html as html_lib
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Callable, cast

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
ARCHIVE_GLOB = "bookings-*.csv"
HISTORICAL_DAYS = 6
BOOKING_LEAD_DAYS = 7
LIDO_SLOT_TIMES = {"10:30-13:30", "14:30-17:30", "18:00-20:00"}
POND_ELEVATION_M = 70.0
LAPSE_RATE_C_PER_KM = 6.5

# Met Office significant weather code mapping (day/night variants use shared short labels).
SIGNIFICANT_WEATHER_LABELS: dict[int, str] = {
	0: "clear",
	1: "sunny",
	2: "partly cloudy",
	3: "partly cloudy",
	5: "mist",
	6: "fog",
	7: "cloudy",
	8: "overcast",
	9: "light rain shower",
	10: "light rain shower",
	11: "drizzle",
	12: "light rain",
	13: "heavy rain shower",
	14: "heavy rain shower",
	15: "heavy rain",
	16: "sleet shower",
	17: "sleet shower",
	18: "sleet",
	19: "hail shower",
	20: "hail shower",
	21: "hail",
	22: "light snow shower",
	23: "light snow shower",
	24: "light snow",
	25: "heavy snow shower",
	26: "heavy snow shower",
	27: "heavy snow",
	28: "thunder shower",
	29: "thunder shower",
	30: "thunder",
}

SIGNIFICANT_WEATHER_ICONS: dict[int, str] = {
	0: "🌙",
	1: "☀️",
	2: "⛅",
	3: "⛅",
	5: "🌫",
	6: "🌫",
	7: "☁",
	8: "☁",
	9: "🌦",
	10: "🌦",
	11: "🌦",
	12: "🌧",
	13: "🌧",
	14: "🌧",
	15: "🌧",
	16: "🌨",
	17: "🌨",
	18: "🌨",
	19: "🌨",
	20: "🌨",
	21: "🌨",
	22: "🌨",
	23: "🌨",
	24: "🌨",
	25: "❄",
	26: "❄",
	27: "❄",
	28: "⛈",
	29: "⛈",
	30: "🌩",
}


def describe_significant_weather(code_value: object) -> str:
	"""Decode Met Office significantWeatherCode into a short lowercase label."""
	code = parse_significant_weather_code(code_value)
	if code is None:
		return "unknown"
	return SIGNIFICANT_WEATHER_LABELS.get(code, "unknown")


def parse_significant_weather_code(code_value: object) -> int | None:
	"""Parse significantWeatherCode to int when possible."""
	if code_value is None:
		return None
	if isinstance(code_value, float) and np.isnan(code_value):
		return None
	try:
		numeric = pd.to_numeric(pd.Series([code_value]), errors="coerce").iloc[0]
		if pd.isna(numeric):
			return None
		return int(round(float(numeric)))
	except (TypeError, ValueError):
		return None


def significant_weather_icon(code_value: object) -> str:
	"""Return a compact weather icon for significantWeatherCode."""
	code = parse_significant_weather_code(code_value)
	if code is None:
		return ""
	return SIGNIFICANT_WEATHER_ICONS.get(code, "")


def availability_to_count(availability_value):
	"""Convert availability text/value into an integer ticket count."""
	if availability_value is None:
		return 0
	if isinstance(availability_value, (int, float)):
		return max(int(availability_value), 0)

	text = str(availability_value).strip()
	if not text:
		return 0
	if text.lower() == "fully booked":
		return 0

	try:
		return max(int(text), 0)
	except ValueError:
		return 0


def availability_to_display(availability_value):
	"""Convert availability into a plain numeric string for HTML display."""
	text = "" if availability_value is None else str(availability_value).strip()
	if text.isdigit():
		return text
	return str(availability_to_count(availability_value))


def resolve_output_path(output_dir: str, file_arg: str) -> str:
	"""Resolve output path.
	Bare filenames are placed under output_dir.
	Explicit paths (with directory component) are used as-is.
	"""
	if os.path.dirname(file_arg):
		return file_arg
	return os.path.join(output_dir, file_arg)


def _timestep_label_from_suffix(snapshot_suffix: str) -> str:
	if snapshot_suffix == "":
		return "hourly"
	if snapshot_suffix == "-3h":
		return "three-hourly"
	if snapshot_suffix == "-1d":
		return "daily"
	return snapshot_suffix.lstrip("-") or "unknown"


def collect_weather_source_runs(n_days: int = 7) -> list[dict[str, object]]:
	"""Collect grouped weather model runs used to build the report."""
	data_dir = REPO_ROOT / "metoffice-data"
	cutoff = pd.Timestamp.now("UTC") - pd.Timedelta(days=n_days)
	runs_by_time: dict[str, dict[str, object]] = {}
	from pond.metoffice import parse_snapshot_metadata_from_filename

	try:
		from pond.metoffice import parse_snapshot_metadata_from_filename
	except Exception:
		return []

	for file_path in sorted(data_dir.glob("pond-*.json")):
		metadata = parse_snapshot_metadata_from_filename(str(file_path))
		if metadata is None:
			continue
		snapshot_time, snapshot_suffix = metadata
		if snapshot_time < cutoff:
			continue

		model_run_at = snapshot_time.isoformat()
		run = runs_by_time.get(model_run_at)
		if run is None:
			run = {"modelRunAt": model_run_at, "sources": []}
			runs_by_time[model_run_at] = run

		sources = cast(list[dict[str, str]], run["sources"])
		sources.append(
			{
				"file": file_path.name,
				"timestep": _timestep_label_from_suffix(snapshot_suffix),
			}
		)

	return sorted(runs_by_time.values(), key=lambda item: str(item.get("modelRunAt") or ""))


def build_report_metadata(
	selected_csv: Path,
	report_slots: list[dict[str, str | int]],
	date_sequence: list[str],
	report_generated_at: datetime,
	n_days: int = 7,
) -> dict[str, object]:
	"""Build a compact metadata manifest for the browser controls."""
	bookings_snapshot_at = infer_snapshot_time(selected_csv)
	all_times: list[str] = []
	all_times_seen: set[str] = set()
	time_slot_groups: dict[str, str] = {}
	days: list[dict[str, object]] = []
	reference_date = bookings_snapshot_at.date()

	for day in date_sequence:
		parsed_day = parse_booking_date(day)
		day_group = day_group_for_date(parsed_day, reference_date)

		day_slots: list[dict[str, str]] = []
		seen_day_times: set[str] = set()
		for slot in sorted((slot for slot in report_slots if slot["date"] == day), key=lambda slot: str(slot["time"])):
			time_text = str(slot["time"])
			if time_text in seen_day_times:
				continue
			seen_day_times.add(time_text)
			slot_group = slot_group_for_time(time_text)
			day_slots.append({"time": time_text, "slotGroup": slot_group})
			if time_text not in time_slot_groups:
				time_slot_groups[time_text] = slot_group
			if time_text not in all_times_seen:
				all_times_seen.add(time_text)
				all_times.append(time_text)

		days.append(
			{
				"date": day,
				"dayGroup": day_group,
				"slots": day_slots,
			}
		)

	weather_sources = collect_weather_source_runs(n_days=n_days)
	weather_forecast_at = weather_sources[-1]["modelRunAt"] if weather_sources else None

	return {
		"schemaVersion": 1,
		"reportGeneratedAt": report_generated_at.astimezone(ZoneInfo("UTC")).isoformat(),
		"bookingsSnapshotAt": bookings_snapshot_at.astimezone(ZoneInfo("UTC")).isoformat(),
		"weatherForecastAt": weather_forecast_at,
		"weatherSources": weather_sources,
		"reportDateRange": {
			"start": date_sequence[0] if date_sequence else None,
			"end": date_sequence[-1] if date_sequence else None,
		},
		"venues": [{"id": idx, "label": venue} for idx, venue in enumerate(["Men's", "Ladies", "Mixed", "Lido"])],
		"slotGroups": [
			{"id": "pond", "label": "Pond slots"},
			{"id": "lido", "label": "Lido slots"},
		],
		"allTimes": all_times,
		"timeSlotGroups": time_slot_groups,
		"days": days,
	}


def parse_archive_timestamp(path: Path) -> datetime:
	stamp = path.stem.removeprefix("bookings-")
	return datetime.strptime(stamp, "%Y-%m%d-%H%M")


def find_latest_bookings_csv(data_dir: Path) -> Path:
	matches = sorted(data_dir.glob(ARCHIVE_GLOB))
	if not matches:
		raise FileNotFoundError(f"No archived bookings CSV files matched {data_dir / ARCHIVE_GLOB}")
	return max(matches, key=parse_archive_timestamp)


def infer_snapshot_time(path: Path) -> datetime:
	if path.name.startswith("bookings-") and path.suffix == ".csv":
		return parse_archive_timestamp(path)
	return datetime.fromtimestamp(path.stat().st_mtime)


def parse_slot_start(date_text: str, time_text: str) -> datetime:
	return datetime.strptime(f"{date_text} {time_text.split('-', 1)[0]}", "%Y-%m%d %H:%M")


def is_fully_historical_slot(date_text: str, time_text: str, reference_time: datetime | None) -> bool:
	if reference_time is None:
		return False
	parsed_date = parse_booking_date(date_text)
	if parsed_date is None or "-" not in time_text:
		return False
	try:
		slot_end = datetime.combine(parsed_date, datetime.strptime(time_text.split("-", 1)[1], "%H:%M").time())
	except ValueError:
		return False
	return slot_end <= reference_time


def make_debug_logger(enabled: bool, file_path: str | None = None) -> Callable[[str], None]:
	"""Create a debug logger used for weather diagnostics."""
	if not enabled:
		return lambda _msg: None

	def _log(message: str) -> None:
		stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		line = f"[{stamp}] [weather-debug] {message}"
		print(line)
		if file_path:
			try:
				os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
				with open(file_path, "a", encoding="utf-8") as fh:
					fh.write(line + "\n")
			except OSError:
				# Keep debug logging non-fatal.
				pass

	return _log


def _load_recent_weather_snapshots(
	n_days: int,
	file_suffix: str,
	debug_log: Callable[[str], None] | None = None,
) -> list[pd.DataFrame]:
	if debug_log is None:
		debug_log = lambda _msg: None

	try:
		from pond.metoffice import dataframe_from_forecast_json, parse_snapshot_metadata_from_filename
		debug_log("Imported pond.metoffice dataframe helpers")
	except Exception as exc:
		debug_log(f"Failed to import pond.metoffice dataframe helpers: {exc!r}")
		return []

	data_dir = REPO_ROOT / "metoffice-data"
	cutoff = pd.Timestamp.now("UTC") - pd.Timedelta(days=n_days)
	snapshot_frames: list[pd.DataFrame] = []

	for file_path in sorted(data_dir.glob("pond-*.json")):
		metadata = parse_snapshot_metadata_from_filename(str(file_path))
		if metadata is None:
			continue
		snapshot_time, snapshot_suffix = metadata
		if snapshot_suffix != file_suffix or snapshot_time < cutoff:
			continue

		try:
			with open(file_path, "r", encoding="utf-8") as fh:
				data = json.load(fh)
			raw_frame = dataframe_from_forecast_json(data).sort_index()
			coords = data.get("features", [{}])[0].get("geometry", {}).get("coordinates", [])
			model_elevation_m = float(coords[2]) if isinstance(coords, list) and len(coords) >= 3 else np.nan
		except Exception as exc:
			debug_log(f"Skipping unreadable forecast file {file_path}: {exc!r}")
			continue

		snapshot_frames.append(
			_normalize_weather_snapshot(
				raw_frame,
				file_path.name,
				snapshot_time,
				snapshot_suffix or "hourly",
					model_elevation_m,
			)
		)

	return snapshot_frames


def _normalize_weather_snapshot(
	snapshot_frame: pd.DataFrame,
	source_file: str,
	source_snapshot_time: pd.Timestamp,
	source_timestep: str,
	model_elevation_m: float,
) -> pd.DataFrame:
	frame = snapshot_frame.copy()
	frame.index = pd.DatetimeIndex(frame.index, tz="UTC")
	frame.index.name = "weather_time_utc"

	if source_timestep == "-3h" and {"minScreenAirTemp", "maxScreenAirTemp"}.issubset(frame.columns):
		screen_temperature = (
			pd.to_numeric(frame["minScreenAirTemp"], errors="coerce")
			+ pd.to_numeric(frame["maxScreenAirTemp"], errors="coerce")
		) / 2
	else:
		if "screenTemperature" in frame.columns:
			screen_temperature = pd.to_numeric(frame["screenTemperature"], errors="coerce")
		else:
			screen_temperature = pd.Series(np.nan, index=frame.index)

	if "uvIndex" in frame.columns:
		uv_index = pd.to_numeric(frame["uvIndex"], errors="coerce")
	else:
		uv_index = pd.Series(np.nan, index=frame.index)

	if "significantWeatherCode" in frame.columns:
		significant_weather_code = pd.to_numeric(frame["significantWeatherCode"], errors="coerce")
	else:
		significant_weather_code = pd.Series(np.nan, index=frame.index)

	if np.isnan(model_elevation_m):
		adjusted_screen_temperature = pd.Series(np.nan, index=frame.index)
	else:
		elevation_delta_m = model_elevation_m - POND_ELEVATION_M
		adjustment_c = LAPSE_RATE_C_PER_KM * (elevation_delta_m / 1000.0)
		adjusted_screen_temperature = screen_temperature + adjustment_c

	frame = pd.DataFrame(
		{
			"screenTemperature": screen_temperature,
			"adjustedScreenTemperature": adjusted_screen_temperature,
			"uvIndex": uv_index,
			"significantWeatherCode": significant_weather_code,
			"source_file": source_file,
			"source_time": frame.index,
			"source_timestep": source_timestep,
			"model_elevation_m": model_elevation_m,
		},
		index=frame.index,
	)
	frame["source_snapshot_time"] = source_snapshot_time
	frame["source_priority"] = 1 if source_timestep == "hourly" else 0
	return frame


def build_unified_weather_dataframe(n_days: int = 7, debug_log: Callable[[str], None] | None = None) -> pd.DataFrame | None:
	if debug_log is None:
		debug_log = lambda _msg: None

	hourly_frames = _load_recent_weather_snapshots(n_days, "", debug_log=debug_log)
	three_hourly_frames = _load_recent_weather_snapshots(n_days, "-3h", debug_log=debug_log)
	if not hourly_frames and not three_hourly_frames:
		return None

	raw_frames = three_hourly_frames + hourly_frames
	raw = pd.concat(raw_frames).sort_index(kind="stable")
	raw = raw[~raw.index.duplicated(keep="last")].sort_index()

	start_time = raw.index.min().floor("h")
	end_time = raw.index.max().ceil("h")
	grid_index = pd.date_range(start=start_time, end=end_time, freq="1h", tz="UTC")
	combined = pd.DataFrame(index=grid_index)
	combined.index.name = "weather_time_utc"

	numeric = raw[["screenTemperature", "uvIndex"]].apply(pd.to_numeric, errors="coerce")
	adjusted_numeric = raw[["adjustedScreenTemperature"]].apply(pd.to_numeric, errors="coerce")
	combined_numeric = (
		numeric.reindex(numeric.index.union(grid_index))
		.sort_index()
		.interpolate(method="time")
		.reindex(grid_index)
	)
	combined_adjusted = (
		adjusted_numeric.reindex(adjusted_numeric.index.union(grid_index))
		.sort_index()
		.interpolate(method="time")
		.reindex(grid_index)
	)
	combined["screenTemperature"] = combined_numeric["screenTemperature"]
	combined["adjustedScreenTemperature"] = combined_adjusted["adjustedScreenTemperature"]
	combined["uvIndex"] = combined_numeric["uvIndex"]
	combined["significantWeatherCode"] = pd.to_numeric(raw["significantWeatherCode"], errors="coerce").reindex(grid_index).ffill().bfill()
	combined["source_file"] = raw["source_file"].reindex(grid_index).ffill()
	combined["source_time"] = raw["source_time"].reindex(grid_index).ffill()
	combined["source_timestep"] = raw["source_timestep"].reindex(grid_index).ffill()
	combined["source_snapshot_time"] = raw["source_snapshot_time"].reindex(grid_index).ffill()
	combined["model_elevation_m"] = raw["model_elevation_m"].reindex(grid_index).ffill()
	combined["is_interpolated"] = ~grid_index.isin(raw.index)

	return combined


def _resolve_weather_row(weather_df: pd.DataFrame | None, target_time: pd.Timestamp) -> pd.Series | None:
	if weather_df is None or weather_df.empty:
		return None
	if target_time < weather_df.index.min() or target_time > weather_df.index.max():
		return None

	augmented = weather_df.reindex(weather_df.index.union([target_time])).sort_index()
	augmented[["screenTemperature", "adjustedScreenTemperature", "uvIndex"]] = augmented[["screenTemperature", "adjustedScreenTemperature", "uvIndex"]].interpolate(method="time")
	for column in ("source_file", "source_time", "source_timestep", "source_snapshot_time", "model_elevation_m", "significantWeatherCode"):
		if column in augmented.columns:
			augmented[column] = augmented[column].ffill()
	row = augmented.loc[target_time]
	if isinstance(row, pd.DataFrame):
		row = row.iloc[0]
	row = row.copy()
	row["is_interpolated"] = bool(target_time not in weather_df.index)
	return row


def _load_weather_frames(n_days: int, debug_log: Callable[[str], None] | None = None) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
	if debug_log is None:
		debug_log = lambda _msg: None

	try:
		from pond.metoffice import load_merged_recent_data
		debug_log("Imported pond.metoffice.load_merged_recent_data")
	except Exception as exc:
		debug_log(f"Failed to import pond.metoffice.load_merged_recent_data: {exc!r}")
		return None, None

	try:
		hourly_weather_df = load_merged_recent_data(nDays=n_days, file_suffix="", verbose=False)
		three_hourly_weather_df = load_merged_recent_data(nDays=n_days, file_suffix="-3h", verbose=False)
	except Exception as exc:
		debug_log(f"Weather merge loader raised exception: {exc!r}")
		return None, None

	return hourly_weather_df, three_hourly_weather_df


def build_hourly_weather_dataframe(
	hourly_weather_df: pd.DataFrame | None,
	three_hourly_weather_df: pd.DataFrame | None,
) -> pd.DataFrame | None:
	weather_columns = ["screenTemperature", "uvIndex"]
	hourly_frame = _prepare_weather_frame(hourly_weather_df)
	three_hourly_frame = _prepare_weather_frame(three_hourly_weather_df, use_three_hour_mean=True)
	if hourly_frame is None and three_hourly_frame is None:
		return None

	frames = [frame for frame in (hourly_frame, three_hourly_frame) if frame is not None and not frame.empty]
	if not frames:
		return None

	start_time = min(frame.index.min() for frame in frames).floor("h")
	end_time = max(frame.index.max() for frame in frames).ceil("h")
	combined_tz = getattr(frames[0].index, "tz", None)
	combined_index = pd.date_range(start=start_time, end=end_time, freq="1h", tz=combined_tz)
	combined = pd.DataFrame(index=combined_index)
	combined.index.name = "weather_time_utc"
	combined["screenTemperature"] = np.nan
	combined["uvIndex"] = np.nan
	combined["source_timestep"] = ""

	if three_hourly_frame is not None and not three_hourly_frame.empty:
		three_hourly_numeric = three_hourly_frame[[column for column in weather_columns if column in three_hourly_frame.columns]]
		three_hourly_hourly = (
			three_hourly_numeric.reindex(three_hourly_numeric.index.union(combined_index))
			.sort_index()
			.interpolate(method="time")
			.reindex(combined_index)
		)
		for column in three_hourly_hourly.columns:
			combined[column] = three_hourly_hourly[column]
		combined["source_timestep"] = "-3h"

	if hourly_frame is not None and not hourly_frame.empty:
		hourly_numeric = hourly_frame[[column for column in weather_columns if column in hourly_frame.columns]]
		hourly_aligned = hourly_numeric.reindex(combined_index)
		hourly_mask = hourly_aligned.notna().any(axis=1)
		for column in hourly_aligned.columns:
			combined.loc[hourly_mask, column] = hourly_aligned.loc[hourly_mask, column]
		combined.loc[hourly_mask, "source_timestep"] = "hourly"

	return combined


def build_test_weather_dataframe(
	input_csv: Path,
	n_days: int = 7,
	debug_log: Callable[[str], None] | None = None,
) -> pd.DataFrame:
	if debug_log is None:
		debug_log = lambda _msg: None

	all_slots, _date_sequence = load_slots_from_csv(input_csv)
	if not all_slots:
		return pd.DataFrame()

	combined_weather_df = build_unified_weather_dataframe(n_days=n_days, debug_log=debug_log)
	if combined_weather_df is None or combined_weather_df.empty:
		return pd.DataFrame()

	london_tz = ZoneInfo("Europe/London")
	utc_tz = ZoneInfo("UTC")

	unique_dates = sorted({slot["date"] for slot in all_slots}, key=lambda value: parse_booking_date(value) or date.min)
	unique_times = sorted({slot["time"] for slot in all_slots})
	slot_lookup = {(slot["date"], slot["time"]) for slot in all_slots}
	rows: list[dict[str, object]] = []

	for slot_date in unique_dates:
		for slot_time in unique_times:
			if (slot_date, slot_time) not in slot_lookup:
				continue
			slot_start_local = parse_slot_start(slot_date, slot_time).replace(tzinfo=london_tz)
			target_time_utc = pd.Timestamp(slot_start_local.astimezone(utc_tz))
			lookup_row = _resolve_weather_row(combined_weather_df, target_time_utc)
			if lookup_row is None:
				continue

			temp_value = lookup_row.get("screenTemperature")
			adjusted_temp_value = lookup_row.get("adjustedScreenTemperature")
			uv_value = lookup_row.get("uvIndex")
			significant_weather_code = lookup_row.get("significantWeatherCode")
			source_timestep = str(lookup_row.get("source_timestep") or "")

			rows.append(
				{
					"slot_date": slot_date,
					"slot_time": slot_time,
					"lookup_time_utc": target_time_utc,
					"source_timestep": source_timestep,
					"source_file": lookup_row.get("source_file"),
					"source_time": lookup_row.get("source_time"),
					"model_elevation_m": lookup_row.get("model_elevation_m"),
					"significantWeatherCode": parse_significant_weather_code(significant_weather_code),
					"significantWeather": describe_significant_weather(significant_weather_code),
					"is_interpolated": bool(lookup_row.get("is_interpolated", False)),
					"screenTemperature": round(float(temp_value), 2) if not pd.isna(temp_value) else pd.NA,
					"adjustedScreenTemperature": round(float(adjusted_temp_value), 2) if not pd.isna(adjusted_temp_value) else pd.NA,
					"uvIndex": round(float(uv_value), 2) if not pd.isna(uv_value) else pd.NA,
				}
			)

	result = pd.DataFrame(rows)
	if result.empty:
		return result

	result["slot_start_local"] = pd.to_datetime(
		result["slot_date"] + " " + result["slot_time"].str.split("-", n=1).str[0],
		format="%Y-%m%d %H:%M",
	).dt.tz_localize(london_tz)
	result = result.set_index("slot_start_local").sort_index()
	result.index.name = "slot_start_local"
	return result[["slot_date", "slot_time", "lookup_time_utc", "source_timestep", "source_file", "source_time", "model_elevation_m", "significantWeatherCode", "significantWeather", "is_interpolated", "screenTemperature", "adjustedScreenTemperature", "uvIndex"]]


def build_test_weather_short_dataframe(weather_df: pd.DataFrame) -> pd.DataFrame:
	"""Build a compact weather dataframe for terminal display."""
	if weather_df.empty:
		return weather_df

	compact = weather_df.copy()
	compact = compact.rename(
		columns={
			"lookup_time_utc": "tLookup",
			"source_timestep": "src_step",
			"source_time": "src_time",
			"model_elevation_m": "model_elev",
			"significantWeatherCode": "SWCode",
			"significantWeather": "SW",
			"is_interpolated": "is_interp",
			"screenTemperature": "scrnTemp",
			"adjustedScreenTemperature": "adjTemp",
		}
	)

	# Keep only HH:MM for slot index and UTC lookup/source times in short mode.
	compact_index_dt = pd.DatetimeIndex(compact.index)
	compact.index = pd.Index(compact_index_dt.strftime("%H:%M"), name="slot_time_local")
	compact["tLookup"] = pd.to_datetime(compact["tLookup"], utc=True).dt.strftime("%H:%M")
	compact["src_time"] = pd.to_datetime(compact["src_time"], utc=True).dt.strftime("%H:%M")

	return compact[
		[
			"slot_date",
			"slot_time",
			"tLookup",
			"src_step",
			"src_time",
			"model_elev",
			"SWCode",
			"SW",
			"is_interp",
			"scrnTemp",
			"adjTemp",
			"uvIndex",
		]
	]


def _prepare_weather_frame(weather_df: pd.DataFrame | None, use_three_hour_mean: bool = False) -> pd.DataFrame | None:
	if weather_df is None or weather_df.empty:
		return None
	frame = weather_df.sort_index().copy()
	if use_three_hour_mean and {"minScreenAirTemp", "maxScreenAirTemp"}.issubset(frame.columns):
		frame["screenTemperature"] = (
			pd.to_numeric(frame["minScreenAirTemp"], errors="coerce")
			+ pd.to_numeric(frame["maxScreenAirTemp"], errors="coerce")
		) / 2
	else:
		temperature_column = next(
			(column for column in ("screenTemperature", "feelsLikeTemp", "maxScreenAirTemp", "minScreenAirTemp") if column in frame.columns),
			None,
		)
		if temperature_column is not None:
			frame["screenTemperature"] = pd.to_numeric(frame[temperature_column], errors="coerce")
	if "uvIndex" in frame.columns:
		frame["uvIndex"] = pd.to_numeric(frame["uvIndex"], errors="coerce")
	return frame


def _format_weather_row(row: pd.Series, use_adjusted_temp: bool = True) -> str:
	if use_adjusted_temp and "adjustedScreenTemperature" in row and not pd.isna(row.get("adjustedScreenTemperature")):
		temp_value = row.get("adjustedScreenTemperature")
	else:
		temp_value = row.get("screenTemperature")
	uv_value = row.get("uvIndex")
	if pd.isna(temp_value) or pd.isna(uv_value):
		return ""

	temp_rounded = int(round(float(temp_value)))
	uv_rounded = int(round(float(uv_value)))
	icon = significant_weather_icon(row.get("significantWeatherCode"))
	prefix = f"{icon} " if icon else ""
	return f"{prefix}{temp_rounded}°C, {uv_rounded}"


def _resolve_from_hourly_frame(weather_df: pd.DataFrame | None, target_time: pd.Timestamp) -> tuple[str, str]:
	frame = _prepare_weather_frame(weather_df)
	if frame is None:
		return "", "no-hourly-data"

	if target_time in frame.index:
		row = frame.loc[target_time]
		if isinstance(row, pd.DataFrame):
			row = row.iloc[0]
		weather_text = _format_weather_row(row)
		return weather_text, "hourly-exact" if weather_text else "hourly-missing-values"

	idx = frame.index.get_indexer(pd.DatetimeIndex([target_time]), method="nearest")
	if len(idx) == 0 or idx[0] < 0:
		return "", "hourly-no-nearest-index"
	nearest_time = cast(pd.Timestamp, frame.index[idx[0]])
	if abs(nearest_time - target_time) > pd.Timedelta(hours=1):
		return "", "hourly-nearest-too-far"
	row = frame.iloc[idx[0]]
	weather_text = _format_weather_row(row)
	return weather_text, "hourly-nearest" if weather_text else "hourly-missing-values"


def _resolve_from_three_hour_frame(weather_df: pd.DataFrame | None, target_time: pd.Timestamp) -> tuple[str, str]:
	frame = _prepare_weather_frame(weather_df)
	if frame is None:
		return "", "no-three-hour-data"

	if target_time < frame.index.min() or target_time > frame.index.max():
		return "", "three-hour-out-of-range"

	augmented = frame.reindex(frame.index.union([target_time])).sort_index().interpolate(method="time")
	row = augmented.loc[target_time]
	if isinstance(row, pd.DataFrame):
		row = row.iloc[0]
	weather_text = _format_weather_row(row)
	if weather_text:
		return weather_text, "three-hour-interpolated" if target_time not in frame.index else "three-hour-exact"
	return "", "three-hour-missing-values"


def resolve_slot_weather(
	weather_df: pd.DataFrame | None,
	slot_date: str,
	slot_time: str,
	london_tz: ZoneInfo,
	utc_tz: ZoneInfo,
	use_adjusted_temp: bool = True,
) -> tuple[str, str]:
	"""Return weather text for slot start time, converting local BST/GMT to UTC."""
	try:
		slot_start_local = parse_slot_start(slot_date, slot_time).replace(tzinfo=london_tz)
	except ValueError:
		return "", "slot-parse-failed"

	slot_start_utc = slot_start_local.astimezone(utc_tz)
	target_time = pd.Timestamp(slot_start_utc)
	row = _resolve_weather_row(weather_df, target_time)
	if row is None:
		return "", "no-weather-match"

	weather_text = _format_weather_row(row, use_adjusted_temp=use_adjusted_temp)
	if not weather_text:
		return "", "missing-temp-or-uv"

	reason = str(row.get("source_timestep") or "weather")
	if row.get("is_interpolated"):
		reason = f"{reason}-interpolated"
	return weather_text, reason


def build_weather_by_slot(
	date_sequence: list[str],
	all_times: list[str],
	n_days: int = 7,
	debug_log: Callable[[str], None] | None = None,
	use_adjusted_temp: bool = True,
) -> dict[tuple[str, str], str]:
	"""Build weather display strings for each slot start from merged forecast files."""
	if debug_log is None:
		debug_log = lambda _msg: None

	debug_log(
		f"Starting weather merge: n_days={n_days}, day_count={len(date_sequence)}, slot_time_count={len(all_times)}"
	)

	weather_df = build_unified_weather_dataframe(n_days=n_days, debug_log=debug_log)
	if weather_df is None:
		return {}

	debug_log(
		"Weather dataframes loaded: "
		f"rows={len(weather_df)}, "
		f"index_min={weather_df.index.min()}, index_max={weather_df.index.max()}, "
		f"interpolated_rows={int(weather_df['is_interpolated'].sum()) if 'is_interpolated' in weather_df.columns else 0}"
	)

	london_tz = ZoneInfo("Europe/London")
	utc_tz = ZoneInfo("UTC")
	weather_by_slot: dict[tuple[str, str], str] = {}
	reason_counts: dict[str, int] = defaultdict(int)
	hit_count = 0
	for day in date_sequence:
		for slot_time in all_times:
			weather_text, reason = resolve_slot_weather(
				weather_df,
				day,
				slot_time,
				london_tz,
				utc_tz,
				use_adjusted_temp=use_adjusted_temp,
			)
			reason_counts[reason] += 1
			if weather_text:
				hit_count += 1
				weather_by_slot[(day, slot_time)] = weather_text

	debug_log(
		f"Weather lookup complete: matched={hit_count}, total_checks={len(date_sequence) * len(all_times)}, "
		f"reason_counts={dict(reason_counts)}"
	)
	return weather_by_slot


def slot_group_for_time(slot_time: str) -> str:
	return "lido" if slot_time in LIDO_SLOT_TIMES else "pond"


def parse_booking_date(date_text: str) -> date | None:
	clean = (date_text or "").strip()
	for fmt in ("%Y-%m%d", "%Y-%m-%d"):
		try:
			return datetime.strptime(clean, fmt).date()
		except ValueError:
			continue
	return None


def day_group_for_date(parsed_day: date | None, reference_date: date | None) -> str:
	if parsed_day is None or reference_date is None:
		return "today"
	if parsed_day < reference_date:
		return "past"
	if parsed_day == reference_date:
		return "today"
	if parsed_day == (reference_date + timedelta(days=1)):
		return "tomorrow"
	return "future"


def format_relative_day_label(target_date: date, reference_date: date) -> str:
	delta_days = (target_date - reference_date).days
	if delta_days == 0:
		return "today"
	if delta_days == -1:
		return "yesterday"
	if delta_days == 1:
		return "tomorrow"
	if delta_days < 0:
		return f"{abs(delta_days)} days ago"
	return f"in {delta_days} days"


def format_booking_day_heading(date_text: str, reference_date: date | None = None) -> str:
	"""Format booking day headings as Weekday + original date text (+ relative label)."""
	clean = (date_text or "").strip()
	parsed_date = parse_booking_date(clean)
	if parsed_date is None:
		return clean

	heading = f"{parsed_date.strftime('%A')} {clean}"
	if reference_date is not None:
		relative = format_relative_day_label(parsed_date, reference_date)
		heading = f"{heading} ({relative})"
	return heading


def format_elapsed(delta: timedelta) -> str:
	total_hours = max(int(delta.total_seconds() // 3600), 0)
	days, hours = divmod(total_hours, 24)
	if days:
		return f"{days}d{hours}h" if hours else f"{days}d"
	return f"{hours}h"


def find_effective_count(points: list[tuple[datetime, int]], moment: datetime) -> int | None:
	eligible = [count for snapshot_time, count in points if snapshot_time <= moment]
	if eligible:
		return eligible[-1]
	for snapshot_time, count in points:
		if snapshot_time > moment:
			return count
	return None


def load_slot_history(
	selected_csv: Path,
	historical_days: int = HISTORICAL_DAYS,
	booking_lead_days: int = BOOKING_LEAD_DAYS,
) -> tuple[dict[tuple[str, str, str, str], list[tuple[datetime, int]]], list[str], datetime]:
	reference_time = infer_snapshot_time(selected_csv)
	selected_slots, selected_dates = load_slots_from_csv(selected_csv)
	max_report_date = max((slot["date"] for slot in selected_slots), default=reference_time.strftime("%Y-%m%d"))
	min_report_date = (reference_time.date() - timedelta(days=historical_days)).strftime("%Y-%m%d")
	history_start = datetime.combine(reference_time.date() - timedelta(days=historical_days + booking_lead_days), time(0, 0))

	history_by_slot: dict[tuple[str, str, str, str], list[tuple[datetime, int]]] = defaultdict(list)
	for archive_path in sorted(DATA_DIR.glob(ARCHIVE_GLOB), key=parse_archive_timestamp):
		snapshot_time = parse_archive_timestamp(archive_path)
		if snapshot_time < history_start or snapshot_time > reference_time:
			continue
		archive_slots, _archive_dates = load_slots_from_csv(archive_path)
		for slot in archive_slots:
			if not (min_report_date <= slot["date"] <= max_report_date):
				continue
			key = (slot["date"], slot["time"], slot["location"], slot["duration"])
			history_by_slot[key].append((snapshot_time, availability_to_count(slot["availability"])))

	date_sequence = sorted({slot_date for slot_date, *_rest in history_by_slot})
	return history_by_slot, date_sequence, reference_time


def build_report_slots(
	selected_csv: Path,
	historical_days: int = HISTORICAL_DAYS,
	booking_lead_days: int = BOOKING_LEAD_DAYS,
) -> tuple[list[dict[str, str | int]], list[str], datetime]:
	history_by_slot, date_sequence, reference_time = load_slot_history(
		selected_csv,
		historical_days=historical_days,
		booking_lead_days=booking_lead_days,
	)
	report_slots: list[dict[str, str | int]] = []
	for (slot_date, slot_time, location, duration), points in sorted(history_by_slot.items()):
		sorted_points = sorted(points)
		final_count = sorted_points[-1][1]
		start_dt = parse_slot_start(slot_date, slot_time)
		start_count = find_effective_count(sorted_points, start_dt)
		if start_count is None:
			start_count = final_count
		is_historical = start_dt <= reference_time
		if is_historical and start_count != final_count:
			display_text = f"{start_count} ({final_count})"
			display_count = start_count
		else:
			display_text = str(final_count if not is_historical else start_count)
			display_count = final_count if not is_historical else start_count

		booked_out_age = ""
		first_zero = next((snapshot_time for snapshot_time, count in sorted_points if count == 0), None)
		if final_count < 5 and first_zero is not None and start_dt > first_zero:
			booked_out_age = format_elapsed(start_dt - first_zero)

		report_slots.append(
			{
				"date": slot_date,
				"time": slot_time,
				"location": location,
				"duration": duration,
				"availability": final_count,
				"availability_display": display_text,
				"availability_style": display_count,
				"availability_final": final_count,
				"booked_out_age": booked_out_age,
			}
		)
	return report_slots, date_sequence, reference_time


def load_slots_from_csv(csv_path):
	all_slots = []
	date_sequence = []
	with open(csv_path, newline="", encoding="utf-8") as f:
		reader = csv.DictReader(f)
		for row in reader:
			slot = {
				"date": (row.get("date") or "").strip(),
				"time": (row.get("time") or "").strip(),
				"location": (row.get("location") or "").strip(),
				"duration": (row.get("duration") or "").strip(),
				"availability": (row.get("availability") or "").strip(),
			}
			if not slot["date"] or not slot["time"] or not slot["location"]:
				continue
			all_slots.append(slot)
			if slot["date"] not in date_sequence:
				date_sequence.append(slot["date"])
	return all_slots, date_sequence


def write_html_report(
	all_slots,
	date_sequence,
	html_output,
	source_url,
	reference_time: datetime | None = None,
	weather_debug_log: Callable[[str], None] | None = None,
	use_adjusted_temp: bool = True,
):
	if weather_debug_log is None:
		weather_debug_log = lambda _msg: None

	venues = ["Men's", "Ladies", "Mixed", "Lido"]
	table = defaultdict(lambda: defaultdict(dict))
	for s in all_slots:
		date_label = s.get("date_display") or s.get("date", "")
		table[date_label][s["time"]][s["location"]] = s["availability"]
		if s.get("availability_display") is not None:
			table[date_label][s["time"]][f"{s['location']}__display"] = s["availability_display"]
		if s.get("availability_style") is not None:
			table[date_label][s["time"]][f"{s['location']}__style"] = s["availability_style"]
		if s.get("availability_final") is not None:
			table[date_label][s["time"]][f"{s['location']}__final"] = s["availability_final"]
		if s.get("booked_out_age"):
			table[date_label][s["time"]][f"{s['location']}__age"] = s["booked_out_age"]

	dates = [d for d in date_sequence if d in table]
	all_times = sorted(set(t for d in table.values() for t in d.keys()))
	weather_by_slot = build_weather_by_slot(
		dates,
		all_times,
		debug_log=weather_debug_log,
		use_adjusted_temp=use_adjusted_temp,
	)
	weather_debug_log(f"Weather entries available for report slots: {len(weather_by_slot)}")
	reference_date = reference_time.date() if reference_time is not None else None

	day_group_by_date: dict[str, str] = {}
	for day in dates:
		parsed_day = parse_booking_date(day)
		group = day_group_for_date(parsed_day, reference_date)
		day_group_by_date[day] = group

	with open(html_output, "w", encoding="utf-8") as f:
		updated_at = datetime.now().strftime("%a, %d %b %Y %H:%M")
		f.write("<div class='bookings-widget'>\n")
		f.write(
			f"<p class='meta'>Last updated: {html_lib.escape(updated_at)} | "
			f"<a href='{html_lib.escape(source_url)}' target='_blank' rel='noopener noreferrer'>"
			"Open City of London bookings page</a></p>\n"
		)

		for date in dates:
			date_value = html_lib.escape(date, quote=True)
			day_group = day_group_by_date[date]
			f.write(f"<div class='booking-day' data-day='{date_value}' data-day-group='{day_group}'>\n")
			date_heading = format_booking_day_heading(date, reference_date)
			f.write(f"<h3>{html_lib.escape(date_heading)}</h3>\n")
			f.write(f"<table class='bookings-table' data-day='{date_value}'>\n<tr><th>Time</th>")
			for idx, v in enumerate(venues):
				f.write(f"<th class='venue-col' data-venue-idx='{idx}'>{html_lib.escape(v)}</th>")
			f.write("<th class='weather-col weather-hidden'>Weather</th>")
			f.write("</tr>\n")
			for t in all_times:
				if t not in table[date]:
					continue
				slot_group = slot_group_for_time(t)
				slot_status_class = "slot-historical" if is_fully_historical_slot(date, t, reference_time) else "slot-current"
				time_value = html_lib.escape(t, quote=True)
				f.write(
					f"<tr data-time='{time_value}' data-slot-group='{slot_group}'>"
					f"<td class='time-cell {slot_status_class}'><b>{html_lib.escape(t)}</b></td>"
				)
				for idx, v in enumerate(venues):
					avail_raw = table[date][t].get(v)
					if avail_raw is None:
						f.write(f'<td class="empty venue-cell" data-venue-idx="{idx}">—</td>')
						continue

					avail = str(table[date][t].get(f"{v}__display") or availability_to_display(avail_raw))
					ticket_count = availability_to_count(table[date][t].get(f"{v}__style", avail_raw))
					booked_out_age = str(table[date][t].get(f"{v}__age") or "")

					if ticket_count <= 0:
						f.write(f'<td class="fully-booked venue-cell" data-venue-idx="{idx}">')
						f.write(html_lib.escape(avail))
						if booked_out_age:
							f.write(f'<div class="booked-out-age">{html_lib.escape(booked_out_age)}</div>')
						f.write("</td>")
					else:
						max_capacity = 650 if v == "Lido" else 120
						ratio = (ticket_count / max_capacity) if ticket_count > 0 else 0
						percentage = ratio * 100
						if ratio < (1 / 6):
							bar_color = "rgba(234, 88, 12, 0.45)"
							cell_bg_color = "#ffedd5"
						elif ratio < (1 / 3):
							bar_color = "rgba(250, 204, 21, 0.35)"
							cell_bg_color = "#fef9c3"
						else:
							bar_color = "rgba(34, 197, 94, 0.35)"
							cell_bg_color = "#d4edda"
						bar_width = min(percentage, 100)
						f.write(
							f'<td class="available venue-cell" data-venue-idx="{idx}" style="position: relative; padding: 0; '
							f'background: {cell_bg_color};">'
						)
						f.write(
							f'<div style="position: absolute; left: 0; top: 0; bottom: 0; '
							f'width: {bar_width}%; background: {bar_color}; pointer-events: none;"></div>'
						)
						f.write(
							f'<div style="position: relative; padding: 6px 12px;">{html_lib.escape(avail)}'
						)
						if booked_out_age:
							f.write(f'<div class="booked-out-age">{html_lib.escape(booked_out_age)}</div>')
						f.write("</div>")
						f.write("</td>")
				weather_text = weather_by_slot.get((date, t), "")
				weather_display = html_lib.escape(weather_text) if weather_text else "—"
				f.write(
					f"<td class='weather-cell weather-col weather-hidden {slot_status_class}'>{weather_display}</td>"
				)
				f.write("</tr>\n")
			f.write("</table>\n")
			f.write("</div>\n")
		f.write("</div>\n")


def write_json_file(path: str, payload: object) -> None:
	with open(path, "w", encoding="utf-8") as fh:
		json.dump(payload, fh, indent=2, ensure_ascii=False)
		fh.write("\n")


def main() -> None:
	parser = argparse.ArgumentParser(description="Generate bookings.html from a bookings CSV file.")
	parser.add_argument(
		"--input-csv",
		default=None,
		help="Bookings CSV filename/path to read. Default: newest archived bookings CSV in ./data.",
	)
	parser.add_argument(
		"--html-output",
		default="bookings.html",
		help="HTML summary filename/path. Bare filename goes under --output-dir.",
	)
	parser.add_argument(
		"--source-url",
		default="https://cityoflondon.xnlcloud.com/LhWeb/en/Members/Home",
		help="URL shown in the generated HTML as the source link.",
	)
	parser.add_argument(
		"--output-dir",
		default="output",
		help="Default directory for outputs when output args are bare filenames.",
	)
	parser.add_argument(
		"--filters",
		action="store_true",
		help="Enable interactive filter buttons for venues, days, and slot times.",
	)
	parser.add_argument(
		"--weather-debug",
		action="store_true",
		help="Enable verbose weather integration debug logs.",
	)
	parser.add_argument(
		"--weather-debug-log",
		default="logs/booking-report-weather.log",
		help="Debug log file path used with --weather-debug. Relative paths are resolved from current working directory.",
	)
	parser.add_argument(
		"--test-weather",
		action="store_true",
		help="Print a slot-indexed weather dataframe for debugging interpolation and forecast source selection.",
	)
	parser.add_argument(
		"--test-weather-short",
		action="store_true",
		help="Print a compact weather dataframe with short column names and HH:MM times.",
	)
	parser.add_argument(
		"--raw-temp",
		action="store_true",
		help="Use raw screenTemperature instead of elevation-adjusted temperatures in booking-report weather output.",
	)
	args = parser.parse_args()

	if args.input_csv is None:
		input_csv = find_latest_bookings_csv(DATA_DIR)
	else:
		input_csv = Path(resolve_output_path(args.output_dir, args.input_csv))
	html_output = resolve_output_path(args.output_dir, args.html_output)
	meta_output = resolve_output_path(args.output_dir, "bookings-meta.json")
	os.makedirs(os.path.dirname(html_output) or ".", exist_ok=True)
	weather_debug_log = make_debug_logger(args.weather_debug, args.weather_debug_log if args.weather_debug else None)
	weather_debug_log(f"booking-report start: input_csv={input_csv}, html_output={html_output}")

	if args.test_weather or args.test_weather_short:
		weather_df = build_test_weather_dataframe(input_csv, debug_log=weather_debug_log)
		if weather_df.empty:
			print("ERROR: No test-weather dataframe could be built")
			sys.exit(1)
		if args.test_weather_short:
			weather_df = build_test_weather_short_dataframe(weather_df)
		with pd.option_context("display.max_rows", None, "display.max_columns", None, "display.width", 200):
			print(weather_df.round({"scrnTemp": 2, "adjTemp": 2, "screenTemperature": 2, "adjustedScreenTemperature": 2, "uvIndex": 2}).to_string())
		sys.exit()

	all_slots, date_sequence, reference_time = build_report_slots(input_csv)
	weather_debug_log(
		f"slot data loaded: all_slots={len(all_slots)}, date_sequence={len(date_sequence)}, reference_time={reference_time}"
	)
	metadata = build_report_metadata(input_csv, all_slots, date_sequence, datetime.now(ZoneInfo("UTC")))
	write_html_report(
		all_slots,
		date_sequence,
		html_output,
		args.source_url,
		reference_time=reference_time,
		weather_debug_log=weather_debug_log,
		use_adjusted_temp=not args.raw_temp,
	)
	write_json_file(meta_output, metadata)
	print(f"Loaded slots from CSV: {input_csv}")
	print(f"Saved: {html_output}")
	print(f"Saved: {meta_output}")


if __name__ == "__main__":
	main()