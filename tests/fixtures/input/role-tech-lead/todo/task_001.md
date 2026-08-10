from collections import OrderedDict
from threading import RLock


class LRUCache:
    """Thread-safe Least-Recently-Used cache with fixed capacity."""

    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self.cache: "OrderedDict[str, str]" = OrderedDict()
        self._lock = RLock()

    def get(self, key: str) -> str | None:
        with self._lock:
            if key not in self.cache:
                return None
            self.cache.move_to_end(key)
            return self.cache[key]

    def put(self, key: str, value: str) -> None:
        with self._lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = value
            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self.cache.clear()

    def size(self) -> int:
        with self._lock:
            return len(self.cache)
