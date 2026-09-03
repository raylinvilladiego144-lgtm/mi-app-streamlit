"""
migracion_ultimo_recalculo.py

Ejecutar UNA SOLA VEZ para agregar la columna 'ultimo_recalculo' a la tabla
'cuotas' en tu base de datos ya existente. No borra ni modifica ningún dato,
solo agrega una columna nueva (queda en NULL para todas las cuotas actuales).

Uso:  python migracion_ultimo_recalculo.py
"""
from sqlalchemy import text
from database import engine

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE cuotas ADD COLUMN ultimo_recalculo VARCHAR(20)"))
        conn.commit()
        print("OK: columna 'ultimo_recalculo' agregada a la tabla 'cuotas'.")
    except Exception as e:
        # Si ya existe la columna (por ejemplo si vuelves a correr el script
        # por error), no pasa nada grave.
        print(f"Aviso: {e}")
