class HttpError(OSError):
    """Raised when the Synapse API returns a non-2xx response.

    Attributes:
        status: the HTTP status code returned by the API.
    """

    def __init__(self, status, message=None):
        """
        Args:
            status: the HTTP status code returned by the API.
            message: optional human-readable message; defaults to a generic
                "HTTP error {status}" if not given.
        """
        self.status = status
        super().__init__(message or "HTTP error {}".format(status))
