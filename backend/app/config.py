import ipaddress
import socket
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, SettingsError


class ConfigurationError(ValueError):
    """Raised when application settings are invalid, without exposing their values."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    app_mode: Literal["local", "hosted"] = "local"
    app_env: str = "production"
    local_auth_bypass: bool = False
    database_url: SecretStr | None = None
    cors_origins: list[str] | None = None
    host: str | None = None
    port: int = Field(default=8000, gt=0, le=65535)
    max_upload_bytes: int = Field(default=1024 * 1024, gt=0)
    benchmark_enabled: bool = False
    benchmark_timeout_seconds: float = Field(default=3600, gt=0, allow_inf_nan=False)
    clerk_jwks_url: str | None = None
    clerk_issuer: str | None = None
    clerk_authorized_parties: list[str] | None = None

    @field_validator("cors_origins")
    @classmethod
    def clean_cors_origins(cls, origins: list[str] | None) -> list[str] | None:
        return (
            [origin.strip() for origin in origins if origin.strip()]
            if origins
            else origins
        )

    @field_validator("clerk_authorized_parties")
    @classmethod
    def clean_clerk_authorized_parties(
        cls, parties: list[str] | None
    ) -> list[str] | None:
        if not parties:
            return parties
        cleaned: list[str] = []
        for party in parties:
            origin = party.strip()
            if not origin:
                continue
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"https", "http"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("CLERK_AUTHORIZED_PARTIES must contain origins only")
            cleaned.append(f"{parsed.scheme}://{parsed.netloc}")
        return cleaned

    @model_validator(mode="after")
    def validate_hosted_settings(self) -> "Settings":
        if self.local_auth_bypass and (
            self.app_env != "development"
            or self.app_mode != "local"
            or not self.bind_host_is_loopback
        ):
            raise ValueError(
                "LOCAL_AUTH_BYPASS requires APP_ENV=development, APP_MODE=local, "
                "and a loopback HOST"
            )
        if self.app_mode == "local" and self.host and not self.bind_host_is_loopback:
            raise ValueError("Non-loopback HOST requires APP_MODE=hosted")
        if self.app_mode == "hosted":
            missing = []
            if (
                self.database_url is None
                or not self.database_url.get_secret_value().strip()
            ):
                missing.append("DATABASE_URL")
            if not self.cors_origins:
                missing.append("CORS_ORIGINS")
            if not self.host or not self.host.strip():
                missing.append("HOST")
            for name, value in (
                ("CLERK_JWKS_URL", self.clerk_jwks_url),
                ("CLERK_ISSUER", self.clerk_issuer),
                ("CLERK_AUTHORIZED_PARTIES", self.clerk_authorized_parties),
            ):
                if isinstance(value, list):
                    if not value:
                        missing.append(name)
                elif not value or not value.strip():
                    missing.append(name)
            if missing:
                raise ValueError(f"Required in hosted mode: {', '.join(missing)}")
            database_url = self.database_url.get_secret_value()
            try:
                database = urlsplit(database_url)
            except ValueError:
                database = None
            if (
                database is None
                or database.scheme not in {"postgres", "postgresql"}
                or not database.hostname
            ):
                raise ValueError(
                    "DATABASE_URL must be a PostgreSQL URL with a host in hosted mode"
                )
            if self.cors_origins and any("*" in origin for origin in self.cors_origins):
                raise ValueError(
                    "CORS_ORIGINS must not contain a wildcard in hosted mode"
                )
        if self.clerk_jwks_url:
            try:
                jwks = urlsplit(self.clerk_jwks_url)
            except ValueError:
                jwks = None
            if (
                jwks is None
                or jwks.scheme not in {"https", "http"}
                or not jwks.hostname
                or jwks.username
                or jwks.password
            ):
                raise ValueError("CLERK_JWKS_URL must be a valid HTTPS URL")
            if jwks.scheme == "http" and (
                self.app_env != "test"
                or self.app_mode != "local"
                or not self.bind_host_is_loopback
                or not resolved_loopback_addresses(jwks.hostname)
            ):
                raise ValueError(
                    "HTTP CLERK_JWKS_URL requires APP_ENV=test, APP_MODE=local, "
                    "and loopback-only HOST and JWKS resolution"
                )
        if any(
            (self.clerk_jwks_url, self.clerk_issuer, self.clerk_authorized_parties)
        ) and not all(
            (self.clerk_jwks_url, self.clerk_issuer, self.clerk_authorized_parties)
        ):
            raise ValueError(
                "Clerk issuer, authorized parties, and JWKS URL must be configured together"
            )
        return self

    @property
    def cors_allow_origins(self) -> list[str]:
        if self.cors_origins is not None:
            return self.cors_origins
        return ["*"] if self.app_mode == "local" else []

    @property
    def bind_host(self) -> str:
        return self.host or "127.0.0.1"

    @property
    def bind_host_is_loopback(self) -> bool:
        return bool(resolved_loopback_addresses(self.bind_host))

    @property
    def test_local_http_jwks(self) -> bool:
        if (
            not self.clerk_jwks_url
            or self.app_env != "test"
            or self.app_mode != "local"
        ):
            return False
        try:
            jwks = urlsplit(self.clerk_jwks_url)
        except ValueError:
            return False
        return (
            jwks.scheme == "http"
            and bool(jwks.hostname)
            and self.bind_host_is_loopback
            and bool(resolved_loopback_addresses(jwks.hostname))
        )


def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as error:
        issues = error.errors(include_input=False, include_context=False)
        fields = sorted(
            {str(part).upper() for issue in issues for part in issue["loc"]}
        )
        messages = [str(issue["msg"]) for issue in issues]
        context = ", ".join(fields) if fields else "; ".join(messages)
        message = f"Invalid application configuration: {context}"
        raise ConfigurationError(message) from None
    except SettingsError:
        raise ConfigurationError("Invalid application configuration") from None


def resolved_loopback_addresses(
    host: str,
) -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        addresses = {
            ipaddress.ip_address(result[4][0])
            for result in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        }
    except (OSError, ValueError):
        return set()
    return (
        addresses
        if addresses and all(address.is_loopback for address in addresses)
        else set()
    )
