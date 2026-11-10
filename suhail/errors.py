"""Exception hierarchy. The UI maps these to user-facing (Arabic) messages."""


class SuhailError(Exception):
    """Base class for all expected, handled errors."""


class ConfigError(SuhailError):
    """Invalid or missing configuration."""


class ModelNotFoundError(SuhailError):
    """The local LLM weights file is missing."""


class IndexMismatchError(SuhailError):
    """The vector index was built with a different embedding model."""


class RegistryError(SuhailError):
    """The document registry on disk could not be read."""


class IngestionError(SuhailError):
    """Base class for problems while ingesting a document."""


class UnsupportedFileTypeError(IngestionError):
    pass


class FileTooLargeError(IngestionError):
    pass


class ExtractionError(IngestionError):
    """The file is corrupt or could not be parsed."""


class EmptyDocumentError(IngestionError):
    """No extractable text (e.g. a scanned PDF without a text layer)."""
