from typing import Callable, List, Dict
from .exceptions import TransactionError

class TransactionManager:
    """Manages database transactions, including begin, commit, and rollback operations."""
    
    def __init__(self):
        self.transaction_active = False
        self.transaction_buffer: List[Dict] = []

    def begin_transaction(self) -> None:
        """
        Begins a transaction.

        Raises:
            TransactionError: If a transaction is already active.
        """
        if self.transaction_active:
            raise TransactionError("Transaction already active")
        self.transaction_active = True
        self.transaction_buffer = []

    def commit(self, buffer_manager) -> None:
        """
        Commits a transaction.

        Args:
            buffer_manager: The buffer manager to flush after commit.

        Raises:
            TransactionError: If no transaction is active or commit fails.
        """
        if not self.transaction_active:
            raise TransactionError("No active transaction")
        try:
            for op in self.transaction_buffer:
                op['func'](*op['args'], **op['kwargs'])
            self.transaction_buffer = []
            self.transaction_active = False
            buffer_manager.flush_buffer()
        except Exception as e:
            self.rollback()
            raise TransactionError(f"Failed to commit transaction: {e}")

    def rollback(self) -> None:
        """
        Rolls back a transaction.

        Raises:
            TransactionError: If no transaction is active.
        """
        if not self.transaction_active:
            raise TransactionError("No active transaction to roll back")
        self.transaction_buffer = []
        self.transaction_active = False

    def add_to_transaction(self, func: Callable, *args, **kwargs) -> None:
        """
        Adds an operation to a transaction or executes it immediately.

        Args:
            func (Callable): The function to execute.
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.
        """
        if self.transaction_active:
            self.transaction_buffer.append({'func': func, 'args': args, 'kwargs': kwargs})
        else:
            func(*args, **kwargs)
