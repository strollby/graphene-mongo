import os
import sphinx_graphene_theme

project = "Graphene-Mongo"
copyright = "2024, graphene-mongo contributors"
author = "graphene-mongo contributors"
version = "0.5"
release = "0.5.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
]

on_rtd = os.environ.get("READTHEDOCS") == "True"
if not on_rtd:
    extensions.append("sphinx.ext.githubpages")

source_suffix = ".rst"
master_doc = "index"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
pygments_style = "sphinx"

html_theme = "sphinx_graphene_theme"
html_theme_path = [sphinx_graphene_theme.get_html_theme_path()]
html_static_path = ["_static"]

intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}

html_context = {
    "rtd_versions_url": "https://readthedocs.org/projects/graphene-mongo/versions/",
}
