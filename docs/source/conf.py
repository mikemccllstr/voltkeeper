import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath("../../src"))

project = "voltkeeper"
copyright = f"{datetime.now().year}, Michael McCallister"
author = "Michael McCallister"
release = "0.1.0"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
]

templates_path = ["_templates"]
exclude_patterns = [
    ".venv",
    "__pycache__",
    "Thumbs.db",
    ".DS_Store",
]

html_theme = "furo"
html_static_path = ["_static"]
html_title = "voltkeeper"
html_logo = "_static/voltkeeper-logo.svg"

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
]

# -- Man pages ----------------------------------------------------------------
man_pages = [
    (
        "man/voltkeeper.1",
        "voltkeeper",
        "CLI tool for Bluetti power stations over BLE",
        [author],
        1,
    ),
]
