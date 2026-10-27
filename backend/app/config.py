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
    clerk_audience: str | None = None

    @field_validator("cors_origins")
    @classmethod
    def clean_cors_origins(cls, origins: list[str] | None) -> list[str] | None:
        return (
            [origin.strip() for origin in origins if origin.strip()]
            if origins
            else origins
        )

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
                ("CLERK_AUDIENCE", self.clerk_audience),
            ):
                if not value or not value.strip():
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
                or jwks.scheme != "https"
                or not jwks.hostname
                or jwks.username
                or jwks.password
            ):
                raise ValueError("CLERK_JWKS_URL must be an HTTPS URL")
        if any(
            (self.clerk_jwks_url, self.clerk_issuer, self.clerk_audience)
        ) and not all((self.clerk_jwks_url, self.clerk_issuer, self.clerk_audience)):
            raise ValueError(
                "Clerk issuer, audience, and JWKS URL must be configured together"
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
        try:
            addresses = {
                ipaddress.ip_address(result[4][0])
                for result in socket.getaddrinfo(
                    self.bind_host, None, type=socket.SOCK_STREAM
                )
            }
        except (OSError, ValueError):
            return False
        return bool(addresses) and all(address.is_loopback for address in addresses)


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
