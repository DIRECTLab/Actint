"""Speeding anomaly simulation for AIS benchmarking.

Pipeline:
1. Clone a baseline SQLite AIS database.
2. Select existing ships, remove original records, and inject synthetic tracks with sudden speed spikes.
3. Emit a benchmark definition file for speeding anomaly detection.
4. Optionally run the benchmark harness against the generated anomaly database.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


BENCHMARK_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BENCHMARK_CONFIG = BENCHMARK_DIR / "benchmarks.yaml"
BENCHMARK_RUNNER = BENCHMARK_DIR / "benchmark_agents.py"
ANOMALIES_ROOT = Path(__file__).resolve().parents[4] / "data" / "db" / "anomalies"


@dataclass
class InjectedSpeedingAnomaly:
	anomaly_id: str
	mmsi: int
	vessel_name: str
	source_mmsi: int
	source_vessel_name: str
	center_lat: float
	center_lon: float
	start_time: str
	end_time: str
	point_count: int
	spike_indices: list[int]
	spike_speeds: list[float]


def resolve_default_source_db() -> Path:
	"""Find the baseline AIS database from common repo locations."""
	candidates = [
		Path(__file__).resolve().parents[4] / "data" / "db" / "ais.db",
		Path(__file__).resolve().parents[5] / "data" / "db" / "ais.db",
	]
	for candidate in candidates:
		if candidate.exists():
			return candidate
	return candidates[0]


def default_output_db_path() -> Path:
	stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
	scenario_dir = ANOMALIES_ROOT / "speeding" / stamp
	return scenario_dir / "ais_speeding.db"


def parse_iso_timestamp(value: str | None) -> datetime:
	if not value:
		return datetime.now(timezone.utc).replace(tzinfo=None)

	value = value.strip()
	fmts = [
		"%Y-%m-%dT%H:%M:%S.%f",
		"%Y-%m-%dT%H:%M:%S",
		"%Y-%m-%d %H:%M:%S",
	]
	for fmt in fmts:
		try:
			return datetime.strptime(value, fmt)
		except ValueError:
			continue

	normalized = value.replace("Z", "+00:00")
	try:
		return datetime.fromisoformat(normalized).replace(tzinfo=None)
	except ValueError:
		return datetime.now(timezone.utc).replace(tzinfo=None)


def clone_database(source_db: Path, output_db: Path) -> None:
	if not source_db.exists():
		raise FileNotFoundError(f"Source database not found at {source_db}")

	output_db.parent.mkdir(parents=True, exist_ok=True)
	shutil.copy2(source_db, output_db)


def get_source_vessels(conn: sqlite3.Connection, min_positions: int, limit: int) -> list[sqlite3.Row]:
	query = """
		SELECT
			p.mmsi AS mmsi,
			COALESCE(MAX(p.vessel_name), MAX(v.vessel_name), 'UNKNOWN') AS vessel_name,
			COUNT(*) AS position_count,
			AVG(p.lat) AS center_lat,
			AVG(p.lon) AS center_lon
		FROM ais_positions p
		LEFT JOIN vessels v ON v.mmsi = p.mmsi
		GROUP BY p.mmsi
		HAVING COUNT(*) >= ?
		ORDER BY position_count DESC
		LIMIT ?
	"""
	return conn.execute(query, (min_positions, limit)).fetchall()


def remove_ship_data(conn: sqlite3.Connection, mmsi: int) -> int:
	"""Remove existing vessel metadata and position history for one MMSI."""
	row = conn.execute("SELECT COUNT(*) FROM ais_positions WHERE mmsi = ?", (mmsi,)).fetchone()
	removed_positions = int(row[0]) if row else 0
	conn.execute("DELETE FROM ais_positions WHERE mmsi = ?", (mmsi,))
	conn.execute("DELETE FROM vessels WHERE mmsi = ?", (mmsi,))
	return removed_positions


def create_speeding_table(conn: sqlite3.Connection) -> None:
	conn.execute(
		"""
		CREATE TABLE IF NOT EXISTS speeding_anomalies (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			anomaly_id TEXT UNIQUE NOT NULL,
			mmsi INTEGER UNIQUE NOT NULL,
			vessel_name TEXT,
			source_mmsi INTEGER,
			source_vessel_name TEXT,
			center_lat REAL,
			center_lon REAL,
			start_time TEXT,
			end_time TEXT,
			point_count INTEGER,
			spike_indices TEXT,
			spike_speeds TEXT,
			created_at TEXT DEFAULT CURRENT_TIMESTAMP
		)
		"""
	)


def get_latest_source_position(conn: sqlite3.Connection, source_mmsi: int) -> sqlite3.Row | None:
	return conn.execute(
		"""
		SELECT
			mmsi,
			vessel_name,
			imo,
			call_sign,
			vessel_type,
			status,
			length,
			width,
			draft,
			cargo,
			transceiver_class,
			base_datetime
		FROM ais_positions
		WHERE mmsi = ?
		ORDER BY base_datetime DESC
		LIMIT 1
		""",
		(source_mmsi,),
	).fetchone()


def get_vessel_metadata(conn: sqlite3.Connection, source_mmsi: int) -> sqlite3.Row | None:
	return conn.execute("SELECT * FROM vessels WHERE mmsi = ?", (source_mmsi,)).fetchone()


def nm_offset_to_lat_lon(center_lat: float, center_lon: float, radius_nm: float, angle_rad: float) -> tuple[float, float]:
	dlat = (radius_nm * math.cos(angle_rad)) / 60.0
	cos_lat = max(math.cos(math.radians(center_lat)), 0.01)
	dlon = (radius_nm * math.sin(angle_rad)) / (60.0 * cos_lat)
	return center_lat + dlat, center_lon + dlon


def _choose_spike_indices(point_count: int, spike_count: int, rng: random.Random) -> list[int]:
	if point_count < 4:
		return [max(0, point_count - 1)]

	start_idx = max(1, point_count // 5)
	end_idx = max(start_idx + 1, point_count - 2)
	candidates = list(range(start_idx, end_idx))
	spike_count = max(1, min(spike_count, len(candidates)))
	return sorted(rng.sample(candidates, k=spike_count))


def inject_speeding_anomalies(
	db_path: Path,
	num_anomalies: int,
	point_count: int,
	radius_nm: float,
	interval_minutes: int,
	normal_max_sog_knots: float,
	spike_min_sog_knots: float,
	spike_max_sog_knots: float,
	spike_count: int,
	min_source_positions: int,
	rng_seed: int,
) -> list[InjectedSpeedingAnomaly]:
	conn = sqlite3.connect(str(db_path))
	conn.row_factory = sqlite3.Row

	try:
		create_speeding_table(conn)

		source_candidates = get_source_vessels(
			conn,
			min_positions=min_source_positions,
			limit=max(num_anomalies * 3, num_anomalies),
		)
		if len(source_candidates) < num_anomalies:
			raise RuntimeError(
				f"Not enough source vessels with at least {min_source_positions} positions. "
				f"Needed {num_anomalies}, found {len(source_candidates)}."
			)

		rng = random.Random(rng_seed)
		anomalies: list[InjectedSpeedingAnomaly] = []

		for i in range(num_anomalies):
			source = source_candidates[i]
			source_mmsi = int(source["mmsi"])
			source_name = str(source["vessel_name"])

			latest_position = get_latest_source_position(conn, source_mmsi)
			vessel_meta = get_vessel_metadata(conn, source_mmsi)

			center_lat = float(source["center_lat"])
			center_lon = float(source["center_lon"])
			if latest_position is not None:
				latest_time = parse_iso_timestamp(latest_position["base_datetime"])
			else:
				latest_time = datetime.utcnow()

			remove_ship_data(conn, source_mmsi)

			start_time = latest_time + timedelta(hours=1)
			anomaly_mmsi = source_mmsi
			vessel_name = source_name
			anomaly_id = f"SPEED-{source_mmsi}"

			conn.execute(
				"""
				INSERT OR REPLACE INTO vessels (
					mmsi, vessel_name, call_sign, domain, class, type,
					pennant_number, callsign_military, world_port_index_number,
					home_base, parent_command, fleet, fleet_original,
					first_seen, last_seen
				) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
				""",
				(
					anomaly_mmsi,
					vessel_name,
					(f"SS{anomaly_mmsi % 100000:05d}"),
					vessel_meta["domain"] if vessel_meta else None,
					vessel_meta["class"] if vessel_meta else "SIMULATED",
					vessel_meta["type"] if vessel_meta else "SIM",
					vessel_meta["pennant_number"] if vessel_meta else None,
					vessel_meta["callsign_military"] if vessel_meta else None,
					vessel_meta["world_port_index_number"] if vessel_meta else None,
					vessel_meta["home_base"] if vessel_meta else "SIM_BASE",
					vessel_meta["parent_command"] if vessel_meta else "SIM_COMMAND",
					vessel_meta["fleet"] if vessel_meta else "SIM_FLEET",
					vessel_meta["fleet_original"] if vessel_meta else "SIM_FLEET",
					start_time.strftime("%Y-%m-%dT%H:%M:%S"),
					(start_time + timedelta(minutes=(point_count - 1) * interval_minutes)).strftime(
						"%Y-%m-%dT%H:%M:%S"
					),
				),
			)

			spike_indices = _choose_spike_indices(point_count, spike_count, rng)
			spike_speeds: list[float] = []

			end_time = start_time
			for step in range(point_count):
				ts = start_time + timedelta(minutes=step * interval_minutes)
				end_time = ts

				angle = rng.uniform(0.0, 2.0 * math.pi)
				radial_nm = rng.uniform(0.0, radius_nm)
				lat, lon = nm_offset_to_lat_lon(center_lat, center_lon, radial_nm, angle)

				if step in spike_indices:
					sog = rng.uniform(spike_min_sog_knots, spike_max_sog_knots)
					spike_speeds.append(round(sog, 3))
				else:
					sog = rng.uniform(0.0, normal_max_sog_knots)
				cog = rng.uniform(0.0, 359.9)

				conn.execute(
					"""
					INSERT INTO ais_positions (
						mmsi, base_datetime, lat, lon, sog, cog, heading,
						vessel_name, imo, call_sign, vessel_type, status,
						length, width, draft, cargo, transceiver_class
					) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
					""",
					(
						anomaly_mmsi,
						ts.strftime("%Y-%m-%dT%H:%M:%S"),
						lat,
						lon,
						sog,
						cog,
						int(cog),
						vessel_name,
						latest_position["imo"] if latest_position else None,
						f"SS{anomaly_mmsi % 100000:05d}",
						latest_position["vessel_type"] if latest_position else None,
						latest_position["status"] if latest_position else 0,
						latest_position["length"] if latest_position else None,
						latest_position["width"] if latest_position else None,
						latest_position["draft"] if latest_position else None,
						latest_position["cargo"] if latest_position else None,
						latest_position["transceiver_class"] if latest_position else "A",
					),
				)

			conn.execute(
				"""
				INSERT OR REPLACE INTO speeding_anomalies (
					anomaly_id, mmsi, vessel_name, source_mmsi, source_vessel_name,
					center_lat, center_lon, start_time, end_time, point_count,
					spike_indices, spike_speeds
				) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
				""",
				(
					anomaly_id,
					anomaly_mmsi,
					vessel_name,
					source_mmsi,
					source_name,
					center_lat,
					center_lon,
					start_time.strftime("%Y-%m-%dT%H:%M:%S"),
					end_time.strftime("%Y-%m-%dT%H:%M:%S"),
					point_count,
					json.dumps(spike_indices),
					json.dumps(spike_speeds),
				),
			)

			anomalies.append(
				InjectedSpeedingAnomaly(
					anomaly_id=anomaly_id,
					mmsi=anomaly_mmsi,
					vessel_name=vessel_name,
					source_mmsi=source_mmsi,
					source_vessel_name=source_name,
					center_lat=center_lat,
					center_lon=center_lon,
					start_time=start_time.strftime("%Y-%m-%dT%H:%M:%S"),
					end_time=end_time.strftime("%Y-%m-%dT%H:%M:%S"),
					point_count=point_count,
					spike_indices=spike_indices,
					spike_speeds=spike_speeds,
				)
			)

		conn.commit()
		return anomalies
	finally:
		conn.close()


def write_speeding_benchmark_config(config_path: Path, expected_mmsis: list[int]) -> None:
	benchmark_config = {
		"benchmarks": [
			{
				"id": "speeding_detection_injected",
				"description": (
					"Detect synthetic speeding anomalies injected into the AIS database. "
					"Success requires detecting all injected speeding anomaly MMSIs; additional MMSIs are allowed."
				),
				"runs": 1,
				"prompt_template": (
					"Use available MCP tools to identify ships with sudden speed increases in the AIS database.\\n"
					"A speeding anomaly is a vessel that has one or more abrupt spikes in Speed Over Ground.\\n"
					"You should use SQL via query_database to compute likely speeding ships.\\n\\n"
					"Return ONLY valid JSON with this exact shape:\\n"
					"{\\\"speeding_mmsi\\\": [<int>, <int>, ...]}\\n\\n"
					"Expected injected anomalies in DB: {expected_count}"
				),
				"input_source": {
					"type": "fixed",
					"values": {
						"expected_loitering_mmsis": expected_mmsis,
						"expected_count": len(expected_mmsis),
					},
				},
				"validation": {
					"method": "loitering_detection",
					"minimum_detected": len(expected_mmsis),
					"require_all_expected": True,
				},
			}
		],
	}

	config_path.parent.mkdir(parents=True, exist_ok=True)
	with config_path.open("w", encoding="utf-8") as f:
		json.dump(benchmark_config, f, indent=2)


def write_manifest(manifest_path: Path, source_db: Path, output_db: Path, anomalies: list[InjectedSpeedingAnomaly]) -> None:
	manifest_path.parent.mkdir(parents=True, exist_ok=True)
	payload = {
		"created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
		"source_db": str(source_db),
		"output_db": str(output_db),
		"anomaly_count": len(anomalies),
		"anomalies": [asdict(a) for a in anomalies],
	}
	with manifest_path.open("w", encoding="utf-8") as f:
		json.dump(payload, f, indent=2)


def run_benchmark(
	main_config: Path,
	benchmark_config: Path,
	sqlite_path: Path,
	output_json: Path,
	aggregate_results_file: Path | None,
	agent: str | None,
) -> None:
	cmd = [
		sys.executable,
		str(BENCHMARK_RUNNER),
		"--config",
		str(main_config),
		"--benchmark",
		"speeding_detection_injected",
		"--sqlite-path",
		str(sqlite_path),
		"--benchmark-catalog",
		str(benchmark_config),
		"--output",
		str(output_json),
	]
	if aggregate_results_file is not None:
		cmd.extend(["--merge-into", str(aggregate_results_file)])
	if agent:
		cmd.extend(["--agent", agent])

	subprocess.run(cmd, check=True)


def build_arg_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="Create and test speeding anomaly AIS databases")
	parser.add_argument(
		"--source-db",
		type=Path,
		default=resolve_default_source_db(),
		help="Path to the baseline AIS SQLite database to clone before injecting anomalies.",
	)
	parser.add_argument(
		"--output-db",
		type=Path,
		default=default_output_db_path(),
		help="Path for the generated anomaly SQLite database.",
	)
	parser.add_argument(
		"--num-anomalies",
		type=int,
		default=5,
		help="Number of existing ships to replace with synthetic speeding tracks.",
	)
	parser.add_argument(
		"--points-per-anomaly",
		type=int,
		default=50,
		help="Number of AIS position points generated per injected speeding vessel.",
	)
	parser.add_argument(
		"--radius-nm",
		type=float,
		default=0.4,
		help="Maximum movement radius around anomaly center in nautical miles.",
	)
	parser.add_argument(
		"--interval-minutes",
		type=int,
		default=15,
		help="Time gap in minutes between successive synthetic AIS points.",
	)
	parser.add_argument(
		"--normal-max-sog-knots",
		type=float,
		default=10.0,
		help="Upper bound for normal non-anomalous speeds in knots.",
	)
	parser.add_argument(
		"--spike-min-sog-knots",
		type=float,
		default=30.0,
		help="Lower bound for sudden speed spike values in knots.",
	)
	parser.add_argument(
		"--spike-max-sog-knots",
		type=float,
		default=45.0,
		help="Upper bound for sudden speed spike values in knots.",
	)
	parser.add_argument(
		"--spike-count",
		type=int,
		default=2,
		help="Number of abrupt speed spikes injected per vessel track.",
	)
	parser.add_argument(
		"--min-source-positions",
		type=int,
		default=5,
		help="Minimum historical AIS points required for selecting a real vessel as anomaly template.",
	)
	parser.add_argument(
		"--seed",
		type=int,
		default=1337,
		help="Random seed for reproducible anomaly generation.",
	)

	parser.add_argument(
		"--benchmark-config-output",
		type=Path,
		default=None,
		help="Optional path for generated benchmark definition file; defaults in the scenario folder.",
	)
	parser.add_argument(
		"--manifest-output",
		type=Path,
		default=None,
		help="Optional path for anomaly manifest JSON; defaults in the scenario folder.",
	)
	parser.add_argument(
		"--run-benchmark",
		action="store_true",
		help="Run benchmark_agents.py immediately after anomaly injection.",
	)
	parser.add_argument(
		"--benchmark-output",
		type=Path,
		default=None,
		help="Optional JSON output path for benchmark results.",
	)
	parser.add_argument(
		"--aggregate-results-file",
		type=Path,
		default=None,
		help="Optional shared JSON file to merge this run into for multi-scenario aggregate reporting.",
	)
	parser.add_argument(
		"--agent",
		type=str,
		default=None,
		help="Optional benchmark agent name; if omitted, all configured agents are run.",
	)
	return parser


def main() -> int:
	args = build_arg_parser().parse_args()

	source_db = args.source_db.expanduser().resolve()
	output_db = args.output_db.expanduser().resolve()

	clone_database(source_db, output_db)
	anomalies = inject_speeding_anomalies(
		db_path=output_db,
		num_anomalies=args.num_anomalies,
		point_count=args.points_per_anomaly,
		radius_nm=args.radius_nm,
		interval_minutes=args.interval_minutes,
		normal_max_sog_knots=args.normal_max_sog_knots,
		spike_min_sog_knots=args.spike_min_sog_knots,
		spike_max_sog_knots=args.spike_max_sog_knots,
		spike_count=args.spike_count,
		min_source_positions=args.min_source_positions,
		rng_seed=args.seed,
	)

	manifest_output = (
		args.manifest_output.expanduser().resolve()
		if args.manifest_output
		else output_db.parent / "manifest.json"
	)
	write_manifest(manifest_output, source_db, output_db, anomalies)

	benchmark_cfg_output = (
		args.benchmark_config_output.expanduser().resolve()
		if args.benchmark_config_output
		else output_db.parent / "benchmark_definitions.json"
	)
	write_speeding_benchmark_config(
		benchmark_cfg_output,
		expected_mmsis=[a.mmsi for a in anomalies],
	)

	print(f"Cloned DB: {output_db}")
	print(f"Injected anomalies: {len(anomalies)}")
	print(f"Manifest: {manifest_output}")
	print(f"Benchmark config: {benchmark_cfg_output}")
	print("Injected anomaly MMSIs:", ", ".join(str(a.mmsi) for a in anomalies))

	if args.run_benchmark:
		benchmark_output = (
			args.benchmark_output.expanduser().resolve()
			if args.benchmark_output
			else BENCHMARK_DIR / "results" / f"speeding_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
		)
		benchmark_output.parent.mkdir(parents=True, exist_ok=True)
		aggregate_results_file = (
			args.aggregate_results_file.expanduser().resolve()
			if args.aggregate_results_file
			else None
		)
		if aggregate_results_file is not None:
			aggregate_results_file.parent.mkdir(parents=True, exist_ok=True)

		print(f"Running benchmark with output: {benchmark_output}")
		run_benchmark(
			main_config=DEFAULT_BENCHMARK_CONFIG,
			benchmark_config=benchmark_cfg_output,
			sqlite_path=output_db,
			output_json=benchmark_output,
			aggregate_results_file=aggregate_results_file,
			agent=args.agent,
		)
		if aggregate_results_file is not None:
			print(f"Merged results file: {aggregate_results_file}")
		print("Benchmark run complete")

	return 0


if __name__ == "__main__":
	raise SystemExit(main())
