from decimal import Decimal
from sqlalchemy.orm import Session
from caja_service import CajaService
from evento import TipoEvento

def obtener_caja_manager(db: Session, usuario: str = "admin"):
    """
    Factoría para obtener una instancia del servicio de caja.
    """
    return CajaService(db, usuario_actual=usuario)

def procesar_abono_cuota(db: Session, monto: float, prestamo_id: int, cliente_id: int):
    """
    Función de conveniencia para registrar pagos.
    """
    service = obtener_caja_manager(db)
    observacion = f"Pago de cuota - Prestamo #{prestamo_id} - Cliente #{cliente_id}"
    
    return service.registrar_pago_cuota(Decimal(str(monto)), observacion)

def procesar_aporte_capital(db: Session, monto: float, fuente: str):
    """
    Función de conveniencia para registrar aportes externos.
    """
    service = obtener_caja_manager(db)
    observacion = f"Aporte de capital externo: {fuente}"
    
    return service.registrar_aporte(Decimal(str(monto)), observacion)

def consultar_estado_caja(db: Session):
    """
    Retorna el resumen financiero actual.
    """
    service = obtener_caja_manager(db)
    return service.obtener_resumen_financiero()
