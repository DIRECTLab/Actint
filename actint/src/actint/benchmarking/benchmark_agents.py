import argparse
import csv
import gc
import inspect
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
	import yaml
except ModuleNotFoundError as exc:  # pragma: no cover - environment safeguard
	raise ModuleNotFoundError(
		"PyYAML is required for benchmarking config loading. Install with: pip install pyyaml"
	) from exc
from mcp import StdioServerParameters
from smolagents import MCPClient, ToolCallingAgent, TransformersModel

from actint.mcp import mcp_server


BENCHMARK_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = BENCHMARK_DIR / "benchmarks.yaml"
DEFAULT_RESULTS_ROOT = BENCHMARK_DIR / "results"
ACTINT_SQLITE_PATH_ENV = "ACTINT_SQLITE_PATH"
DEFAULT_ANOMALIES_ROOT = Path(__file__).resolve().parents[3] / "data" / "db" / "anomalies"


@dataclass
class PositionRecord:
	mmsi: int
	latitude: float
	longitude: float
	timestamp: str


def _resolve_sqlite_path() -> Path:
	"""Resolve SQLite path from likely workspace locations."""
	override = os.getenv(ACTINT_SQLITE_PATH_ENV)
	if override:
		return Path(override).expanduser().resolve()

	candidates = [
		Path(__file__).resolve().parents[3] / "data" / "db" / "ais.db",
		Path(__file__).resolve().parents[4] / "data" / "db" / "ais.db",
	]
	for candidate in candidates:
		if candidate.exists():
			return candidate
	return candidates[0]


SQLITE_PATH = _resolve_sqlite_path()


def _now_utc() -> str:
	return datetime.now(timezone.utc).isoformat()


def _timestamp_for_path() -> str:
	return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _default_output_json_path() -> Path:
	timestamp_dir = DEFAULT_RESULTS_ROOT / _timestamp_for_path()
	return timestamp_dir / "benchmark_results.json"


def _read_yaml_or_json(path: Path) -> dict[str, Any]:
	with path.open("r", encoding="utf-8") as f:
		return yaml.safe_load(f) or {}


def _find_catalog_files_under(root: Path) -> list[Path]:
	if not root.exists():
		return []

	patterns = [
		"**/*benchmark*.yaml",
		"**/*benchmark*.yml",
		"**/*benchmark*.json",
	]
	files: set[Path] = set()
	for pattern in patterns:
		for file_path in root.glob(pattern):
			if file_path.is_file():
				files.add(file_path.resolve())
	return sorted(files)


def _load_benchmark_catalogs(
	config_path: Path,
	anomalies_root: Path | None,
	extra_catalog_files: list[Path],
) -> dict[str, dict[str, Any]]:
	catalog_map: dict[str, dict[str, Any]] = {}

	default_catalog_dirs = [
		config_path.parent / "benchmark_definitions",
	]
	if anomalies_root is not None:
		default_catalog_dirs.append(anomalies_root)

	catalog_files: set[Path] = set()
	for directory in default_catalog_dirs:
		for file_path in _find_catalog_files_under(directory):
			catalog_files.add(file_path)

	for file_path in extra_catalog_files:
		if file_path.exists() and file_path.is_file():
			catalog_files.add(file_path.resolve())

	for file_path in sorted(catalog_files):
		try:
			parsed = _read_yaml_or_json(file_path)
		except Exception:
			continue

		benchmarks = parsed.get("benchmarks", []) if isinstance(parsed, dict) else []
		if not isinstance(benchmarks, list):
			continue

		for benchmark in benchmarks:
			if not isinstance(benchmark, dict):
				continue
			benchmark_id = benchmark.get("id")
			if not benchmark_id:
				continue
			if benchmark_id in catalog_map:
				raise ValueError(
					f"Duplicate benchmark id '{benchmark_id}' found in catalog files. "
					"Ensure benchmark ids are globally unique."
				)
			catalog_map[benchmark_id] = benchmark

	return catalog_map


