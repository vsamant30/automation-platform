from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.schemas.api_response import ApiErrorResponse


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    return JSONResponse(
        status_code=422,
        content=ApiErrorResponse(
            success=False,
            message="Validation failed.",
            errors=exc.errors(),
        ).model_dump(),
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception,
):
    return JSONResponse(
        status_code=500,
        content=ApiErrorResponse(
            success=False,
            message="Internal server error.",
            errors=[str(exc)],
        ).model_dump(),
    )