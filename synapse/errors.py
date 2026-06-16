class HttpError(OSError):
    def __init__(self, status, message=None):
        self.status = status
        super().__init__(message or "HTTP error {}".format(status))
