"""PageIndex package: build hierarchical document trees and retrieve content without vector search."""

from .page_index import *  # PDF indexing: page_index, page_index_main, etc.
from .page_index_md import md_to_tree  # Markdown indexing
from .retrieve import get_document, get_document_structure, get_page_content  # Agent retrieval tools
from .client import PageIndexClient  # High-level indexing + retrieval client