def _resolve_requested_benchmarks(
	base_config: dict[str, Any],
	catalog_map: dict[str, dict[str, Any]],
	only_benchmark: str | None,
) -> list[dict[str, Any]]:
	requested_names: list[str] = []
	for key in ("benchmark_names", "benchmarks"):
		value = base_config.get(key)
		if not isinstance(value, list):
			continue
		for item in value:
			if isinstance(item, str):
				requested_names.append(item)
			elif isinstance(item, dict) and item.get("id"):
				requested_names.append(str(item["id"]))

	if only_benchmark and only_benchmark not in requested_names:
		requested_names.append(only_benchmark)

	# Include inline full benchmark definitions from config for backward compatibility.
	inline_benchmarks = [
		item
		for item in base_config.get("benchmarks", [])
		if isinstance(item, dict) and item.get("prompt_template")
	]
	inline_ids = {str(item["id"]): item for item in inline_benchmarks if item.get("id")}

	resolved: list[dict[str, Any]] = []
	missing: list[str] = []
	seen: set[str] = set()
	for benchmark_id in requested_names:
		if benchmark_id in seen:
			continue
		seen.add(benchmark_id)

		if benchmark_id in inline_ids:
			resolved.append(inline_ids[benchmark_id])
			continue

		definition = catalog_map.get(benchmark_id)
		if definition is None:
			missing.append(benchmark_id)
			continue
		resolved.append(definition)

	if missing:
		print(
			"Warning: benchmark definitions not found for ids: "
			+ ", ".join(sorted(set(missing)))
		)

	if not resolved:
		raise ValueError(
			"No benchmark definitions resolved. Check benchmark_names/benchmarks in config and "
			"ensure matching catalog files are discoverable."
		)

	if only_benchmark:
		resolved = [b for b in resolved if b.get("id") == only_benchmark]
		if not resolved:
			raise ValueError(f"Benchmark '{only_benchmark}' was requested but no definition was resolved")

	return resolved


def load_config(
	path: Path,
	only_benchmark: str | None = None,
	anomalies_root: Path | None = None,
	extra_catalog_files: list[Path] | None = None,
) -> dict[str, Any]:
	data = _read_yaml_or_json(path)

	if "agents" not in data or not isinstance(data["agents"], list):
		raise ValueError("Config must contain an 'agents' list")

	extra_catalog_files = extra_catalog_files or []
	catalog_map = _load_benchmark_catalogs(
		config_path=path,
		anomalies_root=anomalies_root,
		extra_catalog_files=extra_catalog_files,
	)
	resolved_benchmarks = _resolve_requested_benchmarks(data, catalog_map, only_benchmark)

	data["benchmarks"] = resolved_benchmarks

	return data


def _get_connection() -> sqlite3.Connection:
	if not SQLITE_PATH.exists():
		raise FileNotFoundError(f"SQLite database not found at {SQLITE_PATH}")
	return sqlite3.connect(str(SQLITE_PATH))


def _quote_sqlite_identifier(identifier: str) -> str:
	return '"' + (identifier or "").replace('"', '""') + '"'


def _resolve_ais_positions_column_map(conn: sqlite3.Connection) -> dict[str, str]:
	rows = conn.execute("PRAGMA table_info(ais_positions)").fetchall()
	if not rows:
		raise RuntimeError("Table ais_positions not found or has no columns")

	available = {str(row[1]) for row in rows}

	def pick(preferred: list[str], logical_name: str) -> str:
		for name in preferred:
			if name in available:
				return name
		raise RuntimeError(
			f"Could not resolve column for '{logical_name}'. Available columns: {sorted(available)}"
		)

	return {
		"mmsi": pick(["mmsi"], "mmsi"),
		"timestamp": pick(["timestamp", "base_datetime"], "timestamp"),
		"latitude": pick(["latitude", "lat"], "latitude"),
		"longitude": pick(["longitude", "lon"], "longitude"),
	}


def latest_record() -> PositionRecord:
	with _get_connection() as conn:
		col_map = _resolve_ais_positions_column_map(conn)
		query = (
			f"SELECT "
			f"{_quote_sqlite_identifier(col_map['mmsi'])} AS mmsi, "
			f"{_quote_sqlite_identifier(col_map['timestamp'])} AS timestamp, "
			f"{_quote_sqlite_identifier(col_map['latitude'])} AS latitude, "
			f"{_quote_sqlite_identifier(col_map['longitude'])} AS longitude "
			"FROM ais_positions "
			"ORDER BY timestamp DESC "
			"LIMIT 1"
		)
		row = conn.execute(query).fetchone()

	if not row:
		raise RuntimeError("No rows found in ais_positions")

	mmsi, timestamp, latitude, longitude = row
	return PositionRecord(
		mmsi=int(mmsi),
		latitude=float(latitude),
		longitude=float(longitude),
		timestamp=str(timestamp),
	)


