import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from app.models.schemas import SceneMetadata


class MetadataStore:
    def __init__(self, metadata_path: Path):
        self.metadata_path = metadata_path
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.metadata_path.exists():
            self.metadata_path.write_text("", encoding="utf-8")

    def upsert(self, metadata: SceneMetadata) -> None:
        all_items = {item.id: item for item in self.list_all()}
        all_items[metadata.id] = metadata
        with self.metadata_path.open("w", encoding="utf-8") as f:
            for item in all_items.values():
                f.write(item.model_dump_json() + "\n")

    def get(self, scene_id: str) -> Optional[SceneMetadata]:
        for item in self.list_all():
            if item.id == scene_id:
                return item
        return None

    def list_all(self) -> Iterable[SceneMetadata]:
        with self.metadata_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data: Dict = json.loads(line)
                yield SceneMetadata(**data)

    def filter_by_time(self, time_from: Optional[str], time_to: Optional[str]) -> List[SceneMetadata]:
        items = list(self.list_all())
        if time_from:
            items = [i for i in items if i.timestamp >= time_from]
        if time_to:
            items = [i for i in items if i.timestamp <= time_to]
        return items
