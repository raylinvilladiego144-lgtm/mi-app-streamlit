"""
reparar_cuotas_infladas.py

Ejecutar UNA SOLA VEZ, después de la migración y de reemplazar los archivos
corregidos, para devolver a su valor correcto cualquier cuota que haya sido
inflada por el bug del recálculo repetido.

Qué hace:
- Para cada préstamo ACTIVO, recalcula el monto_total y el valor de cuota
  correctos a partir del capital y la tasa de interés (que nunca se dañaron).
- Solo corrige cuotas NO pagadas (PENDIENTE o PARCIAL) cuyo monto no coincide
  con el valor correcto. Las cuotas ya PAGADAS no se tocan (su dinero ya
  entró y no debe alterarse).
- Imprime un resumen de qué préstamos/cuotas corrigió, sin aplicar nada
  todavía (modo simulación) a menos que confirmes.

Uso:  python reparar_cuotas_infladas.py
"""
from decimal import Decimal
from database import SessionLocal
from prestamo import Prestamo, EstadoPrestamo, EstadoCuota

db = SessionLocal()
cambios = []

try:
    prestamos = db.query(Prestamo).filter(Prestamo.estado == EstadoPrestamo.ACTIVO).all()

    for p in prestamos:
        capital = p.capital or Decimal("0.00")
        tasa = (p.porcentaje_interes or Decimal("0.00")) / Decimal("100")
        monto_total_correcto = capital + (capital * tasa)
        valor_cuota_correcto = monto_total_correcto / Decimal(str(p.numero_cuotas))

        prestamo_afectado = False

        for c in p.cuotas:
            if c.estado == EstadoCuota.PAGADA:
                continue  # nunca tocar cuotas ya pagadas

            diferencia = (c.monto_cuota or Decimal("0.00")) - valor_cuota_correcto
            if abs(diferencia) > Decimal("0.01"):
                cambios.append(
                    f"Préstamo #{p.id} ({p.cliente.nombre_completo if p.cliente else '?'}) "
                    f"- Cuota #{c.numero_cuota}: ${c.monto_cuota} -> ${valor_cuota_correcto:.2f}"
                )
                c.monto_cuota = valor_cuota_correcto
                c.ultimo_recalculo = None  # limpia la marca para que no quede huérfana
                prestamo_afectado = True

        if prestamo_afectado:
            cambios.append(f"Préstamo #{p.id}: monto_total ${p.monto_total} -> ${monto_total_correcto:.2f}")
            p.monto_total = monto_total_correcto

    if not cambios:
        print("No se encontraron cuotas infladas. No hay nada que corregir.")
    else:
        print("Se van a aplicar los siguientes cambios:\n")
        for linea in cambios:
            print(" -", linea)

        respuesta = input("\n¿Aplicar estos cambios a la base de datos? (si/no): ").strip().lower()
        if respuesta == "si":
            db.commit()
            print("\nOK: cambios aplicados.")
        else:
            db.rollback()
            print("\nCancelado: no se modificó nada.")

finally:
    db.close()
