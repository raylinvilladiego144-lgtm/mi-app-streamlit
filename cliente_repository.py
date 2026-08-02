"""
app/repositories/cliente_repository.py

Repositorio para la gestión de acceso a datos de la entidad Cliente.
Soporta multitenancy / aislamiento de datos por usuario.
"""

from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.cliente import (
    Cliente,
    EstadoCliente,
)


class ClienteRepository:
    """
    Repositorio de operaciones sobre la entidad Cliente isoladas por usuario.
    """

    def __init__(self, db: Session):
        self.db = db

    # ==========================================================
    # CREAR
    # ==========================================================

    def crear(
        self,
        cliente: Cliente,
        usuario_actual: str = "admin",
    ) -> Cliente:
        """
        Guarda un nuevo cliente asignándolo al usuario activo.
        """
        cliente.usuario = usuario_actual

        self.db.add(cliente)
        self.db.commit()
        self.db.refresh(cliente)

        return cliente

    # ==========================================================
    # CONSULTAS
    # ==========================================================

    def obtener_por_id(
        self,
        cliente_id: int,
        usuario_actual: str = "admin",
    ) -> Optional[Cliente]:
        """
        Busca un cliente por ID asegurando que pertenezca al usuario activo.
        """
        return (
            self.db.query(Cliente)
            .filter(
                Cliente.id == cliente_id,
                Cliente.usuario == usuario_actual,
            )
            .first()
        )

    def obtener_por_documento(
        self,
        documento: str,
        usuario_actual: str = "admin",
    ) -> Optional[Cliente]:
        """
        Busca un cliente por documento dentro de los registros del usuario activo.
        """
        return (
            self.db.query(Cliente)
            .filter(
                Cliente.documento == documento,
                Cliente.usuario == usuario_actual,
            )
            .first()
        )

    def buscar(
        self,
        termino: str,
        usuario_actual: str = "admin",
    ) -> List[Cliente]:
        """
        Busca clientes por nombre, documento o teléfono pertenecientes al usuario activo.
        """
        filtro = f"%{termino}%"

        return (
            self.db.query(Cliente)
            .filter(
                Cliente.usuario == usuario_actual,
                or_(
                    Cliente.nombre_completo.ilike(filtro),
                    Cliente.documento.ilike(filtro),
                    Cliente.telefono.ilike(filtro),
                ),
            )
            .order_by(Cliente.nombre_completo.asc())
            .all()
        )

    def listar_todos(
        self,
        usuario_actual: str = "admin",
    ) -> List[Cliente]:
        """
        Retorna todos los clientes pertenecientes al usuario activo.
        """
        return (
            self.db.query(Cliente)
            .filter(Cliente.usuario == usuario_actual)
            .order_by(Cliente.nombre_completo.asc())
            .all()
        )

    def listar_activos(
        self,
        usuario_actual: str = "admin",
    ) -> List[Cliente]:
        """
        Retorna únicamente los clientes activos del usuario en sesión.
        """
        return (
            self.db.query(Cliente)
            .filter(
                Cliente.usuario == usuario_actual,
                Cliente.estado == EstadoCliente.ACTIVO,
            )
            .order_by(Cliente.nombre_completo.asc())
            .all()
        )

    # ==========================================================
    # ACTUALIZAR
    # ==========================================================

    def actualizar(
        self,
        cliente: Cliente,
    ) -> Cliente:
        """
        Guarda los cambios realizados sobre un cliente.
        """
        self.db.commit()
        self.db.refresh(cliente)

        return cliente

    # ==========================================================
    # ELIMINAR
    # ==========================================================

    def eliminar(
        self,
        cliente: Cliente,
    ) -> None:
        """
        Elimina un cliente.
        """
        self.db.delete(cliente)
        self.db.commit()