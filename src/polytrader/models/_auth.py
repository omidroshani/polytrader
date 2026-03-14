from ._helpers import StrictStruct


class PolymarketAuth(StrictStruct):
    """Polymarket API authentication credentials"""

    api_key: str
    secret: str
    passphrase: str

    def to_auth_dict(self) -> dict[str, str]:
        """Convert to dict format for WebSocket auth"""
        return {
            "apiKey": self.api_key,
            "secret": self.secret,
            "passphrase": self.passphrase,
        }
