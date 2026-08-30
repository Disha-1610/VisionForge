import base64
import logging
from io import BytesIO
from pathlib import Path

import numpy as np
import requests
import torch
from PIL import Image

try:
    import faiss
except ImportError:
    faiss = None

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Unified Image Embedding Service with FAISS similarity search.
    Primary: Google Gemini (gemini-embedding-2) with 1-shot attempt.
    Fallback: Local OpenCLIP (openai/clip-vit-base-patch32).
    """

    def __init__(self, clip_model_name: str = "ViT-B-32"):
        self.clip_model_name = clip_model_name
        self.clip_model = None
        self.clip_preprocess = None
        self.clip_tokenizer = None
        self._index: faiss.IndexFlatIP | None = None
        self._id_map: list[str] = []
        self._dimension: int = 3072
        self._raw_embeddings: list[np.ndarray] = []

    def load_clip_model(self) -> None:
        """Lazy-load local OpenCLIP model on first use."""
        if self.clip_model is not None:
            return

        import open_clip

        name = self.clip_model_name
        if "vit-base-patch32" in name.lower() or "b-32" in name.lower():
            name = "ViT-B-32"

        logger.info("Loading local OpenCLIP model: %s", name)
        self.clip_model, _, self.clip_preprocess = open_clip.create_model_and_transforms(
            name, pretrained="openai"
        )
        self.clip_tokenizer = open_clip.get_tokenizer(name)
        self.clip_model.eval()
        logger.info("Local OpenCLIP model loaded successfully")

    def _generate_clip_embedding(self, image: Image.Image) -> np.ndarray:
        """Generate a normalized 512-dim embedding using local OpenCLIP."""
        self.load_clip_model()
        image_tensor = self.clip_preprocess(image).unsqueeze(0)
        with torch.no_grad():
            features = self.clip_model.encode_image(image_tensor)
            features = features / features.norm(dim=-1, keepdim=True)
            return features.squeeze(0).cpu().numpy().astype(np.float32)

    def _generate_gemini_embedding(self, image: Image.Image, timeout: float = 6.0) -> np.ndarray:
        """Generate a normalized 3072-dim embedding using Google Gemini (1 attempt)."""
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not configured")

        buf = BytesIO()
        image.convert("RGB").save(buf, format="JPEG", quality=90)
        img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        url = f"{settings.GEMINI_BASE_URL.rstrip('/')}/models/{settings.GEMINI_EMBEDDING_MODEL}:embedContent?key={settings.GEMINI_API_KEY}"
        payload = {
            "model": f"models/{settings.GEMINI_EMBEDDING_MODEL}",
            "content": {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": img_b64,
                        }
                    }
                ]
            },
        }

        resp = requests.post(url, json=payload, timeout=timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"Gemini API returned status {resp.status_code}: {resp.text[:200]}")

        values = resp.json().get("embedding", {}).get("values", [])
        if not values:
            raise ValueError("Empty embedding returned by Gemini API")

        vec = np.array(values, dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def generate_embedding(self, image: Image.Image, try_gemini: bool = True) -> np.ndarray:
        """
        Generate a normalized image embedding.
        Tries Google Gemini API first (1 try); falls back to local OpenCLIP on failure.
        """
        if try_gemini and settings.GEMINI_API_KEY:
            try:
                vec = self._generate_gemini_embedding(image)
                logger.debug("Successfully generated embedding via Gemini (dim=%d)", len(vec))
                return vec
            except Exception as exc:
                logger.warning(
                    "Gemini embedding 1-shot attempt failed (%s). Falling back to OpenCLIP.", exc
                )

        return self._generate_clip_embedding(image)

    def build_index(self, embeddings: np.ndarray, ids: list[str]) -> None:
        """Build a new index from a batch of embeddings."""
        self._dimension = embeddings.shape[1]
        self._id_map = list(ids)
        self._raw_embeddings = [vec / np.linalg.norm(vec) for vec in embeddings]
        if faiss is not None:
            self._index = faiss.IndexFlatIP(self._dimension)
            faiss.normalize_L2(embeddings)
            self._index.add(embeddings)
            logger.info("FAISS index built with %d vectors (dim=%d)", len(ids), self._dimension)
        else:
            logger.info("Numpy Vector index built with %d vectors (dim=%d)", len(ids), self._dimension)

    def add_to_index(self, embedding: np.ndarray, id_str: str) -> None:
        """Add a single embedding to the existing index."""
        norm_vec = embedding / np.linalg.norm(embedding)
        self._raw_embeddings.append(norm_vec)
        self._id_map.append(id_str)
        self._dimension = len(embedding)

        if faiss is not None:
            if self._index is None:
                self._index = faiss.IndexFlatIP(self._dimension)
            vec = embedding.reshape(1, -1).astype(np.float32)
            faiss.normalize_L2(vec)
            self._index.add(vec)

    def search(self, query_embedding: np.ndarray, k: int = 5) -> list[tuple[str, float]]:
        """Search the index for the k most similar images. Returns [(id, score)]."""
        if not self._id_map:
            return []

        if faiss is not None and self._index is not None and self._index.ntotal > 0:
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

        # Fallback: Numpy Cosine Dot Product
        q_norm = query_embedding / np.linalg.norm(query_embedding)
        scores = [float(np.dot(q_norm, db_vec)) for db_vec in self._raw_embeddings]
        ranked = sorted(zip(self._id_map, scores), key=lambda x: x[1], reverse=True)[:k]
        return ranked

    def save_index(self, path: str | Path) -> None:
        """Persist the FAISS index and ID map to disk."""
        if self._index is None:
            raise RuntimeError("No index to save â€” call build_index first")

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
