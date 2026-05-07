import shutil


class CleanupRegistry:
    def __init__(self):
        self._items = []
        self.last_report = {"succeeded": [], "failed": []}

    def add(self, label, callback, retries=0):
        self._items.append({"label": label, "callback": callback, "retries": retries})

    def add_path(self, path, retries=0):
        def remove_path():
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()

        self.add(str(path), remove_path, retries=retries)
        return self

    def run(self):
        report = {"succeeded": [], "failed": []}
        while self._items:
            item = self._items.pop()
            label = item["label"]
            callback = item["callback"]
            retries = item["retries"]
            attempts = 0

            while True:
                attempts += 1
                try:
                    callback()
                    report["succeeded"].append({"label": label, "attempts": attempts})
                    break
                except Exception as exc:
                    if attempts <= retries:
                        continue
                    report["failed"].append({"label": label, "attempts": attempts, "error": str(exc)})
                    break

        self.last_report = report
        if report["failed"]:
            failed = "; ".join(f"{item['label']}: {item['error']}" for item in report["failed"])
            raise AssertionError("cleanup failed: " + failed)
        return report


def register_cleanup(testcase):
    registry = CleanupRegistry()
    testcase.addCleanup(registry.run)
    return registry