def current_position_for_mmsi(mmsi: int) -> PositionRecord:
	with _get_connection() as conn:
		col_map = _resolve_ais_positions_column_map(conn)
		query = (
			f"SELECT "
			f"{_quote_sqlite_identifier(col_map['mmsi'])} AS mmsi, "
			f"{_quote_sqlite_identifier(col_map['timestamp'])} AS timestamp, "
			f"{_quote_sqlite_identifier(col_map['latitude'])} AS latitude, "
			f"{_quote_sqlite_identifier(col_map['longitude'])} AS longitude "
			"FROM ais_positions "
			"WHERE mmsi = ? "
			"ORDER BY timestamp DESC "
			"LIMIT 1"
		)
		row = conn.execute(query, (mmsi,)).fetchone()

	if not row:
		raise RuntimeError(f"No AIS records found for MMSI {mmsi}")

	mmsi_val, timestamp, latitude, longitude = row
	return PositionRecord(
		mmsi=int(mmsi_val),
		latitude=float(latitude),
		longitude=float(longitude),
		timestamp=str(timestamp),
	)


def build_runtime_inputs(input_source: dict[str, Any]) -> dict[str, Any]:
	source_type = (input_source or {}).get("type", "latest_record_mmsi")

	if source_type == "latest_record_mmsi":
		latest = latest_record()
		return {"mmsi": latest.mmsi}

	if source_type == "fixed":
		values = (input_source or {}).get("values", {})
		if not isinstance(values, dict):
			raise ValueError("fixed input_source requires a dict under values")
		return values

	if source_type == "loitering_anomaly_targets_from_db":
		limit = int((input_source or {}).get("limit", 5))
		if limit <= 0:
			limit = 5
		with _get_connection() as conn:
			rows = conn.execute(
				"SELECT mmsi FROM loitering_anomalies ORDER BY mmsi LIMIT ?",
				(limit,),
			).fetchall()

		targets = [int(row[0]) for row in rows]
		if not targets:
			raise RuntimeError(
				"No loitering anomaly targets found. Ensure loitering_anomalies table is populated "
				"in the benchmark SQLite database."
			)

		return {
			"expected_loitering_mmsis": targets,
			"expected_count": len(targets),
		}

	raise ValueError(f"Unsupported input_source type: {source_type}")


def _extract_json_object(text: str) -> dict[str, Any] | None:
	text = text.strip()

	try:
		obj = json.loads(text)
		if isinstance(obj, dict):
			return obj
	except json.JSONDecodeError:
		pass

	candidates = re.findall(r"\{[\s\S]*?\}", text)
	for candidate in candidates:
		try:
			obj = json.loads(candidate)
			if isinstance(obj, dict):
				return obj
		except json.JSONDecodeError:
			continue

	return None


