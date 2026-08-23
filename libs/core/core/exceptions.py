"""Shared exception hierarchy. Module-specific exceptions extend these rather
than raising bare Exception, so failure classification (kernel.failure) can
pattern-match on type."""


class AgentOSError(Exception):
    """Base class for all Agent OS domain exceptions."""


class ValidationError(AgentOSError):
    pass


class NotFoundError(AgentOSError):
    pass


class ConfigurationError(AgentOSError):
    pass
