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
        Crea y registra un nuevo cliente en la base de datos usando las 
        columnas exactas del modelo (nombre_completo, documento, etc.).
        """
        cliente_data = {
            "nombre_completo": nombre,  # Mapea 'nombre' al campo real 'nombre_completo'
            "documento": documento,     # Incluye el documento obligatorio del modelo
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
        Si la tabla no cuenta con la columna 'usuario', retorna todos los registros.
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
