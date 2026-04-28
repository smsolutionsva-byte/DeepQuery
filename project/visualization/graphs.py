from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

matplotlib.use("Agg")


class GraphBuilder:
    DATE_PATTERNS = [
        re.compile(r"(?<!\d)(?P<y>\d{4})[-_](?P<m>\d{2})[-_](?P<d>\d{2})(?!\d)"),
        re.compile(r"(?<!\d)(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})(?!\d)"),
    ]
    MAX_GRAPH_IMAGES = 50
    MIN_PLOTTABLE_YEAR = 1900
    MAX_PLOTTABLE_YEAR = 2099

    def _is_safe_year(self, year: int) -> bool:
        return self.MIN_PLOTTABLE_YEAR <= year <= self.MAX_PLOTTABLE_YEAR

    def _extract_timestamp(self, image_path: Path) -> datetime | None:
        name = image_path.stem
        for pattern in self.DATE_PATTERNS:
            match = pattern.search(name)
            if match:
                try:
                    year = int(match.group("y"))
                    month = int(match.group("m"))
                    day = int(match.group("d"))
                    if not self._is_safe_year(year):
                        continue
                    return datetime(year, month, day)
                except ValueError:
                    continue

        try:
            mtime = image_path.stat().st_mtime
            if mtime < 0:
                return None
            timestamp = datetime.fromtimestamp(mtime)
            if not self._is_safe_year(timestamp.year):
                return None
            return timestamp
        except (OSError, OverflowError, ValueError):
            return None

    @staticmethod
    def _load_temperature_by_date(temperature_csv: Path | None) -> dict[str, float]:
        if temperature_csv is None or not temperature_csv.exists():
            return {}

        records: dict[str, float] = {}
        with temperature_csv.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                return records

            date_key = None
            temp_key = None
            for key in reader.fieldnames:
                lower = key.strip().lower()
                if lower in {"date", "timestamp", "time"}:
                    date_key = key
                if lower in {"temperature", "temp", "temperature_c", "temp_c"}:
                    temp_key = key

            if date_key is None or temp_key is None:
                return records

            for row in reader:
                date_text = (row.get(date_key) or "").strip()
                temp_text = (row.get(temp_key) or "").strip()
                if not date_text or not temp_text:
                    continue
                try:
                    value = float(temp_text)
                except ValueError:
                    continue
                records[date_text] = value

        return records

    @staticmethod
    def _vegetation_score(image: np.ndarray) -> float:
        image = image.astype(np.float32) / 255.0
        r = image[:, :, 0]
        g = image[:, :, 1]
        b = image[:, :, 2]
        exg = 2.0 * g - r - b
        return float(np.mean(exg))

    @staticmethod
    def _urban_score(image: np.ndarray) -> float:
        image = image.astype(np.float32) / 255.0
        r = image[:, :, 0]
        g = image[:, :, 1]
        b = image[:, :, 2]
        brightness = (r + g + b) / 3.0
        green_bias = g - (r + b) / 2.0
        return float(np.mean(brightness - green_bias))

    def build_timeline_graphs(
        self,
        image_paths: list[Path],
        output_dir: Path,
        prefix: str = "timeline",
        temperature_csv: Path | None = None,
    ) -> tuple[list[Path], str]:
        output_dir.mkdir(parents=True, exist_ok=True)

        if len(image_paths) < 2:
            return [], "Not enough historical images for timeline graphs (need at least 2)."

        total_images = len(image_paths)
        if total_images > self.MAX_GRAPH_IMAGES:
            step = max(1, total_images // self.MAX_GRAPH_IMAGES)
            image_paths = image_paths[::step]
            print(
                f"Info: sampling {len(image_paths)} of {total_images} images for timeline graph generation."
            )

        datapoints: list[tuple[datetime, float, float]] = []
        for path in image_paths:
            try:
                with Image.open(path) as img:
                    arr = np.asarray(img.convert("RGB"))
                timestamp = self._extract_timestamp(path)
                if timestamp is None:
                    print(
                        f"Warning: skipping {path} because the timestamp is invalid or out-of-range."
                    )
                    continue
                if arr.ndim != 3 or arr.shape[2] != 3:
                    print(f"Warning: skipping {path} because it is not a valid RGB image.")
                    continue
                vegetation = self._vegetation_score(arr)
                urban = self._urban_score(arr)
                datapoints.append((timestamp, vegetation, urban))
            except Exception as exc:  # noqa: BLE001
                print(f"Warning: skipping graph metric extraction for {path}: {exc}")

        if len(datapoints) < 2:
            return [], "Not enough valid images for graph generation after filtering invalid files."

        datapoints.sort(key=lambda x: x[0])
        dates = [x[0] for x in datapoints]
        vegetation = [x[1] for x in datapoints]
        urban = [x[2] for x in datapoints]

        graph_paths: list[Path] = []

        try:
            veg_graph = output_dir / f"{prefix}_vegetation_loss.png"
            plt.figure(figsize=(10, 5))
            plt.plot(dates, vegetation, marker="o", linewidth=2)
            plt.title("Vegetation Trend (Proxy)")
            plt.xlabel("Time")
            plt.ylabel("Excess Green Index")
            plt.grid(alpha=0.3)
            plt.tight_layout()
            plt.savefig(veg_graph, dpi=160)
            plt.close()
            graph_paths.append(veg_graph)

            urban_graph = output_dir / f"{prefix}_urban_growth.png"
            plt.figure(figsize=(10, 5))
            plt.plot(dates, urban, marker="o", linewidth=2, color="tab:red")
            plt.title("Urban Growth Trend (Proxy)")
            plt.xlabel("Time")
            plt.ylabel("Urban Intensity Score")
            plt.grid(alpha=0.3)
            plt.tight_layout()
            plt.savefig(urban_graph, dpi=160)
            plt.close()
            graph_paths.append(urban_graph)
        except Exception as exc:  # noqa: BLE001
            return [], f"Graph plotting failed: {exc}"

        temperature_by_date = self._load_temperature_by_date(temperature_csv)
        if temperature_by_date:
            temp_x: list[float] = []
            urban_y: list[float] = []
            for dt, _, urban_score in datapoints:
                key = dt.strftime("%Y-%m-%d")
                if key in temperature_by_date:
                    temp_x.append(temperature_by_date[key])
                    urban_y.append(urban_score)

            if len(temp_x) >= 2:
                try:
                    temp_graph = output_dir / f"{prefix}_temperature_correlation.png"
                    plt.figure(figsize=(8, 5))
                    plt.scatter(temp_x, urban_y, c="tab:orange", alpha=0.8)
                    plt.title("Temperature vs Urban Intensity Correlation")
                    plt.xlabel("Temperature")
                    plt.ylabel("Urban Intensity Score")
                    plt.grid(alpha=0.3)
                    plt.tight_layout()
                    plt.savefig(temp_graph, dpi=160)
                    plt.close()
                    graph_paths.append(temp_graph)
                except Exception as exc:  # noqa: BLE001
                    print(f"Warning: failed to build temperature correlation graph: {exc}")

        summary = (
            f"Graph summary: vegetation trend changed from {vegetation[0]:.3f} to {vegetation[-1]:.3f}; "
            f"urban trend changed from {urban[0]:.3f} to {urban[-1]:.3f}."
        )
        return graph_paths, summary

        veg_graph = output_dir / f"{prefix}_vegetation_loss.png"
        plt.figure(figsize=(10, 5))
        plt.plot(dates, vegetation, marker="o", linewidth=2)
        plt.title("Vegetation Trend (Proxy)")
        plt.xlabel("Time")
        plt.ylabel("Excess Green Index")
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(veg_graph, dpi=160)
        plt.close()
        graph_paths.append(veg_graph)

        urban_graph = output_dir / f"{prefix}_urban_growth.png"
        plt.figure(figsize=(10, 5))
        plt.plot(dates, urban, marker="o", linewidth=2, color="tab:red")
        plt.title("Urban Growth Trend (Proxy)")
        plt.xlabel("Time")
        plt.ylabel("Urban Intensity Score")
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(urban_graph, dpi=160)
        plt.close()
        graph_paths.append(urban_graph)

        # Optional temperature correlation graph when side data is available.
        temperature_by_date = self._load_temperature_by_date(temperature_csv)
        if temperature_by_date:
            temp_x: list[float] = []
            urban_y: list[float] = []
            for dt, _, urban_score in datapoints:
                key = dt.strftime("%Y-%m-%d")
                if key in temperature_by_date:
                    temp_x.append(temperature_by_date[key])
                    urban_y.append(urban_score)

            if len(temp_x) >= 2:
                temp_graph = output_dir / f"{prefix}_temperature_correlation.png"
                plt.figure(figsize=(8, 5))
                plt.scatter(temp_x, urban_y, c="tab:orange", alpha=0.8)
                plt.title("Temperature vs Urban Intensity Correlation")
                plt.xlabel("Temperature")
                plt.ylabel("Urban Intensity Score")
                plt.grid(alpha=0.3)
                plt.tight_layout()
                plt.savefig(temp_graph, dpi=160)
                plt.close()
                graph_paths.append(temp_graph)

        summary = (
            f"Graph summary: vegetation trend changed from {vegetation[0]:.3f} to {vegetation[-1]:.3f}; "
            f"urban trend changed from {urban[0]:.3f} to {urban[-1]:.3f}."
        )
        return graph_paths, summary
