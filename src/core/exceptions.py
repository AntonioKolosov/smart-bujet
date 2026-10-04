class BaseSmartBujetError(Exception):
    pass

class NotFoundError(BaseSmartBujetError):
    pass

class AuthError(BaseSmartBujetError):
    pass

class ValidationError(BaseSmartBujetError):
    pass

class TransactionParseError(BaseSmartBujetError):
    def __init__(self, message: str, raw_text: str | None = None):
        super().__init__(message)
        self.raw_text = raw_text

class InvalidTransactionAmountError(TransactionParseError):
    pass

class OffTopicMessageError(TransactionParseError):
    pass

