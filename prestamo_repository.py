"""
prestamo_repository.py

Repositorio para la gestión de acceso a datos de
Préstamos, Cuotas y Eventos Financieros.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

# Importaciones corregidas para la estructura plana en la raíz
from models.prestamo import (
    Prestamo,
    Cuota,
    EstadoPrestamo,
)
from models.evento import (
    EventoFinanciero,
)


class PrestamoRepository:
    """
    Repositorio para operaciones de préstamos.
    """

    def __init__(self, db: Session):
        self.db = db

    # ==========================================================
    # PRÉSTAMOS
    # ==========================================================

    def crear_prestamo(
        self,
        prestamo: Prestamo,
    ) -> Prestamo:
        """
        Guarda un préstamo junto con sus cuotas.
        """
        self.db.add(prestamo)
        self.db.commit()
        self.db.refresh(prestamo)
        return prestamo

    def obtener_por_id(
        self,
        prestamo_id: int,
    ) -> Optional[Prestamo]:
        """
        Obtiene un préstamo por su ID.
        """
        return (
            self.db.query(Prestamo)
            .filter(
                Prestamo.id == prestamo_id
            )
            .first()
        )

    def obtener_activo_por_cliente(
        self,
        cliente_id: int,
    ) -> Optional[Prestamo]:
        """
        Retorna el préstamo activo de un cliente.
        """
        return (
            self.db.query(Prestamo)
            .filter(
                Prestamo.cliente_id == cliente_id,
                Prestamo.estado == EstadoPrestamo.ACTIVO,
            )
            .first()
        )

    def listar_activos(
        self,
    ) -> List[Prestamo]:
        """
        Lista todos los préstamos activos.
        """
        return (
            self.db.query(Prestamo)
            .filter(
                Prestamo.estado == EstadoPrestamo.ACTIVO
            )
            .all()
        )

    def actualizar_prestamo(
        self,
        prestamo: Prestamo,
    ) -> Prestamo:
        """
        Guarda cambios sobre un préstamo.
        """
        self.db.commit()
        self.db.refresh(prestamo)
        return prestamo

    # ==========================================================
    # CUOTAS
    # ==========================================================

    def obtener_cuota(
        self,
        cuota_id: int,
    ) -> Optional[Cuota]:
        """
        Obtiene una cuota por su ID.
        """
        return (
            self.db.query(Cuota)
            .filter(
                Cuota.id == cuota_id
            )
            .first()
        )

    def listar_cuotas_prestamo(
        self,
        prestamo_id: int,
    ) -> List[Cuota]:
        """
        Lista las cuotas de un préstamo.
        """
        return (
            self.db.query(Cuota)
            .filter(
                Cuota.prestamo_id == prestamo_id
            )
            .order_by(
                Cuota.numero_cuota
            )
            .all()
        )

    # ==========================================================
    # EVENTOS FINANCIEROS
    # ==========================================================

    def registrar_evento(
        self,
        evento: EventoFinanciero,
    ) -> EventoFinanciero:
        """
        Registra un evento financiero.
        """
        self.db.add(evento)
        self.db.commit()
        self.db.refresh(evento)
        return evento

    def listar_ultimos_eventos(
        self,
        limite: int = 10,
    ) -> List[EventoFinanciero]:
        """
        Obtiene los últimos movimientos registrados.
        """
        return (
            self.db.query(
                EventoFinanciero
            )
            .order_by(
                EventoFinanciero.creado_en.desc()
            )
            .limit(limite)
            .all()
        )
