from __future__ import annotations

import logging
from pathlib import Path

import faiss
import numpy as np
import torch
from PIL import Image

logger = logging.getLogger(__name__)


class EmbeddingService:
    """CLIP-based image embedding generation with FAISS similarity search."""

    def __init__(self, model_name: str = "openai/clip-vit-base-patch32"):
        self.model_name = model_name
        self.model = None
        self.preprocess = None
        self.tokenizer = None
        self._index: faiss.IndexFlatIP | None = None
        self._id_map: list[str] = []
        self._dimension: int = 512

    def load_model(self) -> None:
        """Lazy-load CLIP model on first use."""
        if self.model is not None:
            return

        import open_clip

        logger.info("Loading CLIP model: %s", self.model_name)
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            self.model_name, pretrained="openai"
        )
        self.tokenizer = open_clip.get_tokenizer(self.model_name)
        self.model.eval()
        logger.info("CLIP model loaded successfully")

    @torch.no_grad()
    def generate_embedding(self, image: Image.Image) -> np.ndarray:
        """Generate a normalized embedding for a single image."""
        self.load_model()
        image_tensor = self.preprocess(image).unsqueeze(0)
        features = self.model.encode_image(image_tensor)
        features = features / features.norm(dim=-1, keepdim=True)
        return features.squeeze(0).cpu().numpy().astype(np.float32)

    def build_index(self, embeddings: np.ndarray, ids: list[str]) -> None:
        """Build a new FAISS index from a batch of embeddings."""
        self._dimension = embeddings.shape[1]
        self._index = faiss.IndexFlatIP(self._dimension)
        self._id_map = list(ids)
        faiss.normalize_L2(embeddings)
        self._index.add(embeddings)
        logger.info("FAISS index built with %d vectors (dim=%d)", len(ids), self._dimension)

    def add_to_index(self, embedding: np.ndarray, id_str: str) -> None:
        """Add a single embedding to the existing index."""
        if self._index is None:
            self._dimension = len(embedding)
            self._index = faiss.IndexFlatIP(self._dimension)

        vec = embedding.reshape(1, -1).astype(np.float32)
        faiss.normalize_L2(vec)
        self._index.add(vec)
        self._id_map.append(id_str)

    def search(self, query_embedding: np.ndarray, k: int = 5) -> list[tuple[str, float]]:
        """Search the index for the k most similar images. Returns [(id, score)]."""
        if self._index is None or self._index.ntotal == 0:
            return []

        vec = query_embedding.reshape(1, -1).astype(np.float32)
        faiss.normalize_L2(vec)
        k = min(k, self._index.ntotal)
        scores, indices = self._index.search(vec, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self._id_map):
                continue
            results.append((self._id_map[idx], float(score)))
        return results

    def save_index(self, path: str | Path) -> None:
        """Persist the FAISS index and ID map to disk."""
        if self._index is None:
            raise RuntimeError("No index to save — call build_index first")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        faiss.write_index(self._index, str(path))
        map_path = path.with_suffix(".ids.npy")
        np.save(str(map_path), np.array(self._id_map))
        logger.info("FAISS index saved to %s", path)

    def load_index(self, path: str | Path) -> bool:
        """Load a persisted FAISS index. Returns True if successful."""
        path = Path(path)
        map_path = path.with_suffix(".ids.npy")

        if not path.exists() or not map_path.exists():
            logger.warning("FAISS index not found at %s", path)
            return False

        self._index = faiss.read_index(str(path))
        self._id_map = np.load(str(map_path), allow_pickle=True).tolist()
        self._dimension = self._index.d
        logger.info("FAISS index loaded: %d vectors (dim=%d)", self._index.ntotal, self._dimension)
        return True

    @property
    def index_size(self) -> int:
        return self._index.ntotal if self._index else 0


embedding_service = EmbeddingService()
