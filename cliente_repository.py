from sqlalchemy.orm import Session
from cliente import Cliente  # Asumiendo que tu modelo de cliente se llama cliente.py


class ClienteRepository:
    def __init__(self, db: Session):
        self.db = db

    def listar_todos(self):
        return self.db.query(Cliente).all()

    def obtener_por_id(self, cliente_id: int):
        return self.db.query(Cliente).filter(Cliente.id == cliente_id).first()
