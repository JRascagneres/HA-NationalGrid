from homeassistant.exceptions import HomeAssistantError


class NationalGridError(HomeAssistantError):
    """Base error"""


class InvalidAuthError(NationalGridError):
    """Invalid auth"""


class UnexpectedDataError(NationalGridError):
    """Unexpected data"""
