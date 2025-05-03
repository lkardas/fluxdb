from .admin import AdminServer

class AdminServerWrapper:
    """Manages the web admin server for the database."""
    
    def __init__(self, db_path: str, host: str, port: int, debugweb: bool):
        self.server = AdminServer(db_path, host, port, debugweb)

    def start(self) -> None:
        """
        Starts the web admin server.

        Args:
            None

        Raises:
            None
        """
        self.server.start()
