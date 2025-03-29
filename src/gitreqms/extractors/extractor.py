from abc import ABC, abstractmethod
from pathlib import Path
from typing import Sequence

from gitreqms.config import InputRecord
from gitreqms.artifact import Artifact


class Extractor(ABC):
    @abstractmethod
    def extract_from_file(self, filepath: Path) -> Sequence[Artifact]:
        pass

    @abstractmethod
    def extract(self, record: InputRecord) -> Sequence[Artifact]:
        pass
