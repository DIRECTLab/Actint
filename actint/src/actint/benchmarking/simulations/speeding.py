"""Speeding anomaly simulation for AIS benchmarking."""

from __future__ import annotations

import argparse
import random
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np

try:
	from actint.benchmarking.simulations.base_simulation import BaseSimulation
except ModuleNotFoundError:
	from base_simulation import BaseSimulation


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


def _choose_spike_indices(point_count: int, spike_count: int, rng: random.Random) -> list[int]:
	if point_count < 4:
		return [max(0, point_count - 1)]

	start_idx = max(1, point_count // 5)
	end_idx = max(start_idx + 1, point_count - 2)
	candidates = list(range(start_idx, end_idx))
	spike_count = max(1, min(spike_count, len(candidates)))
	return sorted(rng.sample(candidates, k=spike_count))



class SpeedingSimulation(BaseSimulation):
	def __init__(self) -> None:
		super().__init__(Path(__file__), scenario_name="speeding", benchmark_id="speeding_detection_injected")

	def inject_anomalies(
		self,
		db_path: Path,
		ships_to_replace: int,
		mean_new_data_count: float,
		std_new_data_count: float,
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
			source_candidates = self.get_source_vessels(
				conn,
				min_positions=min_source_positions,
				limit=max(ships_to_replace * 3, ships_to_replace),
			)
			if len(source_candidates) < ships_to_replace:
				raise RuntimeError(
					f"Not enough source vessels with at least {min_source_positions} positions. "
					f"Needed {ships_to_replace}, found {len(source_candidates)}."
				)

			rng = random.Random(rng_seed)
			anomalies: list[InjectedSpeedingAnomaly] = []

			for i in range(ships_to_replace):
				point_count = self.sample_new_data_count(mean_new_data_count, std_new_data_count, rng)
				source = source_candidates[i]
				source_mmsi = int(source["mmsi"])
				source_name = str(source["vessel_name"])

				latest_position = self.get_latest_source_position(conn, source_mmsi)
				vessel_meta = self.get_vessel_metadata(conn, source_mmsi)

				center_lat = float(source["center_lat"])
				center_lon = float(source["center_lon"])
				if latest_position is not None:
					latest_time = self.parse_iso_timestamp(latest_position["base_datetime"])
				else:
					latest_time = datetime.utcnow()

				self.remove_ship_data(conn, source_mmsi)

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

					angle = rng.uniform(0.0, 2.0 * np.pi)
					radial_nm = rng.uniform(0.0, radius_nm)
					lat, lon = self.nm_offset_to_lat_lon(center_lat, center_lon, radial_nm, angle)

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

	def write_benchmark_config(self, config_path: Path, expected_mmsis: list[int]) -> None:
		description = (
			"Detect synthetic speeding anomalies injected into the AIS database. "
			"Success requires detecting all injected speeding anomaly MMSIs; additional MMSIs are allowed."
		)
		prompt_template = (
			"Use available MCP tools to identify ships with sudden speed increases in the AIS database.\\n"
			"A speeding anomaly is a vessel that has one or more abrupt spikes in Speed Over Ground.\\n"
			"You should use SQL via query_database to compute likely speeding ships.\\n\\n"
			"Return ONLY valid JSON with this exact shape:\\n"
			"{\\\"speeding_mmsi\\\": [<int>, <int>, ...]}"
		)
		self.write_detection_benchmark_config(
			config_path=config_path,
			expected_mmsis=expected_mmsis,
			description=description,
			prompt_template=prompt_template,
			expected_field_name="expected_speeding_mmsis",
			validation_method="speeding_detection",
		)

	def build_arg_parser(self) -> argparse.ArgumentParser:
		parser = argparse.ArgumentParser(description="Create and test speeding anomaly AIS databases")
		self.add_common_args(
			parser,
			default_output_db=self.default_output_db_path("ais_speeding.db"),
			manifest_help="Optional path for anomaly manifest JSON; defaults in the scenario folder.",
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
		return parser

	def run_from_args(self, args: argparse.Namespace) -> int:
		source_db = args.source_db.expanduser().resolve()
		output_db = args.output_db.expanduser().resolve()

		self.clone_database(source_db, output_db)
		ships_to_replace = self.validate_ships_to_replace(
			db_path=output_db,
			min_source_positions=args.min_source_positions,
			ships_to_replace=args.ships_to_replace,
		)
		anomalies = self.inject_anomalies(
			db_path=output_db,
			ships_to_replace=ships_to_replace,
			mean_new_data_count=args.mean_new_data_count,
			std_new_data_count=args.std_new_data_count,
			radius_nm=args.radius_nm,
			interval_minutes=args.interval_minutes,
			normal_max_sog_knots=args.normal_max_sog_knots,
			spike_min_sog_knots=args.spike_min_sog_knots,
			spike_max_sog_knots=args.spike_max_sog_knots,
			spike_count=args.spike_count,
			min_source_positions=args.min_source_positions,
			rng_seed=args.seed,
		)

		self.finalize_outputs_and_run(
			args=args,
			source_db=source_db,
			output_db=output_db,
			anomalies=anomalies,
			write_benchmark_config=self.write_benchmark_config,
		)
		return 0


def main() -> int:
	simulation = SpeedingSimulation()
	args = simulation.build_arg_parser().parse_args()
	return simulation.run_from_args(args)


if __name__ == "__main__":
	raise SystemExit(main())
