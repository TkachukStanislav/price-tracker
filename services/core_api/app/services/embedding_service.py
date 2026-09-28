import asyncio
import logging

from fastembed import TextEmbedding

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        # Ініціалізуємо легку та швидку ONNX-модель
        self.model = TextEmbedding(model_name=model_name)

    def generate_embedding(self, text: str) -> list[float]:
        """Генерує векторний ембеддинг (384 числа) для переданого рядка."""
        try:
            embeddings = list(self.model.embed([text]))
            return embeddings[0].tolist()
        except Exception:
            logger.exception("Помилка генерації ембеддингу")
            raise

    async def generate_embedding_async(self, text: str) -> list[float]:
        """Рахує ембеддинг в окремому потоці, щоб не блокувати event loop."""
        return await asyncio.to_thread(self.generate_embedding, text)


embedding_service = EmbeddingService()
