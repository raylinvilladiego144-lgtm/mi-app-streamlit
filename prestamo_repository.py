from decimal import Decimal
from sqlalchemy.orm import Session
from prestamo import Prestamo, Cuota, EstadoPrestamo, EstadoCuota


class PrestamoRepository:
    def __init__(self, db: Session):
        self.db = db

    def listar_activos(self):
        return self.db.query(Prestamo).filter(
            Prestamo.estado.in_([EstadoPrestamo.ACTIVO, EstadoPrestamo.VENCIDO])
        ).all()

    def obtener_por_id(self, prestamo_id: int):
        return self.db.query(Prestamo).filter(Prestamo.id == prestamo_id).first()

    def guardar(self, prestamo: Prestamo):
        self.db.add(prestamo)
        self.db.commit()
        self.db.refresh(prestamo)
        return prestamo
