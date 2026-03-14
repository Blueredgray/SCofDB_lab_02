"""Доменные исключения."""


class DomainException(Exception):
    """Базовое исключение."""

    pass


class InvalidEmailError(DomainException):
    """Неверный формат email."""

    def __init__(self, email: str):
        self.email = email
        super().__init__(f"Invalid email format: {email}")


class OrderAlreadyPaidError(DomainException):
    """Заказ уже оплачен."""

    def __init__(self, order_id):
        self.order_id = order_id
        super().__init__(f"Order {order_id} already paid")


class OrderCancelledError(DomainException):
    """Заказ отменён."""

    def __init__(self, order_id):
        self.order_id = order_id
        super().__init__(f"Order {order_id} is cancelled")


class InvalidQuantityError(DomainException):
    """Неверное количество."""

    def __init__(self, quantity: int):
        self.quantity = quantity
        super().__init__(f"Quantity must be positive, got: {quantity}")


class InvalidPriceError(DomainException):
    """Неверная цена."""

    def __init__(self, price):
        self.price = price
        super().__init__(f"Price cannot be negative, got: {price}")


class InvalidAmountError(DomainException):
    """Неверная сумма."""

    def __init__(self, amount):
        self.amount = amount
        super().__init__(f"Amount cannot be negative, got: {amount}")


class UserNotFoundError(DomainException):
    """Пользователь не найден."""

    def __init__(self, user_id):
        self.user_id = user_id
        super().__init__(f"User {user_id} not found")


class OrderNotFoundError(DomainException):
    """Заказ не найден."""

    def __init__(self, order_id):
        self.order_id = order_id
        super().__init__(f"Order {order_id} not found")


class EmailAlreadyExistsError(DomainException):
    """Email уже существует."""

    def __init__(self, email: str):
        self.email = email
        super().__init__(f"Email already exists: {email}")