def parse_position_prediction(agent_output: Any) -> dict[str, Any]:
	if isinstance(agent_output, dict):
		payload = agent_output
	else:
		payload = _extract_json_object(str(agent_output))

	if payload:
		lat = payload.get("latitude", payload.get("lat"))
		lon = payload.get("longitude", payload.get("lon"))
		mmsi = payload.get("mmsi")
		timestamp = payload.get("timestamp")

		if lat is None or lon is None:
			raise ValueError("Missing latitude/longitude fields in agent JSON output")

		parsed = {
			"mmsi": int(mmsi) if mmsi is not None else None,
			"latitude": float(lat),
			"longitude": float(lon),
			"timestamp": str(timestamp) if timestamp is not None else None,
		}
		return parsed

	text = str(agent_output)
	lat_match = re.search(r"(?:latitude|lat)\s*[:=]\s*(-?\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
	lon_match = re.search(r"(?:longitude|lon)\s*[:=]\s*(-?\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
	mmsi_match = re.search(r"mmsi\s*[:=]\s*(\d+)", text, flags=re.IGNORECASE)
	ts_match = re.search(r"timestamp\s*[:=]\s*([0-9T:\-.+Z]+)", text, flags=re.IGNORECASE)

	if not lat_match or not lon_match:
		raise ValueError("Unable to parse latitude/longitude from agent output")

	return {
		"mmsi": int(mmsi_match.group(1)) if mmsi_match else None,
		"latitude": float(lat_match.group(1)),
		"longitude": float(lon_match.group(1)),
		"timestamp": ts_match.group(1) if ts_match else None,
	}


def _coerce_mmsi_list(value: Any) -> list[int]:
	if value is None:
		return []
	if isinstance(value, (int, str)):
		try:
			return [int(value)]
		except Exception:
			return []
	if isinstance(value, list):
		output: list[int] = []
		for item in value:
			try:
				output.append(int(item))
			except Exception:
				continue
		return output
	return []


def parse_loitering_prediction(agent_output: Any) -> dict[str, Any]:
	if isinstance(agent_output, dict):
		payload = agent_output
	else:
		payload = _extract_json_object(str(agent_output))

	if payload:
		for key in ["loitering_mmsi", "loitering_mmsis", "mmsis", "ships", "vessels"]:
			if key in payload:
				mmsis = sorted(set(_coerce_mmsi_list(payload.get(key))))
				return {"mmsis": mmsis}

	text = str(agent_output)
	mmsis = sorted(set(int(m.group(0)) for m in re.finditer(r"\b\d{9}\b", text)))
	return {"mmsis": mmsis}


def validate_current_position_from_db(
	runtime_inputs: dict[str, Any],
	agent_output: Any,
	validation_config: dict[str, Any],
) -> dict[str, Any]:
	expected = current_position_for_mmsi(int(runtime_inputs["mmsi"]))
	predicted = parse_position_prediction(agent_output)

	lat_tol = float(validation_config.get("latitude_tolerance", 0.02))
	lon_tol = float(validation_config.get("longitude_tolerance", 0.02))
	require_timestamp = bool(validation_config.get("require_timestamp_match", False))

	lat_error = abs(predicted["latitude"] - expected.latitude)
	lon_error = abs(predicted["longitude"] - expected.longitude)

	timestamp_ok = True
	if require_timestamp:
		timestamp_ok = predicted.get("timestamp") == expected.timestamp

	success = lat_error <= lat_tol and lon_error <= lon_tol and timestamp_ok

	return {
		"success": success,
		"expected": {
			"mmsi": expected.mmsi,
			"latitude": expected.latitude,
			"longitude": expected.longitude,
			"timestamp": expected.timestamp,
		},
		"predicted": predicted,
		"metrics": {
			"latitude_error": lat_error,
			"longitude_error": lon_error,
			"latitude_tolerance": lat_tol,
			"longitude_tolerance": lon_tol,
			"timestamp_match": timestamp_ok,
		},
	}


def validate_loitering_detection(
	runtime_inputs: dict[str, Any],
	agent_output: Any,
	validation_config: dict[str, Any],
) -> dict[str, Any]:
	expected = [int(x) for x in runtime_inputs.get("expected_loitering_mmsis", [])]
	if not expected:
		raise ValueError("Runtime inputs missing expected_loitering_mmsis")

	predicted = parse_loitering_prediction(agent_output)
	found = sorted(set(int(x) for x in predicted.get("mmsis", [])))

	expected_set = set(expected)
	found_set = set(found)
	detected_expected = sorted(expected_set.intersection(found_set))
	missed_expected = sorted(expected_set.difference(found_set))
	false_positives = sorted(found_set.difference(expected_set))

	minimum_detected = int(validation_config.get("minimum_detected", len(expected)))
	require_all_expected = bool(validation_config.get("require_all_expected", False))

	success = len(detected_expected) >= minimum_detected
	if require_all_expected:
		success = success and not missed_expected

	return {
		"success": success,
		"expected": {
			"expected_loitering_mmsis": expected,
			"expected_count": len(expected),
		},
		"predicted": {
			"reported_mmsis": found,
			"reported_count": len(found),
		},
		"metrics": {
			"minimum_detected": minimum_detected,
			"detected_expected_count": len(detected_expected),
			"detected_expected_mmsis": detected_expected,
			"missed_expected_mmsis": missed_expected,
			"false_positive_mmsis": false_positives,
		},
	}


def validate_result(
	benchmark: dict[str, Any],
	runtime_inputs: dict[str, Any],
	agent_output: Any,
) -> dict[str, Any]:
	validation = benchmark.get("validation", {})
	method = validation.get("method")

	if method == "current_position_from_db":
		return validate_current_position_from_db(runtime_inputs, agent_output, validation)

	if method == "loitering_detection":
		return validate_loitering_detection(runtime_inputs, agent_output, validation)

	raise ValueError(f"Unsupported validation method: {method}")


def build_server_params() -> StdioServerParameters:
	python_executable = sys.executable
	conda_prefix = os.getenv("CONDA_PREFIX")
	if conda_prefix:
		candidate = Path(conda_prefix) / "bin" / "python"
		if candidate.exists():
			python_executable = str(candidate)

	return StdioServerParameters(
		command=python_executable,
		args=[mcp_server.__file__],
		env=os.environ.copy(),
		cwd=os.getcwd(),
	)


def _release_model_resources() -> None:
	"""Best-effort memory cleanup between model loads to reduce VRAM pressure."""
	gc.collect()
	try:
		import torch  # type: ignore

		if torch.cuda.is_available():
			torch.cuda.empty_cache()
			torch.cuda.ipc_collect()
	except Exception:
		# Ignore cleanup failures when torch/CUDA is unavailable.
		pass


def run_benchmarks(config: dict[str, Any], only_agent: str | None, only_benchmark: str | None) -> dict[str, Any]:
	started_at = _now_utc()
	server_params = build_server_params()
	mcp_client = None

	try:
		mcp_client = MCPClient(server_params, structured_output=False)
		tools = mcp_client.get_tools()

		run_results: list[dict[str, Any]] = []

		for agent_cfg in config["agents"]:
			agent_name = agent_cfg.get("name")
			if only_agent and agent_name != only_agent:
				continue

			model_id = agent_cfg.get("model_id")
			if not model_id:
				raise ValueError(f"Agent {agent_name} missing model_id")

			model_kwargs = agent_cfg.get("model_kwargs", {}) or {}

			# Ensure previous model memory is reclaimed before loading a new model.
			_release_model_resources()

			model = None
			agent = None
			try:
				model = TransformersModel(model_id=model_id, **model_kwargs)

				agent_kwargs: dict[str, Any] = {
					"tools": tools,
					"model": model,
				}
				# Backward/forward compatibility: only pass fields supported by installed smolagents.
				if "structured_output" in inspect.signature(ToolCallingAgent.__init__).parameters:
					agent_kwargs["structured_output"] = bool(agent_cfg.get("structured_output", False))

				agent = ToolCallingAgent(**agent_kwargs)

				for benchmark in config["benchmarks"]:
					benchmark_id = benchmark.get("id")
					if only_benchmark and benchmark_id != only_benchmark:
						continue

					runs = int(benchmark.get("runs", 1))
					prompt_template = benchmark.get("prompt_template")
					if not prompt_template:
						raise ValueError(f"Benchmark {benchmark_id} missing prompt_template")

					for run_idx in range(runs):
						runtime_inputs = build_runtime_inputs(benchmark.get("input_source", {}))
						prompt = prompt_template.format(**runtime_inputs)

						started = time.perf_counter()
						agent_error = None
						agent_output: Any = None

						try:
							agent_output = agent.run(prompt)
						except Exception as exc:  # pragma: no cover - runtime safeguard
							agent_error = str(exc)

						duration_sec = time.perf_counter() - started

						if agent_error is None:
							try:
								validation_result = validate_result(benchmark, runtime_inputs, agent_output)
							except Exception as exc:
								validation_result = {
									"success": False,
									"error": f"Validation failed: {exc}",
								}
						else:
							validation_result = {
								"success": False,
								"error": f"Agent execution failed: {agent_error}",
							}

						run_results.append(
							{
								"agent": agent_name,
								"model_id": model_id,
								"benchmark_id": benchmark_id,
								"run_index": run_idx,
								"runtime_inputs": runtime_inputs,
								"prompt": prompt,
								"duration_sec": duration_sec,
								"agent_output": agent_output,
								"validation": validation_result,
							}
						)
			finally:
				# Drop strong refs and force memory cleanup before the next model loads.
				del agent
				del model
				_release_model_resources()

		summary = summarize_results(run_results)
		return {
			"started_at": started_at,
			"finished_at": _now_utc(),
			"sqlite_path": str(SQLITE_PATH),
			"summary": summary,
			"results": run_results,
		}
	finally:
		if mcp_client is not None:
			mcp_client.disconnect()


def summarize_results(run_results: list[dict[str, Any]]) -> dict[str, Any]:
	if not run_results:
		return {
			"total_runs": 0,
			"successful_runs": 0,
			"success_rate": 0.0,
			"average_duration_sec": 0.0,
			"by_agent": {},
			"by_benchmark": {},
		}

	total_runs = len(run_results)
	successful = sum(1 for r in run_results if bool(r.get("validation", {}).get("success")))
	avg_duration = sum(float(r.get("duration_sec", 0.0)) for r in run_results) / total_runs

	by_agent: dict[str, dict[str, Any]] = {}
	by_benchmark: dict[str, dict[str, Any]] = {}

	for result in run_results:
		agent = result["agent"]
		benchmark_id = result["benchmark_id"]
		success = bool(result.get("validation", {}).get("success"))
		duration = float(result.get("duration_sec", 0.0))

		if agent not in by_agent:
			by_agent[agent] = {"runs": 0, "successes": 0, "avg_duration_sec": 0.0}
		by_agent[agent]["runs"] += 1
		by_agent[agent]["successes"] += int(success)
		by_agent[agent]["avg_duration_sec"] += duration

		if benchmark_id not in by_benchmark:
			by_benchmark[benchmark_id] = {"runs": 0, "successes": 0, "avg_duration_sec": 0.0}
		by_benchmark[benchmark_id]["runs"] += 1
		by_benchmark[benchmark_id]["successes"] += int(success)
		by_benchmark[benchmark_id]["avg_duration_sec"] += duration

	for stats in by_agent.values():
		stats["avg_duration_sec"] /= stats["runs"]
		stats["success_rate"] = stats["successes"] / stats["runs"]

	for stats in by_benchmark.values():
		stats["avg_duration_sec"] /= stats["runs"]
		stats["success_rate"] = stats["successes"] / stats["runs"]

	return {
		"total_runs": total_runs,
		"successful_runs": successful,
		"success_rate": successful / total_runs,
		"average_duration_sec": avg_duration,
		"by_agent": by_agent,
		"by_benchmark": by_benchmark,
	}


def _merge_with_existing_results(
	new_results: dict[str, Any],
	aggregate_path: Path,
) -> dict[str, Any]:
	"""Merge newly produced benchmark results into an existing aggregate file."""
	if not aggregate_path.exists():
		return new_results

	with aggregate_path.open("r", encoding="utf-8") as f:
		existing = json.load(f)

	existing_runs = existing.get("results", []) if isinstance(existing, dict) else []
	new_runs = new_results.get("results", [])
	merged_runs = [*existing_runs, *new_runs]

	started_at = (
		existing.get("started_at")
		if isinstance(existing, dict) and existing.get("started_at")
		else new_results.get("started_at")
	)
	sqlite_paths = []
	if isinstance(existing, dict) and existing.get("sqlite_path"):
		sqlite_paths.append(existing["sqlite_path"])
	if new_results.get("sqlite_path"):
		sqlite_paths.append(new_results["sqlite_path"])
	sqlite_paths = sorted(set(sqlite_paths))

	return {
		"started_at": started_at,
		"finished_at": _now_utc(),
		"sqlite_path": new_results.get("sqlite_path"),
		"sqlite_paths": sqlite_paths,
		"summary": summarize_results(merged_runs),
		"results": merged_runs,
	}


def run_benchmarks_isolated_by_agent(
	config: dict[str, Any],
	config_path: Path,
	only_agent: str | None,
	only_benchmark: str | None,
	anomalies_root: Path | None,
	benchmark_catalogs: list[Path],
) -> dict[str, Any]:
	"""Run each agent in a fresh subprocess so GPU memory is fully released between models."""
	started_at = _now_utc()
	run_results: list[dict[str, Any]] = []

	for agent_cfg in config["agents"]:
		agent_name = agent_cfg.get("name")
		if only_agent and agent_name != only_agent:
			continue

		safe_agent_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(agent_name or "agent"))
		with tempfile.NamedTemporaryFile(prefix=f"bench_{safe_agent_name}_", suffix=".json", delete=False) as tmp:
			tmp_path = Path(tmp.name)

		cmd = [
			sys.executable,
			str(Path(__file__).resolve()),
			"--config",
			str(config_path),
			"--output",
			str(tmp_path),
			"--agent",
			str(agent_name),
			"--no-isolate-agents",
		]
		if only_benchmark:
			cmd.extend(["--benchmark", only_benchmark])
		if anomalies_root is not None:
			cmd.extend(["--anomalies-root", str(anomalies_root)])
		for catalog in benchmark_catalogs:
			cmd.extend(["--benchmark-catalog", str(catalog)])

		proc = subprocess.run(cmd)
		if proc.returncode != 0:
			raise RuntimeError(
				f"Isolated benchmark subprocess failed for agent '{agent_name}' (exit {proc.returncode})."
			)

		with tmp_path.open("r", encoding="utf-8") as f:
			agent_result = json.load(f)
		run_results.extend(agent_result.get("results", []))

		try:
			tmp_path.unlink()
		except Exception:
			pass

	return {
		"started_at": started_at,
		"finished_at": _now_utc(),
		"sqlite_path": str(SQLITE_PATH),
		"summary": summarize_results(run_results),
		"results": run_results,
	}


def write_csv_results(results: dict[str, Any], csv_path: Path) -> None:
	rows = results.get("results", []) or []
	fieldnames = [
		"agent",
		"model_id",
		"benchmark_id",
		"run_index",
		"duration_sec",
		"success",
		"error",
		"input_mmsi",
		"expected_mmsi",
		"expected_latitude",
		"expected_longitude",
		"expected_timestamp",
		"predicted_mmsi",
		"predicted_latitude",
		"predicted_longitude",
		"predicted_timestamp",
		"latitude_error",
		"longitude_error",
		"latitude_tolerance",
		"longitude_tolerance",
		"timestamp_match",
	]

	csv_path.parent.mkdir(parents=True, exist_ok=True)
	with csv_path.open("w", encoding="utf-8", newline="") as f:
		writer = csv.DictWriter(f, fieldnames=fieldnames)
		writer.writeheader()

		for result in rows:
			validation = result.get("validation", {}) or {}
			expected = validation.get("expected", {}) or {}
			predicted = validation.get("predicted", {}) or {}
			metrics = validation.get("metrics", {}) or {}
			runtime_inputs = result.get("runtime_inputs", {}) or {}

			writer.writerow(
				{
					"agent": result.get("agent"),
					"model_id": result.get("model_id"),
					"benchmark_id": result.get("benchmark_id"),
					"run_index": result.get("run_index"),
					"duration_sec": result.get("duration_sec"),
					"success": validation.get("success"),
					"error": validation.get("error"),
					"input_mmsi": runtime_inputs.get("mmsi"),
					"expected_mmsi": expected.get("mmsi"),
					"expected_latitude": expected.get("latitude"),
					"expected_longitude": expected.get("longitude"),
					"expected_timestamp": expected.get("timestamp"),
					"predicted_mmsi": predicted.get("mmsi"),
					"predicted_latitude": predicted.get("latitude"),
					"predicted_longitude": predicted.get("longitude"),
					"predicted_timestamp": predicted.get("timestamp"),
					"latitude_error": metrics.get("latitude_error"),
					"longitude_error": metrics.get("longitude_error"),
					"latitude_tolerance": metrics.get("latitude_tolerance"),
					"longitude_tolerance": metrics.get("longitude_tolerance"),
					"timestamp_match": metrics.get("timestamp_match"),
				}
			)


def print_human_summary(summary: dict[str, Any]) -> None:
	print("=" * 80)
	print("Benchmark Summary")
	print("=" * 80)
	print(f"Total runs: {summary['total_runs']}")
	print(f"Successful runs: {summary['successful_runs']}")
	print(f"Success rate: {summary['success_rate']:.2%}")
	print(f"Average duration: {summary['average_duration_sec']:.2f}s")

	print("\nPer-agent:")
	for agent, stats in summary["by_agent"].items():
		print(
			f"  - {agent}: runs={stats['runs']}, "
			f"success_rate={stats['success_rate']:.2%}, avg_duration={stats['avg_duration_sec']:.2f}s"
		)

	print("\nPer-benchmark:")
	for benchmark_id, stats in summary["by_benchmark"].items():
		print(
			f"  - {benchmark_id}: runs={stats['runs']}, "
			f"success_rate={stats['success_rate']:.2%}, avg_duration={stats['avg_duration_sec']:.2f}s"
		)


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Benchmark MCP tool-calling agents")
	parser.add_argument(
		"--config",
		type=Path,
		default=DEFAULT_CONFIG_PATH,
		help="Path to benchmark YAML config",
	)
	parser.add_argument(
		"--output",
		type=Path,
		default=None,
		help="Path to write benchmark JSON results (default: benchmarking/results/<timestamp>/benchmark_results.json)",
	)
	parser.add_argument(
		"--merge-into",
		type=Path,
		default=None,
		help="Optional aggregate JSON path; when provided, append new runs into that file and recompute summary.",
	)
	parser.add_argument(
		"--agent",
		type=str,
		default=None,
		help="Run only one agent by name",
	)
	parser.add_argument(
		"--benchmark",
		type=str,
		default=None,
		help="Run only one benchmark by id",
	)
	parser.add_argument(
		"--anomalies-root",
		type=Path,
		default=DEFAULT_ANOMALIES_ROOT,
		help="Root folder for anomaly scenario benchmark definition discovery.",
	)
	parser.add_argument(
		"--benchmark-catalog",
		type=Path,
		action="append",
		default=[],
		help="Additional benchmark definition file(s) to load. Repeat for multiple files.",
	)
	parser.add_argument(
		"--sqlite-path",
		type=Path,
		default=None,
		help="Override SQLite database path for benchmark and MCP tool server",
	)
	parser.add_argument(
		"--no-isolate-agents",
		action="store_true",
		help="Disable running each agent in a fresh subprocess",
	)
	return parser.parse_args()


def main() -> int:
	global SQLITE_PATH
	args = parse_args()
	if args.sqlite_path is not None:
		sqlite_override = args.sqlite_path.expanduser().resolve()
		os.environ[ACTINT_SQLITE_PATH_ENV] = str(sqlite_override)
		SQLITE_PATH = sqlite_override

	output_json_path = args.output or _default_output_json_path()
	output_csv_path = output_json_path.with_suffix(".csv")
	anomalies_root = args.anomalies_root.expanduser().resolve() if args.anomalies_root else None
	benchmark_catalogs = [p.expanduser().resolve() for p in args.benchmark_catalog]

	config = load_config(
		args.config,
		only_benchmark=args.benchmark,
		anomalies_root=anomalies_root,
		extra_catalog_files=benchmark_catalogs,
	)

	isolate_agents = not args.no_isolate_agents
	agent_count = len(config.get("agents", []))
	if isolate_agents and args.agent is None and agent_count > 1:
		results = run_benchmarks_isolated_by_agent(
			config,
			args.config,
			args.agent,
			args.benchmark,
			anomalies_root,
			benchmark_catalogs,
		)
	else:
		results = run_benchmarks(config, args.agent, args.benchmark)

	if args.merge_into is not None:
		aggregate_path = args.merge_into.expanduser().resolve()
		aggregate_path.parent.mkdir(parents=True, exist_ok=True)
		results = _merge_with_existing_results(results, aggregate_path)
		output_json_path = aggregate_path

	output_json_path.parent.mkdir(parents=True, exist_ok=True)
	with output_json_path.open("w", encoding="utf-8") as f:
		json.dump(results, f, indent=2, default=str)

	write_csv_results(results, output_csv_path)

	print_human_summary(results["summary"])
	print(f"\nSaved JSON results to: {output_json_path}")
	print(f"Saved CSV results to: {output_csv_path}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
