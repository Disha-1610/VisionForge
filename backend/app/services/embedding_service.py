import base64
import json
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

# Embedding providers and their output dimensions. An index is built in ONE
# provider's space; queries must use the same provider or search breaks.
PROVIDER_DIMS: dict[str, int] = {
    "gemini": 3072,
    "clip": 512,
}


class EmbeddingDimensionMismatch(Exception):
    """Raised when a query/index embedding dimension doesn't match the index."""


class EmbeddingService:
    """
    Unified Image Embedding Service with FAISS similarity search.
    Primary: Google Gemini (gemini-embedding-2) with 1-shot attempt.
    Fallback: Local OpenCLIP (openai/clip-vit-base-patch32).

    Dimension safety (W2 D4): the index tracks which provider built it
    (`_provider`). Queries generated via `generate_embedding_for_index()`
    always match the index space, so a Gemini->CLIP fallback can never
    corrupt a 3072-dim index with a 512-dim vector.
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
        self._provider: str | None = None

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

    def generate_embedding_for_index(self, image: Image.Image) -> tuple[np.ndarray, str]:
        """
        Generate an embedding that matches the CURRENT index's provider space.

        Returns (embedding, provider). Rules:
        - Empty index: full dual logic (Gemini 1-shot -> CLIP); the chosen
          provider becomes the index provider on first add.
        - CLIP-built index: always CLIP (local, deterministic).
        - Gemini-built index: Gemini 1-shot; on failure raise
          EmbeddingDimensionMismatch (a CLIP fallback vector would not be
          comparable against gemini-space vectors in the index).
        """
        if self._provider == "clip" or (self._index is not None and self._dimension == PROVIDER_DIMS["clip"]):
            return self._generate_clip_embedding(image), "clip"

        if self._provider == "gemini":
            vec = self._generate_gemini_embedding(image)
            return vec, "gemini"

        # Empty index — dual logic decides the provider.
        if settings.GEMINI_API_KEY:
            try:
                vec = self._generate_gemini_embedding(image)
                return vec, "gemini"
            except Exception as exc:
                logger.warning("Gemini 1-shot failed (%s); using OpenCLIP for new index.", exc)
        return self._generate_clip_embedding(image), "clip"

    def _validate_dim(self, embedding: np.ndarray, context: str) -> None:
        if self._id_map and embedding.shape[0] != self._dimension:
            raise EmbeddingDimensionMismatch(
                f"{context}: embedding dim {embedding.shape[0]} does not match "
                f"index dim {self._dimension} (provider={self._provider})"
            )

    def index_golden_reference(self, image_path: str, golden_id: str) -> tuple[str, float]:
        """
        High-level W2 D4 helper: embed a golden image and add it to the index.
        Returns (provider, processing_time_ms).
        """
        import time

        start = time.perf_counter()
        from app.utils.image_utils import load_pil_image

        embedding, provider = self.generate_embedding_for_index(load_pil_image(image_path))
        self.add_to_index(embedding, golden_id, provider=provider)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("Indexed golden reference %s (provider=%s)", golden_id, provider)
        return provider, round(elapsed_ms, 2)

    def rebuild_index(self, references: list[tuple[str, str]]) -> str:
        """
        Rebuild the whole index from (image_path, golden_id) pairs — used for
        bulk admin uploads and after deletions (FAISS IndexFlatIP cannot
        remove single vectors). Returns the provider used.
        """
        if not references:
            self._index = None
            self._id_map = []
            self._raw_embeddings = []
            self._provider = None
            logger.info("Index cleared (no references to build)")
            return "none"

        provider_used: str | None = None
        embeddings: list[np.ndarray] = []
        ids: list[str] = []
        from app.utils.image_utils import load_pil_image

        for image_path, golden_id in references:
            embedding, provider = self.generate_embedding_for_index(load_pil_image(image_path))
            if provider_used is None:
                provider_used = provider
            elif provider != provider_used:
                raise EmbeddingDimensionMismatch(
                    f"Mixed embedding providers during rebuild: {provider_used} vs {provider}"
                )
            embeddings.append(embedding)
            ids.append(golden_id)

        self.build_index(np.vstack(embeddings).astype(np.float32), ids, provider=provider_used)
        return provider_used

    def remove_from_index(self, id_str: str) -> bool:
        """
        Remove a golden reference's embedding (VisionForge.md §8 deletion rule).
        FAISS IndexFlatIP cannot delete in place, so the index is rebuilt from
        the retained raw embeddings. Returns True if the id was found+removed.
        """
        if id_str not in self._id_map:
            return False

        keep = [
            (vec, iid)
            for vec, iid in zip(self._raw_embeddings, self._id_map)
            if iid != id_str
        ]
        if not keep:
            self._index = None
            self._id_map = []
            self._raw_embeddings = []
            self._provider = None
            logger.info("Index emptied after removing %s", id_str)
            return True

        vectors = np.vstack([v for v, _ in keep]).astype(np.float32)
        remaining_ids = [iid for _, iid in keep]
        self.build_index(vectors, remaining_ids, provider=self._provider or "clip")
        logger.info("Removed %s from index; rebuilt with %d vectors", id_str, len(remaining_ids))
        return True

    def build_index(
        self, embeddings: np.ndarray, ids: list[str], provider: str | None = None
    ) -> None:
        """Build a new index from a batch of embeddings."""
        self._dimension = embeddings.shape[1]
        self._id_map = list(ids)
        self._raw_embeddings = [vec / np.linalg.norm(vec) for vec in embeddings]
        self._provider = provider or self._provider
        if faiss is not None:
            self._index = faiss.IndexFlatIP(self._dimension)
            vecs = embeddings.copy()
            faiss.normalize_L2(vecs)
            self._index.add(vecs)
            logger.info(
                "FAISS index built with %d vectors (dim=%d, provider=%s)",
                len(ids), self._dimension, self._provider,
            )
        else:
            logger.info("Numpy Vector index built with %d vectors (dim=%d)", len(ids), self._dimension)

    def add_to_index(
        self, embedding: np.ndarray, id_str: str, provider: str | None = None
    ) -> None:
        """Add a single embedding to the existing index (dimension-guarded)."""
        self._validate_dim(embedding, f"add_to_index({id_str})")
        if self._provider is None and provider:
            self._provider = provider

        norm_vec = embedding / np.linalg.norm(embedding)
        self._raw_embeddings.append(norm_vec)
        self._id_map.append(id_str)
        self._dimension = embedding.shape[0]

        if faiss is not None:
            if self._index is None:
                self._index = faiss.IndexFlatIP(self._dimension)
            vec = embedding.reshape(1, -1).astype(np.float32)
            faiss.normalize_L2(vec)
            self._index.add(vec)

    def search(self, query_embedding: np.ndarray, k: int = 5) -> list[tuple[str, float]]:
        """
        Search the index for the k most similar images. Returns [(id, score)].
        Raises EmbeddingDimensionMismatch if the query dim doesn't match the
        index (never silently returns garbage).
        """
        if not self._id_map:
            return []

        self._validate_dim(query_embedding, "search")

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
        """Persist the FAISS index, ID map and provider metadata to disk."""
        if self._index is None and not self._raw_embeddings:
            raise RuntimeError("No index to save — call build_index first")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if faiss is not None and self._index is not None:
            faiss.write_index(self._index, str(path))
        else:
            np.save(str(path) + ".npy", np.vstack(self._raw_embeddings))

        map_path = path.with_suffix(".ids.npy")
        np.save(str(map_path), np.array(self._id_map))

        meta_path = path.with_suffix(".meta.json")
        meta_path.write_text(
            json.dumps({"provider": self._provider, "dimension": self._dimension}),
            encoding="utf-8",
        )
        logger.info(
            "FAISS index saved to %s (vectors=%d, provider=%s)",
            path, len(self._id_map), self._provider,
        )

    def load_index(self, path: str | Path) -> bool:
        """Load a persisted FAISS index (with provider metadata). Returns True if successful."""
        path = Path(path)
        map_path = path.with_suffix(".ids.npy")

        faiss_file_exists = path.exists() and path.suffix in (".index", ".faiss")
        npy_file_exists = Path(str(path) + ".npy").exists()
        if not map_path.exists() or not (faiss_file_exists or npy_file_exists):
            logger.warning("FAISS index not found at %s", path)
            return False

        meta_path = path.with_suffix(".meta.json")
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self._provider = meta.get("provider")
            self._dimension = int(meta.get("dimension", 0))

        if faiss is not None and faiss_file_exists:
            self._index = faiss.read_index(str(path))
            self._id_map = np.load(str(map_path), allow_pickle=True).tolist()
            self._dimension = self._index.d
            # Reconstruct raw vectors so numpy-fallback search and
            # remove_from_index rebuilds work after a process restart.
            self._raw_embeddings = [
                self._index.reconstruct(i) for i in range(self._index.ntotal)
            ]
        else:
            vectors = np.load(str(path) + ".npy")
            self._id_map = np.load(str(map_path), allow_pickle=True).tolist()
            self._dimension = vectors.shape[1]
            self._raw_embeddings = list(vectors)
            self._index = None

        logger.info(
            "FAISS index loaded: %d vectors (dim=%d, provider=%s)",
            len(self._id_map), self._dimension, self._provider,
        )
        return True

    @property
    def index_size(self) -> int:
        return self._index.ntotal if self._index else len(self._id_map)

    @property
    def provider(self) -> str | None:
        return self._provider


embedding_service = EmbeddingService()
