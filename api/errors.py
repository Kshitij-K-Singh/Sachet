"""Service errors: user-facing failures with an HTTP status code attached."""


class PipelineError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status
