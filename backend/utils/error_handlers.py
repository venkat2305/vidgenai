from fastapi import Request
from fastapi.responses import JSONResponse
import logging
import traceback

logger = logging.getLogger("vidgenai.error_handlers")


async def handle_exception(request: Request, exc: Exception) -> JSONResponse:
    # Log the exception
    logger.error(f"Exception for {request.url}: {str(exc)}")
    logger.error(traceback.format_exc())

    # Determine status code based on exception type
    status_code = 500

    if hasattr(exc, "status_code"):
        status_code = exc.status_code

    # Create error response
    error_response = {
        "error": True,
        "message": str(exc),
        "path": str(request.url.path)
    }

    return JSONResponse(
        status_code=status_code,
        content=error_response
    )
