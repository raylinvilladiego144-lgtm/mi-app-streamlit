"""
cliente_repository.py
Repositorio para la gestión de operaciones de base de datos para Clientes.
"""

from sqlalchemy import or_
from sqlalchemy.orm import Session
from cliente import Cliente


class ClienteRepository:
    """
    Repositorio encargado de interactuar con la tabla de clientes en la base de datos.

    IMPORTANTE: todas las consultas que devuelven listados aceptan (y deben recibir)
    el 'usuario' del admin que tiene la sesión activa, para que cada admin solo
    vea/edite los clientes que él mismo registró. Así, mientras un admin está
    inscribiendo un cliente, ese registro nunca aparece para los otros admins.
    """

    def __init__(self, db: Session):
        self.db = db

    def crear(self, cliente: Cliente) -> Cliente:
        """
        Inserta un objeto Cliente ya construido (usado por la pantalla de registro).
        """
        self.db.add(cliente)
        self.db.commit()
        self.db.refresh(cliente)
        return cliente

    def obtener_por_documento(self, documento: str, usuario: str | None = None) -> Cliente | None:
        """
        Busca un cliente por documento. Si se pasa 'usuario', la búsqueda de
        duplicados queda aislada a los clientes de ese mismo admin.
        """
        query = self.db.query(Cliente).filter(Cliente.documento == documento)
        if usuario and hasattr(Cliente, "usuario"):
            query = query.filter(Cliente.usuario == usuario)
        return query.first()

    def buscar_clientes(self, texto: str, usuario: str | None = None) -> list[Cliente]:
        """
        Busca por nombre o documento. Si se pasa 'usuario', solo busca dentro
        de los clientes registrados por ese admin (no ve los de los otros 2).
        """
        patron = f"%{texto.strip()}%"
        query = self.db.query(Cliente).filter(
            or_(
                Cliente.nombre_completo.ilike(patron),
                Cliente.documento.ilike(patron),
            )
        )
        if usuario and hasattr(Cliente, "usuario"):
            query = query.filter(Cliente.usuario == usuario)
        return query.all()

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
