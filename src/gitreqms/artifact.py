class ARef:
    def __init__(self, atype: str, aid: str):
        self.atype: str = atype
        self.aid: str = aid

class Artifact:
    def __init__(self, atype: str, aid: str, pids: list[ARef] = []):
        self.atype: str = atype
        self.aid: str = aid
        self.pids: list[ARef] = pids

    def driver(self) -> str: ...

    def metastring(self) -> str:
        return ''
