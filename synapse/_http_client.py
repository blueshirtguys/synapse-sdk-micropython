import socket
import ssl

from collections import namedtuple

ApiTarget = namedtuple("ApiTarget", ("host", "port", "use_tls"))

_RECV_CHUNK_SIZE = 512
_DEFAULT_HTTPS_PORT = 443
_DEFAULT_HTTP_PORT = 80


def parse_url(url: str) -> ApiTarget:
    scheme, sep, rest = url.partition("://")

    if not sep:
        scheme, rest = "https", url

    if scheme not in ("http", "https"):
        raise ValueError("url must use http:// or https://, got: " + scheme)

    host_port, _, _path = rest.partition("/")

    if ":" in host_port:
        host, port_str = host_port.split(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            raise ValueError("url has an invalid port: " + port_str)
    else:
        host = host_port
        port = _DEFAULT_HTTPS_PORT if scheme == "https" else _DEFAULT_HTTP_PORT

    if not host:
        raise ValueError("url is missing a host")
    if not (0 < port < 65536):
        raise ValueError("url port out of range: " + str(port))

    return ApiTarget(host, port, scheme == "https")


class HttpClient:
    """Minimal HTTP/1.1 client over a raw socket, with optional TLS."""

    def __init__(self, base_url: str, timeout: float = 5.0):
        target = parse_url(base_url)
        self.host = target.host
        self.port = target.port
        self.use_tls = target.use_tls
        self.timeout = timeout

    def post(self, path: str, body_bytes: bytes, headers: dict) -> int:
        """Sends a POST request and returns the response status code."""
        return self._request("POST", path, body_bytes, headers)

    def _request(self, method: str, path: str, body_bytes: bytes, headers: dict) -> int:
        request_bytes = self._build_request(method, path, body_bytes, headers)
        response = self._transmit(request_bytes)
        return self._parse_status(response)

    def _build_request(self, method: str, path: str, body_bytes: bytes, headers: dict) -> bytes:
        header_lines = "".join(
            f"{name}: {value}\r\n" for name, value in headers.items()
        )
        request = (
            f"{method} {path} HTTP/1.1\r\n"
            f"Host: {self.host}\r\n"
            f"Content-Length: {len(body_bytes)}\r\n"
            f"{header_lines}"
            "Connection: close\r\n"
            "\r\n"
        )
        return request.encode("utf-8") + body_bytes

    def _transmit(self, request_bytes: bytes) -> bytes:
        s = socket.socket()
        try:
            s.settimeout(self.timeout)
            s.connect((self.host, self.port))
            if self.use_tls:
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                ctx.verify_mode = ssl.CERT_NONE
                s = ctx.wrap_socket(s, server_hostname=self.host)

            s.send(request_bytes)

            response = b""
            while True:
                chunk = s.recv(_RECV_CHUNK_SIZE)
                if not chunk:
                    break
                response += chunk
        finally:
            s.close()

        return response

    def _parse_status(self, response: bytes) -> int:
        return int(response.split(b" ", 2)[1])
