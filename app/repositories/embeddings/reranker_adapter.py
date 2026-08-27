import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol

import httpx

from app.config.settings import settings
from app.repositories.embeddings.fastembed_offline import load_fastembed_model

logger = logging.getLogger(__name__)


class RerankAdapter(Protocol):
    """Contract for a Reranker Adapter"""
    async def rerank(self,
                     query: str,
                     documents: list[str],
    ) -> list[tuple[int, float]]:
        ...

class FastEmbedCrossEncoderAdapter:
    """Cross-encoder reranker using FastEmbeds TextCrossEncoder"""

    def __init__(
            self,
            model: str = settings.RERANKING_MODEL,
            threads: int = settings.RERANKING_THREADS,
            cache_dir: str | None  = None,
    ):
        """Intialise FastEmbed cross encoder"""
        self.model_name = model
        self.threads = threads
        self.cache_dir = cache_dir

        effective_cache_dir = cache_dir or settings.FASTEMBED_CACHE_DIR
        self._model = load_fastembed_model(
            model_role="reranking",
            model_name=model,
            cache_dir=effective_cache_dir,
            factory=lambda fastembed_kwargs: self._create_text_cross_encoder(
                model=model,
                threads=threads,
                cache_dir=cache_dir,
                fastembed_kwargs=fastembed_kwargs,
            ),
        )
        self._executor = ThreadPoolExecutor(max_workers=1)

    def _create_text_cross_encoder(
            self,
            *,
            model: str,
            threads: int,
            cache_dir: str | None,
            fastembed_kwargs: dict[str, bool],
    ):
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        return TextCrossEncoder(
            model_name=model,
            threads=threads,
            cache_dir=cache_dir,
            **fastembed_kwargs,
        )

    async def rerank(
            self,
            query: str,
            documents: list[str],
    ) -> list[tuple[int, float]]:
        """Score documents by relevance to query"""
        if not documents:
            return []

        loop = asyncio.get_event_loop()

        ranked = await loop.run_in_executor(
            self._executor,
            self._rerank_sync,
            query,
            documents,
        )

        return ranked

    def _rerank_sync(self, query: str, documents: list[str])-> list[tuple[int,float]]:
        """Synchronus reranking implementation"""
        scores = list(self._model.rerank(query=query, documents=documents))
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return ranked

    def __del__(self):
        """CLeanup thread ppol on deletion."""
        if hasattr(self, "_executor"):
            self._executor.shutdown(wait=False)


class HttpRerankAdapter:
    """Cross-encoder reranker using http"""

    def __init__(
            self,
            model: str | None = None,
            url: str | None = None,
            api_key: str | None = None,
    ):
        self.model = model if model is not None else settings.RERANKING_MODEL
        self.url = url if url is not None else settings.RERANKING_URL
        self.api_key = api_key if api_key is not None else settings.RERANKING_API_KEY
        # Bounded timeout so a wedged remote reranker (e.g. a GPU that has fallen
        # off the bus) fails fast instead of hanging the whole query.
        self.timeout = settings.RERANKING_HTTP_TIMEOUT
        # Lazily-built local CPU reranker used as a fallback when the HTTP
        # endpoint is unreachable/slow, so recall degrades to CPU reranking
        # rather than to no reranking. Built on first fallback and reused.
        self._cpu_fallback: FastEmbedCrossEncoderAdapter | None = None

    def _get_cpu_fallback(self) -> "FastEmbedCrossEncoderAdapter | None":
        if not settings.RERANKING_HTTP_CPU_FALLBACK:
            return None
        if self._cpu_fallback is None:
            self._cpu_fallback = FastEmbedCrossEncoderAdapter(
                cache_dir=settings.FASTEMBED_CACHE_DIR,
            )
        return self._cpu_fallback

    async def rerank(
            self,
            query: str,
            documents: list[str],
    ) -> list[tuple[int, float]]:

        if not documents:
            return []

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "query": query,
            "documents": documents,
            "model": self.model,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url=self.url, headers=headers, json=payload)
                response.raise_for_status()

            response_json = response.json()

            return [
                (r["index"], r["relevance_score"])
                for r in response_json["results"]
            ]
        except Exception as exc:
            # HTTP reranker unreachable/slow/erroring. Fall back to a local CPU
            # reranker if enabled; if that also fails, re-raise so the caller can
            # degrade to the pre-rerank order (memory stays up either way).
            fallback = self._get_cpu_fallback()
            if fallback is None:
                logger.warning(
                    "HTTP reranker failed (%s) and CPU fallback disabled; "
                    "caller should degrade to pre-rerank order.", exc,
                )
                raise
            logger.warning(
                "HTTP reranker failed (%s); falling back to local CPU reranker.",
                exc,
            )
            return await fallback.rerank(query=query, documents=documents)


