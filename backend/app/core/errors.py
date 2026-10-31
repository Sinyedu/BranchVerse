"""Domain errors. Each carries an HTTP status and a safe, user-facing message."""


class BranchVerseError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class InvalidInput(BranchVerseError):
    status_code = 400
    code = "invalid_input"


class NotFound(BranchVerseError):
    status_code = 404
    code = "not_found"


class NoRepository(BranchVerseError):
    status_code = 409
    code = "no_repository"


class GitUnavailable(BranchVerseError):
    status_code = 503
    code = "git_unavailable"


class GitTimeout(BranchVerseError):
    status_code = 504
    code = "git_timeout"


class GitOutputTooLarge(BranchVerseError):
    status_code = 413
    code = "output_too_large"


class GitCommandError(BranchVerseError):
    status_code = 500
    code = "git_error"


class Busy(BranchVerseError):
    status_code = 409
    code = "busy"
