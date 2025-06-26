import time

class TimedCache:
    def __init__(self, ttl_seconds=300):
        self.ttl = ttl_seconds
        self.cache = {}

    def get(self, key):
        value, timestamp = self.cache.get(key, (None, 0))
        if time.time() - timestamp < self.ttl:
            return value
        return None

    def set(self, key, value):
        self.cache[key] = (value, time.time())

    def clear(self):
        self.cache.clear()
