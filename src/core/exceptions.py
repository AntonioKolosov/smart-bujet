class BaseSmartBujetError(Exception):
    pass

class NotFoundError(BaseSmartBujetError):
    pass

class AuthError(BaseSmartBujetError):
    pass

class ValidationError(BaseSmartBujetError):
    pass
