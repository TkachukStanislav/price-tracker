import asyncio
import logging

from fastembed import TextEmbedding

from app.core.config import settings
from app.core.metrics import EMBEDDING_DURATION

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self, model_name: str, cache_dir: str | None = None) -> None:
        # Модель завантажується один раз і далі береться з cache_dir
        self.model = TextEmbedding(model_name=model_name, cache_dir=cache_dir)

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Генерує ембеддинги (по 384 числа) для списку рядків за один прохід."""
        try:
            with EMBEDDING_DURATION.time():
                return [vector.tolist() for vector in self.model.embed(texts)]
        except Exception:
            logger.exception("Помилка генерації ембеддингів")
            raise

    def generate_embedding(self, text: str) -> list[float]:
        """Генерує векторний ембеддинг для одного рядка."""
        return self.generate_embeddings([text])[0]

    async def generate_embedding_async(self, text: str) -> list[float]:
        """Рахує ембеддинг в окремому потоці, щоб не блокувати event loop."""
        return await asyncio.to_thread(self.generate_embedding, text)

    async def generate_embeddings_async(self, texts: list[str]) -> list[list[float]]:
        """Пакетна версія generate_embedding_async."""
        return await asyncio.to_thread(self.generate_embeddings, texts)


embedding_service = EmbeddingService(
    model_name=settings.EMBEDDING_MODEL,
    cache_dir=settings.EMBEDDING_CACHE_DIR,
)
