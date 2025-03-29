
from abc import ABC, abstractmethod


class Artifact(ABC):
    def __init__(self, atype: str, aid: str):
        self.atype: str = atype
        self.aid: str = aid
 
    @abstractmethod
    def driver(self) -> str:
        pass

    @abstractmethod
    def metastring(self) -> str:
        pass
