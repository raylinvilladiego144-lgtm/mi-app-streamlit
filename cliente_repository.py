"""
cliente_repository.py
Repositorio para la gestión de operaciones de base de datos para Clientes.
"""

from sqlalchemy.orm import Session
from cliente import Cliente


class ClienteRepository:
    """
    Repositorio encargado de interactuar con la tabla de clientes en la base de datos.
    """

    def __init__(self, db: Session):
        self.db = db

    def crear_cliente(
        self,
        nombre: str,
        telefono: str,
        direccion: str | None = None,
        documento: str = "S/D",
        usuario: str = "admin",
    ) -> Cliente:
        """
        Crea y registra un nuevo cliente en la base de datos.
        """
        cliente_data = {
            "nombre_completo": nombre,
            "documento": documento,
            "telefono": telefono,
            "direccion": direccion,
        }
        
        if hasattr(Cliente, "usuario"):
            cliente_data["usuario"] = usuario

        nuevo_cliente = Cliente(**cliente_data)

        self.db.add(nuevo_cliente)
        self.db.commit()
        self.db.refresh(nuevo_cliente)

        return nuevo_cliente

    def obtener_por_usuario(self, usuario: str) -> list[Cliente]:
        """
        Obtiene la lista de clientes filtrados por el usuario actual.
        """
        query = self.db.query(Cliente)
        if hasattr(Cliente, "usuario"):
            query = query.filter(Cliente.usuario == usuario)
        return query.all()

    def obtener_todos(self) -> list[Cliente]:
        """
        Retorna todos los clientes registrados en el sistema.
        """
        return self.db.query(Cliente).all()

    def listar_todos(self) -> list[Cliente]:
        """
        Alias de compatibilidad para que prestamos.py pueda listar los clientes sin errores.
        """
        return self.obtener_todos()
