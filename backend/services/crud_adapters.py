class Adapter:
    def __init__(self, list_fn, get_fn, create_fn, update_fn, delete_fn):
        self.list_items = list_fn
        self.get_item = get_fn
        self.create_item = create_fn
        self.update_item = update_fn
        self.delete_item = delete_fn


# Keep route modules declarative while preserving dedicated service modules.
