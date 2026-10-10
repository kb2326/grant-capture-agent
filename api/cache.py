"""In-memory results for the life of the API process; a hit costs nothing (M4 spec §3.1)."""


class ResultCache:
    def __init__(self) -> None:
        self._data: dict[tuple, dict] = {}

    def get(self, key: tuple) -> dict | None:
        return self._data.get(key)

    def put(self, key: tuple, value: dict) -> None:
        self._data[key] = value
