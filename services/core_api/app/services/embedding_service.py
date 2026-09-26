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
        except Exception as e:
            logger.error(f"Помилка генерації ембеддингу: {e}")
            raise e


embedding_service = EmbeddingService()