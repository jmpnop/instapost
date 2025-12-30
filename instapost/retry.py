"""Retry utilities with exponential backoff for API calls."""

import time
import logging
from functools import wraps
from typing import Callable, Any, Tuple, Type
import requests

logger = logging.getLogger(__name__)


class RetryError(Exception):
    """Raised when all retry attempts are exhausted."""
    pass


def exponential_backoff_retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (requests.exceptions.RequestException,),
    retryable_status_codes: Tuple[int, ...] = (429, 500, 502, 503, 504)
):
    """Decorator for retrying functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        backoff_factor: Multiplier for delay after each retry
        retryable_exceptions: Tuple of exception types to retry
        retryable_status_codes: HTTP status codes that should trigger retry

    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except retryable_exceptions as e:
                    last_exception = e

                    # Check if it's a requests exception with a response
                    if hasattr(e, 'response') and e.response is not None:
                        status_code = e.response.status_code

                        # Don't retry on non-retryable status codes
                        if status_code not in retryable_status_codes:
                            logger.error(f"{func.__name__}: Non-retryable error (status {status_code})")
                            raise

                        # Special handling for rate limiting
                        if status_code == 429:
                            # Check for Retry-After header
                            retry_after = e.response.headers.get('Retry-After')
                            if retry_after:
                                try:
                                    delay = float(retry_after)
                                    logger.warning(f"{func.__name__}: Rate limited, waiting {delay}s")
                                except ValueError:
                                    pass

                    # Last attempt failed
                    if attempt >= max_retries:
                        logger.error(f"{func.__name__}: All {max_retries} retries exhausted")
                        raise RetryError(f"Failed after {max_retries} retries: {str(last_exception)}") from last_exception

                    # Wait before retrying
                    actual_delay = min(delay, max_delay)
                    logger.warning(
                        f"{func.__name__}: Attempt {attempt + 1}/{max_retries} failed. "
                        f"Retrying in {actual_delay:.1f}s... Error: {str(e)}"
                    )
                    time.sleep(actual_delay)
                    delay *= backoff_factor

                except Exception as e:
                    # Non-retryable exception
                    logger.error(f"{func.__name__}: Non-retryable exception: {type(e).__name__}")
                    raise

            # Should never reach here
            if last_exception:
                raise last_exception

        return wrapper
    return decorator


def retry_instagram_operation(func: Callable) -> Callable:
    """Specialized retry decorator for Instagram API operations.

    Handles:
    - Network errors
    - Rate limiting (429)
    - Server errors (500, 502, 503, 504)
    - Media not ready errors (specific to Instagram)
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        max_retries = 5
        delay = 2.0
        last_exception = None

        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)

            except ValueError as e:
                error_str = str(e)
                last_exception = e

                # Check for Instagram-specific errors
                is_retryable = any([
                    'Media Not Found' in error_str,
                    'media not ready' in error_str.lower(),
                    'error_subcode' in error_str and '2207027' in error_str,  # Media not ready
                    'error_subcode' in error_str and '2207006' in error_str,  # Media not found
                ])

                # Check for network/server errors
                if not is_retryable and hasattr(e, '__cause__'):
                    cause = e.__cause__
                    is_retryable = isinstance(cause, (
                        requests.exceptions.ConnectionError,
                        requests.exceptions.Timeout,
                        requests.exceptions.RequestException
                    ))

                if not is_retryable:
                    logger.error(f"{func.__name__}: Non-retryable error")
                    raise

                if attempt >= max_retries - 1:
                    logger.error(f"{func.__name__}: All {max_retries} retries exhausted")
                    raise RetryError(f"Failed after {max_retries} retries: {error_str}") from e

                # Wait with exponential backoff
                logger.warning(
                    f"{func.__name__}: Attempt {attempt + 1}/{max_retries} failed. "
                    f"Retrying in {delay:.1f}s... Error: {error_str[:100]}"
                )
                time.sleep(delay)
                delay *= 1.5

            except requests.exceptions.RequestException as e:
                last_exception = e

                if attempt >= max_retries - 1:
                    logger.error(f"{func.__name__}: All {max_retries} retries exhausted")
                    raise RetryError(f"Failed after {max_retries} retries: {str(e)}") from e

                logger.warning(
                    f"{func.__name__}: Network error on attempt {attempt + 1}/{max_retries}. "
                    f"Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
                delay *= 1.5

        if last_exception:
            raise last_exception

    return wrapper
