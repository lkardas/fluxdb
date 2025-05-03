from .admin import start_admin_server

class AdminServer:
    """Manages the web admin server for the database."""
    
    def __init__(self, db_path: str, host: str, port: int, debugweb: bool):
        self.db_path = db_path
        self.host = host
        self.port = port
        self.debugweb = debugweb

    def start(self) -> None:
        """
        Starts the web admin server.

        Args:
            None

        Raises:
            None
        """
        start_admin_server(self.db_path, self.host, self.port, self.debugweb)
