"""What a Go file publishes for the others (`HttpResult.publish`), and what it leaves waiting on them (`Pending`)."""

from __future__ import annotations

from typing import NamedTuple


class SwaggerBase(NamedTuple):
    """go-swagger's `embedded_spec.go`: the spec's `basePath`, by the spec's directory."""
    base_path: str


class SwaggerRoute(NamedTuple):
    """A go-swagger route, relative to the `basePath` of the spec in `spec_dir`."""
    spec_dir: str


class Encoder(NamedTuple):
    """A go-kit request encoder: the path it sets, by `<package directory>:<function>`."""
    path: str


class EncodedCall(NamedTuple):
    """A go-kit client whose path its encoder sets, by `<package directory>:<function>`."""
    encoder: str
