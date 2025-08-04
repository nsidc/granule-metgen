import sys
from pathlib import Path

sys.path.insert(0, str(Path("..", "..", "src").resolve()))

project = "MetGenC"
copyright = "2024, NSIDC"
author = "National Snow and Ice Data Center"
release = "v1.10.0rc1"
version = "v1.10.0rc1"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.doctest",
    "sphinx.ext.duration",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
]

exclude_patterns = [
    "_build",
    "**.ipynb_checkpoints",
    "Thumbs.db",
    ".DS_Store",
    ".env",
    ".venv",
]
intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "sphinx": ("https://www.sphinx-doc.org/en/master/", None),
}
intersphinx_disabled_domains = ["std"]

templates_path = ["_templates"]

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

always_document_param_types = True
html_theme = "sphinx_rtd_theme"

html_theme = "alabaster"

html_static_path = ["_static"]
epub_show_urls = "footnote"
