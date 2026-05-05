from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class BaseSimulation:
	"""Shared utilities for AIS anomaly simulation benchmark generators."""

	def __init__(self, script_file: Path, scenario_name: str, benchmark_id: str) -> None:
		self.script_file = script_file.resolve()
		self.scenario_name = scenario_name
		self.benchmark_id = benchmark_id

		self.benchmark_dir = self.script_file.parents[1]
		self.default_benchmark_config = self.benchmark_dir / "benchmarks.yaml"
		self.benchmark_runner = self.benchmark_dir / "benchmark_agents.py"
		self.anomalies_root = self.script_file.parents[4] / "data" / "db" / "anomalies"

	def resolve_default_source_db(self) -> Path:
		"""Find the baseline AIS database from common repo locations."""
		candidates = [
			self.script_file.parents[4] / "data" / "db" / "ais.db",
			self.script_file.parents[5] / "data" / "db" / "ais.db",
		]
		for candidate in candidates:
			if candidate.exists():
				return candidate
		return candidates[0]

	def default_output_db_path(self, db_name: str) -> Path:
		scenario_dir = self.anomalies_root / self.scenario_name
		return scenario_dir / db_name

	@staticmethod
	def parse_iso_timestamp(value: str | None) -> datetime:
		if not value:
			return datetime.now(timezone.utc).replace(tzinfo=None)

		value = value.strip()
		# Common sqlite text timestamps may use UTC suffix; normalize for strptime fallback.
		if value.endswith("Z"):
			value = value[:-1]
		fmts = [
			"%Y-%m-%dT%H:%M:%S.%f",
			"%Y-%m-%dT%H:%M:%S",
			"%Y-%m-%d %H:%M:%S.%f",
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

	@staticmethod
	def clone_database(source_db: Path, output_db: Path) -> None:
		if not source_db.exists():
			raise FileNotFoundError(f"Source database not found at {source_db}")

		output_db.parent.mkdir(parents=True, exist_ok=True)
		shutil.copy2(source_db, output_db)

	@staticmethod
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

	@staticmethod
	def get_source_vessels_by_mmsis(
		conn: sqlite3.Connection,
		target_mmsis: list[int],
		min_positions: int,
	) -> list[sqlite3.Row]:
		if not target_mmsis:
			return []

		placeholders = ",".join(["?"] * len(target_mmsis))
		query = f"""
			SELECT
				p.mmsi AS mmsi,
				COALESCE(MAX(p.vessel_name), MAX(v.vessel_name), 'UNKNOWN') AS vessel_name,
				COUNT(*) AS position_count,
				AVG(p.lat) AS center_lat,
				AVG(p.lon) AS center_lon
			FROM ais_positions p
			LEFT JOIN vessels v ON v.mmsi = p.mmsi
			WHERE p.mmsi IN ({placeholders})
			GROUP BY p.mmsi
			HAVING COUNT(*) >= ?
		"""
		rows = conn.execute(query, (*target_mmsis, min_positions)).fetchall()
		by_mmsi = {int(r["mmsi"]): r for r in rows}
		return [by_mmsi[m] for m in target_mmsis if m in by_mmsi]

	@staticmethod
	def remove_ship_data(conn: sqlite3.Connection, mmsi: int) -> int:
		row = conn.execute("SELECT COUNT(*) FROM ais_positions WHERE mmsi = ?", (mmsi,)).fetchone()
		removed_positions = int(row[0]) if row else 0
		conn.execute("DELETE FROM ais_positions WHERE mmsi = ?", (mmsi,))
		conn.execute("DELETE FROM vessels WHERE mmsi = ?", (mmsi,))
		return removed_positions

	@staticmethod
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

	@staticmethod
	def get_vessel_metadata(conn: sqlite3.Connection, source_mmsi: int) -> sqlite3.Row | None:
		return conn.execute("SELECT * FROM vessels WHERE mmsi = ?", (source_mmsi,)).fetchone()

	def get_dataset_time_bounds(self, conn: sqlite3.Connection) -> tuple[datetime, datetime]:
		row = conn.execute(
			"SELECT MIN(base_datetime) AS first_ts, MAX(base_datetime) AS last_ts FROM ais_positions"
		).fetchone()
		if row is None:
			raise RuntimeError("Failed to read AIS timestamp bounds from ais_positions")

		first_raw = row["first_ts"] if isinstance(row, sqlite3.Row) else row[0]
		last_raw = row["last_ts"] if isinstance(row, sqlite3.Row) else row[1]
		if not first_raw or not last_raw:
			raise RuntimeError("AIS dataset has no timestamps in ais_positions")

		first_ts = self.parse_iso_timestamp(str(first_raw))
		last_ts = self.parse_iso_timestamp(str(last_raw))
		return first_ts, last_ts

	@staticmethod
	def nm_offset_to_lat_lon(center_lat: float, center_lon: float, radius_nm: float, angle_rad: float) -> tuple[float, float]:
		dlat = (radius_nm * math.cos(angle_rad)) / 60.0
		cos_lat = max(math.cos(math.radians(center_lat)), 0.01)
		dlon = (radius_nm * math.sin(angle_rad)) / (60.0 * cos_lat)
		return center_lat + dlat, center_lon + dlon

	@staticmethod
	def sample_new_data_count(mean: float, std: float, rng: random.Random) -> int:
		std = max(0.0, std)
		if std == 0.0:
			return max(1, int(round(mean)))
		return max(1, int(round(rng.gauss(mean, std))))

	@staticmethod
	def validate_ships_to_replace(db_path: Path, min_source_positions: int, ships_to_replace: int) -> int:
		if ships_to_replace <= 0:
			raise ValueError("--ships-to-replace must be greater than 0")

		with sqlite3.connect(str(db_path)) as conn:
			row = conn.execute(
				"""
				SELECT COUNT(*)
				FROM (
					SELECT p.mmsi
					FROM ais_positions p
					GROUP BY p.mmsi
					HAVING COUNT(*) >= ?
				) eligible
				""",
				(min_source_positions,),
			).fetchone()

		eligible_count = int(row[0]) if row else 0
		if eligible_count <= 0:
			raise RuntimeError(
				f"No source vessels found with at least {min_source_positions} positions."
			)
		if ships_to_replace > eligible_count:
			raise RuntimeError(
				f"Requested --ships-to-replace={ships_to_replace}, but only {eligible_count} "
				f"eligible vessels exist with at least {min_source_positions} positions."
			)

		return ships_to_replace

	@staticmethod
	def resolve_replacement_mmsis(
		db_path: Path,
		min_source_positions: int,
		ships_to_replace: int,
		replace_mmsis: list[int] | None,
	) -> list[int] | None:
		if replace_mmsis:
			normalized: list[int] = []
			seen: set[int] = set()
			for value in replace_mmsis:
				m = int(value)
				if m <= 0:
					raise ValueError("--replace-mmsis values must be positive MMSI integers")
				if m in seen:
					continue
				seen.add(m)
				normalized.append(m)

			with sqlite3.connect(str(db_path)) as conn:
				placeholders = ",".join(["?"] * len(normalized))
				query = f"""
					SELECT mmsi, COUNT(*) AS n
					FROM ais_positions
					WHERE mmsi IN ({placeholders})
					GROUP BY mmsi
				"""
				rows = conn.execute(query, tuple(normalized)).fetchall()

			counts = {int(r[0]): int(r[1]) for r in rows}
			invalid = [m for m in normalized if counts.get(m, 0) < min_source_positions]
			if invalid:
				raise RuntimeError(
					"Requested --replace-mmsis not eligible (missing or below min-source-positions "
					f"{min_source_positions}): {invalid}"
				)

			return normalized

		return None

	@staticmethod
	def to_sqlite_timestamp(dt: datetime) -> str:
		"""Serialize datetime in a sqlite/pandas-friendly timestamp text format."""
		if dt.tzinfo is not None:
			dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
		return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")

	@staticmethod
	def write_manifest(manifest_path: Path, source_db: Path, output_db: Path, anomalies: list[Any]) -> None:
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

	def write_detection_benchmark_config(
		self,
		config_path: Path,
		expected_mmsis: list[int],
		description: str,
		prompt_template: str,
		expected_field_name: str,
		validation_method: str,
	) -> None:
		benchmark_config = {
			"benchmarks": [
				{
					"id": self.benchmark_id,
					"description": description,
					"runs": 1,
					"prompt_template": prompt_template,
					"input_source": {
						"type": "fixed",
						"values": {
							expected_field_name: expected_mmsis,
						},
					},
					"validation": {
						"method": validation_method,
						"minimum_detected": len(expected_mmsis),
						"require_all_expected": True,
					},
				}
			],
		}

		config_path.parent.mkdir(parents=True, exist_ok=True)
		with config_path.open("w", encoding="utf-8") as f:
			json.dump(benchmark_config, f, indent=2)

	def run_benchmark(
		self,
		benchmark_config: Path,
		sqlite_path: Path,
		output_json: Path,
		aggregate_results_file: Path | None,
		agent: str | None,
	) -> None:
		cmd = [
			sys.executable,
			str(self.benchmark_runner),
			"--config",
			str(self.default_benchmark_config),
			"--benchmark",
			self.benchmark_id,
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

	def add_common_args(
		self,
		parser: argparse.ArgumentParser,
		default_output_db: Path,
		manifest_help: str,
	) -> None:
		parser.add_argument(
			"--source-db",
			type=Path,
			default=self.resolve_default_source_db(),
			help="Path to the baseline AIS SQLite database to clone before injecting anomalies.",
		)
		parser.add_argument(
			"--output-db",
			type=Path,
			default=default_output_db,
			help="Path for the generated anomaly SQLite database.",
		)
		parser.add_argument(
			"--ships-to-replace",
			type=int,
			default=5,
			help=(
				"Number of ships to replace with synthetic anomaly records. "
				"Ignored when --replace-mmsis is provided."
			),
		)
		parser.add_argument(
			"--replace-mmsis",
			type=int,
			nargs="+",
			default=None,
			help=(
				"Optional explicit MMSI list to replace. "
				"When set, these MMSIs override --ships-to-replace."
			),
		)
		parser.add_argument(
			"--mean-new-data-count",
			type=float,
			default=400,
			help="Mean number of synthetic AIS position records generated per replaced ship.",
		)
		parser.add_argument(
			"--std-new-data-count",
			type=float,
			default=10.0,
			help="Standard deviation for synthetic AIS position record count per replaced ship.",
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
			help=manifest_help,
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

	def finalize_outputs_and_run(
		self,
		args: argparse.Namespace,
		source_db: Path,
		output_db: Path,
		anomalies: list[Any],
		write_benchmark_config: Any,
	) -> None:
		manifest_output = (
			args.manifest_output.expanduser().resolve()
			if args.manifest_output
			else output_db.parent / "manifest.json"
		)
		self.write_manifest(manifest_output, source_db, output_db, anomalies)

		benchmark_cfg_output = (
			args.benchmark_config_output.expanduser().resolve()
			if args.benchmark_config_output
			else output_db.parent / "benchmark_definitions.json"
		)
		write_benchmark_config(benchmark_cfg_output, [int(a.mmsi) for a in anomalies])

		print(f"Cloned DB: {output_db}")
		print(f"Injected anomalies: {len(anomalies)}")
		print(f"Manifest: {manifest_output}")
		print(f"Benchmark config: {benchmark_cfg_output}")
		print("Injected anomaly MMSIs:", ", ".join(str(a.mmsi) for a in anomalies))

		if args.run_benchmark:
			benchmark_output = (
				args.benchmark_output.expanduser().resolve()
				if args.benchmark_output
				else self.benchmark_dir / "results" / f"{self.scenario_name}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
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
			self.run_benchmark(
				benchmark_config=benchmark_cfg_output,
				sqlite_path=output_db,
				output_json=benchmark_output,
				aggregate_results_file=aggregate_results_file,
				agent=args.agent,
			)
			if aggregate_results_file is not None:
				print(f"Merged results file: {aggregate_results_file}")
			print("Benchmark run complete")
