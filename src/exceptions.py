"""Errores propios del recomendador. Los de arranque deben ser claros y fatales."""


class ChefWiseError(Exception):
    """Base de los errores del dominio."""


class DatasetNotFoundError(ChefWiseError, FileNotFoundError):
    """No existe el CSV procesado de recetas."""


class DatasetSchemaError(ChefWiseError, ValueError):
    """El CSV no tiene las columnas obligatorias."""


class ArtifactNotFoundError(ChefWiseError, FileNotFoundError):
    """Falta un artefacto del modelo (vectorizador o matriz TF-IDF)."""


class ArtifactMismatchError(ChefWiseError, ValueError):
    """Los artefactos del modelo no corresponden al CSV cargado."""


class RecipeNotFoundError(ChefWiseError, LookupError):
    """El recipe_id solicitado no existe en el dataset."""
