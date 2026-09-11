from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ProblemDetailException(Exception):
    def __init__(
        self,
        status_code: int,
        title: str,
        detail: str,
        type_url: str = "about:blank",
        extras: dict[str, Any] | None = None,
    ):
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.type_url = type_url
        self.extras = extras or {}
        super().__init__(detail)


def rfc7807_response(
    request: Request,
    status_code: int,
    title: str,
    detail: str,
    type_url: str = "about:blank",
    extras: dict[str, Any] | None = None,
) -> JSONResponse:
    content: dict[str, Any] = {
        "type": type_url,
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": request.url.path,
    }
    if extras:
        content.update(extras)
    return JSONResponse(
        status_code=status_code,
        content=content,
        headers={"Content-Type": "application/problem+json"},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemDetailException)
    async def problem_detail_handler(request: Request, exc: ProblemDetailException) -> JSONResponse:
        return rfc7807_response(
            request=request,
            status_code=exc.status_code,
            title=exc.title,
            detail=exc.detail,
            type_url=exc.type_url,
            extras=exc.extras,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = str(exc.detail) if exc.detail else "An HTTP error occurred"
        return rfc7807_response(
            request=request,
            status_code=exc.status_code,
            title=exc.detail if isinstance(exc.detail, str) else "HTTP Error",
            detail=detail,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return rfc7807_response(
            request=request,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Validation Error",
            detail="Request input validation failed",
            type_url="https://errors.legalmetro.gov.in/validation-error",
            extras={"errors": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return rfc7807_response(
            request=request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail=str(exc) if app.debug else "An unexpected internal server error occurred",
            type_url="https://errors.legalmetro.gov.in/internal-error",
        )
