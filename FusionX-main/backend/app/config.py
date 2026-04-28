from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    project_name: str = "FusionX Semantic Intelligence API"
    embedding_dim: int = 768
    tile_size: int = 224
    data_dir: Path = Path("backend/data")
    faiss_index_path: Path = Path("backend/data/vector.index")
    metadata_path: Path = Path("backend/data/metadata.jsonl")
    model_name: str = "google/siglip-base-patch16-224"
    device: str = "cpu"


settings = Settings()
