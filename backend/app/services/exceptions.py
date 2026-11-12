class EmailAlreadyExistsError(Exception):
    pass

class UserNotFoundError(Exception):
    pass

class NotFoundError(Exception):
    pass
class ExistingMemberError(Exception):
    pass

class NotOwnerError(Exception):
    pass

class OwnershipRuleViolationError(Exception):
    pass