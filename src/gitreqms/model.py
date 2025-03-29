from abc import abstractmethod

class IModel:
    @abstractmethod
    def isValidAType(self, atype: str) -> bool:
        pass


class StandardModel(IModel):
    STANDARD_ATYPES = ['REQ', 'ARCH', 'VALID', 'SRC', 'TEST']

    def isValidAType(self, atype: str) -> bool:
        return atype in StandardModel.STANDARD_ATYPES
