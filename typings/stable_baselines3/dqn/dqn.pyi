from pathlib import Path
from typing import Self

import numpy as np
from numpy.typing import NDArray


class DQN:
    @classmethod
    def load(cls, path: str | Path, *, device: str) -> Self: ...

    def predict(
        self,
        observation: NDArray[np.float32],
        *,
        deterministic: bool,
    ) -> tuple[NDArray[np.generic], tuple[NDArray[np.float32], ...] | None]: ...

    def save(self, path: Path) -> None: ...
