"""Scraper configuration and registry."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Type


@dataclass
class ScraperConfig:
    """Configuration for a scraper worker."""

    worker_name: str
    institute_id: str
    provider: str
    source: str
    scope: str
    election_id: str
    method_id: str = "99"
    urls: List[Dict[str, Any]] = field(default_factory=list)
    type: str = "wahlrecht_bund"
    config_file: str | None = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScraperConfig":
        """Create config from dictionary."""
        return cls(
            worker_name=data.get("worker_name", data.get("name", "")),
            institute_id=data.get("institute_id", ""),
            provider=data.get("provider", "Wahlrecht.de"),
            source=data.get("source", "html_scraper"),
            scope=data.get("scope", "federal"),
            election_id=data.get("election_id", "Bundestagswahl"),
            method_id=data.get("method_id", "99"),
            urls=data.get("urls", []),
            type=data.get("type", "wahlrecht_bund"),
            config_file=data.get("config_file"),
        )


class ScraperRegistry:
    """Registry for scraper classes."""

    _registry: Dict[str, Type] = {}

    @classmethod
    def register(cls, type_name: str):
        """Decorator to register a scraper class."""

        def decorator(scraper_class: Type) -> Type:
            cls._registry[type_name] = scraper_class
            scraper_class.type_name = type_name
            return scraper_class

        return decorator

    @classmethod
    def get(cls, type_name: str) -> Type | None:
        """Get scraper class by type name."""
        return cls._registry.get(type_name)

    @classmethod
    def list_types(cls) -> List[str]:
        """List all registered type names."""
        return list(cls._registry.keys())
