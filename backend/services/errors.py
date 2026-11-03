from typing import Optional


class ServiceError(Exception):
    status_code = 500

    def __init__(self, detail: str, status_code: Optional[int] = None):
        super().__init__(detail)
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code
