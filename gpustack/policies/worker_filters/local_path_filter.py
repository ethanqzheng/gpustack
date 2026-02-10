import logging
from typing import List, Tuple

from gpustack.client.worker_filesystem_client import WorkerFilesystemClient
from gpustack.policies.base import WorkerFilter
from gpustack.schemas.models import Model, SourceEnum
from gpustack.schemas.workers import Worker

logger = logging.getLogger(__name__)


class LocalPathFilter(WorkerFilter):
    """
    Filter workers based on whether the local path exists on them.
    Only applies to LOCAL_PATH models.
    """

    def __init__(self, model: Model):
        self._model = model

    async def filter(self, workers: List[Worker]) -> Tuple[List[Worker], List[str]]:
        """
        Filter workers by validating that the local path exists on each worker.
        For non-LOCAL_PATH models, all workers pass through unchanged.
        """

        # Skip filtering for non-LOCAL_PATH models
        if self._model.source != SourceEnum.LOCAL_PATH:
            return workers, []

        candidates = []
        invalid_workers = []

        # Validate local path existence on each worker
        async with WorkerFilesystemClient() as filesystem_client:
            for worker in workers:
                try:
                    exists_response = await filesystem_client.path_exists(
                        worker, self._model.local_path
                    )
                    if exists_response.exists:
                        candidates.append(worker)
                    else:
                        invalid_workers.append(worker.name)
                except Exception as e:
                    logger.warning(
                        f"Failed to check path {self._model.local_path} "
                        f"on worker {worker.name}: {e}"
                    )
                    invalid_workers.append(worker.name)

        messages = []
        if invalid_workers:
            messages.append(
                f"The model file path '{self._model.local_path}' does not "
                f"exist on the following workers: "
                f"{', '.join(sorted(invalid_workers))}. "
                f"Please ensure the model file is accessible on all workers."
            )

        return candidates, messages
