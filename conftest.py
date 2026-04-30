import os

collect_ignore = [
    os.path.join(os.path.dirname(__file__), "filer", "tests", "utils"),
    os.path.join(os.path.dirname(__file__), "filer", "tests", "__init__.py"),
    os.path.join(os.path.dirname(__file__), "filer", "contrib"),
    os.path.join(os.path.dirname(__file__), "filer", "management"),
]

