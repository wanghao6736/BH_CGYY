from __future__ import annotations

from typing import Any, Dict, Optional

from src.api.catalog_api import CatalogApi
from src.parsers.catalog import CatalogParsed, parse_catalog_response


class CatalogService:
    def __init__(self, api: CatalogApi) -> None:
        self.api = api

    def get_catalog_raw(self) -> Dict[str, Any]:
        return self.api.website_init()

    def get_catalog_parsed(self) -> tuple[bool, str, Optional[CatalogParsed]]:
        raw = self.get_catalog_raw()
        return parse_catalog_response(raw)
