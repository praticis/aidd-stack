class Cache:
    def __init__(self):
        self.items = {}

    def get(self, key: str):
        return self.items.get(key)
