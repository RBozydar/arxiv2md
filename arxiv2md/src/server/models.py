"""Pydantic models for the query form."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from server.server_config import MAX_FILE_SIZE_KB

# needed for type checking (pydantic)
if TYPE_CHECKING:
    from server.form_types import IntForm, OptStrForm, StrForm


class SectionFilterMode(str, Enum):
    """Enumeration for section filtering modes."""

    INCLUDE = "include"
    EXCLUDE = "exclude"


PatternType = SectionFilterMode


class IngestRequest(BaseModel):
    """Request model for the /api/ingest endpoint.

    Attributes
    ----------
    input_text : str
        The arXiv URL or ID to ingest.
    remove_refs : bool
        Remove references section from the output.
    remove_toc : bool
        Remove table of contents from the output.
    section_filter_mode : SectionFilterMode
        Section filtering mode (include or exclude).
    sections : list[str]
        Section titles to include or exclude.
    max_file_size : int | None
        Deprecated: retained for compatibility with gitingest UI.
    pattern_type : SectionFilterMode | None
        Deprecated: retained for compatibility with gitingest UI.
    pattern : str
        Deprecated: retained for compatibility with gitingest UI.
    token : str | None
        Deprecated: retained for compatibility with gitingest UI.

    """

    model_config = ConfigDict(extra="allow")

    input_text: str = Field(..., description="arXiv URL or ID to ingest")
    remove_refs: bool = Field(default=False, description="Remove references from output")
    remove_toc: bool = Field(default=False, description="Remove table of contents from output")
    section_filter_mode: SectionFilterMode = Field(
        default=SectionFilterMode.EXCLUDE,
        description="Section filtering mode",
    )
    sections: list[str] = Field(default_factory=list, description="Section titles to include or exclude")

    max_file_size: int | None = Field(
        default=None,
        ge=1,
        le=MAX_FILE_SIZE_KB,
        description="Deprecated: file size in KB",
    )
    pattern_type: SectionFilterMode | None = Field(
        default=None,
        description="Deprecated: pattern type",
    )
    pattern: str = Field(default="", description="Deprecated: pattern string")
    token: str | None = Field(default=None, description="Deprecated: GitHub token")

    @field_validator("input_text")
    @classmethod
    def validate_input_text(cls, v: str) -> str:
        """Validate that ``input_text`` is not empty."""
        if not v.strip():
            err = "input_text cannot be empty"
            raise ValueError(err)
        return v.strip()

    @field_validator("sections", mode="before")
    @classmethod
    def normalize_sections(cls, v: str | list[str] | None) -> list[str]:
        """Normalize section inputs from comma-separated strings or lists."""
        if not v:
            return []
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return [item.strip() for item in v if item.strip()]

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, v: str) -> str:
        """Validate ``pattern`` field."""
        return v.strip()


class IngestSuccessResponse(BaseModel):
    """Success response model for the /api/ingest endpoint.

    Attributes
    ----------
    arxiv_id : str | None
        The arXiv identifier.
    version : str | None
        The arXiv version string, if present.
    title : str | None
        The paper title.
    source_url : str | None
        The canonical URL for the arXiv abstract.
    summary : str
        Summary of the ingestion process including token estimates.
    digest_url : str
        URL to download the full digest content from the local cache.
    tree : str
        Section tree structure of the paper.
    sections_tree : str | None
        Section tree structure (alias for tree).
    content : str
        Processed markdown content.
    remove_refs : bool | None
        Whether references were removed.
    remove_toc : bool | None
        Whether the table of contents was removed.
    section_filter_mode : str | None
        Section filtering mode.
    sections : list[str] | None
        Sections included or excluded.
    repo_url : str | None
        Deprecated: original repository URL.
    short_repo_url : str | None
        Deprecated: short form of repository URL.
    default_max_file_size : int | None
        Deprecated: file size slider position used.
    pattern_type : str | None
        Deprecated: pattern type used for filtering.
    pattern : str | None
        Deprecated: pattern used for filtering.

    """

    arxiv_id: str | None = Field(default=None, description="arXiv identifier")
    version: str | None = Field(default=None, description="arXiv version")
    title: str | None = Field(default=None, description="Paper title")
    source_url: str | None = Field(default=None, description="Canonical arXiv abstract URL")
    summary: str = Field(..., description="Ingestion summary with token estimates")
    digest_url: str = Field(..., description="URL to download the full digest content")
    tree: str = Field(..., description="Section tree structure")
    sections_tree: str | None = Field(default=None, description="Section tree structure (alias)")
    content: str = Field(..., description="Processed markdown content")
    remove_refs: bool | None = Field(default=None, description="References removed")
    remove_toc: bool | None = Field(default=None, description="TOC removed")
    section_filter_mode: str | None = Field(default=None, description="Section filter mode")
    sections: list[str] | None = Field(default=None, description="Sections included or excluded")
    repo_url: str | None = Field(default=None, description="Deprecated: original repository URL")
    short_repo_url: str | None = Field(default=None, description="Deprecated: short repository URL")
    default_max_file_size: int | None = Field(default=None, description="Deprecated: file size slider position used")
    pattern_type: str | None = Field(default=None, description="Deprecated: pattern type used")
    pattern: str | None = Field(default=None, description="Deprecated: pattern used")


class IngestErrorResponse(BaseModel):
    """Error response model for the /api/ingest endpoint.

    Attributes
    ----------
    error : str
        Error message describing what went wrong.

    """

    error: str = Field(..., description="Error message")


# Union type for API responses
IngestResponse = Union[IngestSuccessResponse, IngestErrorResponse]


class QueryForm(BaseModel):
    """Form data for the query.

    Attributes
    ----------
    input_text : str
        Text or URL supplied in the form.
    remove_refs : bool
        Remove references section from the output.
    remove_toc : bool
        Remove table of contents from the output.
    section_filter_mode : str
        Section filtering mode.
    sections : str
        Comma-separated section titles to include or exclude.
    max_file_size : int | None
        Deprecated: maximum allowed file size for the input.
    pattern_type : str | None
        Deprecated: pattern type used in gitingest.
    pattern : str
        Deprecated: pattern string used in gitingest.
    token : str | None
        Deprecated: GitHub personal access token (PAT).

    """

    input_text: str
    remove_refs: bool = False
    remove_toc: bool = False
    section_filter_mode: str = SectionFilterMode.EXCLUDE.value
    sections: str = ""
    max_file_size: int | None = None
    pattern_type: str | None = None
    pattern: str = ""
    token: str | None = None

    @classmethod
    def as_form(
        cls,
        input_text: StrForm,
        max_file_size: IntForm,
        pattern_type: StrForm,
        pattern: StrForm,
        token: OptStrForm,
    ) -> QueryForm:
        """Create a QueryForm from FastAPI form parameters.

        Parameters
        ----------
        input_text : StrForm
            The input text provided by the user.
        max_file_size : IntForm
            Deprecated: max file size from gitingest UI.
        pattern_type : StrForm
            Deprecated: pattern type from gitingest UI.
        pattern : StrForm
            Deprecated: pattern string from gitingest UI.
        token : OptStrForm
            Deprecated: GitHub token from gitingest UI.

        Returns
        -------
        QueryForm
            The QueryForm instance.

        """
        return cls(
            input_text=input_text,
            max_file_size=max_file_size,
            pattern_type=pattern_type,
            pattern=pattern,
            token=token,
        )
