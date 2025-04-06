class RMSException(Exception):
    pass

class InvalidArtifactIdentifier(RMSException):
    pass

class InvalidArtifactType(RMSException):
    pass

class NonFatalError(RMSException):
    def __init__(self):
        super().__init__('Errors were reported')