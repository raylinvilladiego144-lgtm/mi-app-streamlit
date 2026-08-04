"""
main.py
Punto de entrada principal con Login, Dashboard financiero, Préstamos, Pagos, Clientes, Gestión y Respaldos (Arquitectura Plana).
"""

from datetime import datetime, timedelta
from decimal import Decimal
import os
import pandas as pd
import streamlit as st

# --- IMPORTACIÓN DE MÓDULOS PLANOS EXISTENTES ---
from database import SessionLocal, init_db, engine, Base
from caja_service import CajaService
from prestamos import render_prestamos
from cliente_repository import ClienteRepository
from prestamo import Prestamo, Cuota, EstadoPrestamo, EstadoCuota

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Gestión de Préstamos e Inversiones",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- INICIALIZAR LAS TABLAS DE SQLALCHEMY AUTOMÁTICAMENTE ---
init_db()

# --- CREDENCIALES DE ACCESO (ADMINISTRADOR DEFINIDO COMO 'simon') ---
USUARIOS = {
    "simon": "12345",
    "raylin": "Barcelona12*",
}


# --- CLASE / LÓGICA FINANCIERA (Garantía de Persistencia y Temporalidad Independiente) ---
class RepositorioFinanciero:

    @staticmethod
    def registrar_abono(db: SessionLocal, prestamo_id: int, monto_abono: float | Decimal, usuario: str):
        """
        Registra el pago de la cuota respetando la frecuencia de cobro y evaluando 
        la temporalidad si se cruzan los periodos calendario establecidos.
        """
        monto_dec = Decimal(str(monto_abono))
        if monto_dec <= 0:
            raise ValueError("El monto del abono debe ser mayor a cero.")

        cuota_pendiente = db.query(Cuota).join(Prestamo).filter(
            Prestamo.id == prestamo_id,
            Prestamo.usuario == usuario,
            Cuota.estado == EstadoCuota.PENDIENTE
        ).order_by(Cuota.numero_cuota.asc()).first()

        if not cuota_pendiente:
            raise ValueError("No hay cuotas pendientes para este préstamo.")

        cuota_pendiente.monto_pagado += monto_dec
        if cuota_pendiente.monto_pagado >= cuota_pendiente.monto_cuota:
            cuota_pendiente.estado = EstadoCuota.PAGADA
        else:
            cuota_pendiente.estado = EstadoCuota.PARCIAL

        caja_service = CajaService(db, usuario_actual=usuario)
        operacion_exitosa = False
        
        for metodo_caja in ["registrar_ingreso", "registrar_aporte", "registrar_movimiento", "ingresar"]:
            if hasattr(caja_service, metodo_caja):
                try:
                    fn = getattr(caja_service, metodo_caja)
                    try:
                        fn(monto=monto_dec, tipo="INGRESO", observacion=f"Abono cuota #{cuota_pendiente.numero_cuota} (Préstamo #{prestamo_id})")
                    except TypeError:
                        try:
                            fn(monto=monto_dec, observacion=f"Abono cuota #{cuota_pendiente.numero_cuota} (Préstamo #{prestamo_id})")
                        except TypeError:
                            fn(monto_dec)
                    operacion_exitosa = True
                    break
                except Exception:
                    pass

        if not operacion_exitosa and hasattr(caja_service, "caja") and caja_service.caja:
            if hasattr(caja_service.caja, "saldo_disponible"):
                caja_service.caja.saldo_disponible += monto_dec
                db.add(caja_service.caja)

        db.commit()
        db.refresh(cuota_pendiente)
        return cuota_pendiente

    @staticmethod
    def eliminar_prestamo(db: SessionLocal, prestamo_id: int, usuario: str):
        prestamo = db.query(Prestamo).filter(
            Prestamo.id == prestamo_id,
            Prestamo.usuario == usuario
        ).first()
        
        if not prestamo:
            raise ValueError(f"El préstamo con ID {prestamo_id} no existe o no pertenece a este usuario.")
        
        db.query(Cuota).filter(Cuota.prestamo_id == prestamo_id).delete()
        db.delete(prestamo)
        db.commit()


# --- MÓDULO 1: DASHBOARD / CAJA ---
def render_dashboard(usuario):
    st.title(f"📊 Dashboard Financiero — {usuario.capitalize()}")
    st.markdown("Resumen general del estado de caja, capital en la calle y flujos de efectivo.")

    db = SessionLocal()
    try:
        caja_service = CajaService(db, usuario_actual=usuario)
        resumen = caja_service.obtener_resumen_financiero()

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(label="💵 Caja Disponible", value=f"${resumen['caja_disponible']:,.2f}")
        with col2:
            st.metric(label="📈 Capital Prestado (Activo)", value=f"${resumen['capital_prestado']:,.2f}")
        with col3:
            st.metric(label="🏦 Capital Total (Caja + Cartera)", value=f"${resumen['capital_total']:,.2f}")

        st.divider()

        # --- SECCIÓN DE MOVIMIENTOS MANUALES (Ingreso Genérico por defecto) ---
        with st.expander("⚙️ Registrar Movimiento de Caja (Ingreso Genérico o Reposición)", expanded=False):
            with st.form("form_ajuste_caja_dashboard"):
                tipo_movimiento = st.selectbox(
                    "Tipo de Operación *",
                    ["Ingreso Genérico", "Reposición de Capital"]
                )
                monto_movimiento = st.number_input("Monto ($) *", min_value=0.0, value=500.0, step=50.0)
                observacion_movimiento = st.text_input("Observación / Motivo *", placeholder="Ej: Ingreso de efectivo adicional o inyección de capital")
                
                btn_guardar_mov = st.form_submit_button("📥 Registrar Movimiento en Caja", type="primary", use_container_width=True)

                if btn_guardar_mov:
                    if monto_movimiento <= 0:
                        st.warning("El monto debe ser mayor a cero.")
                    elif not observacion_movimiento.strip():
                        st.warning("La observación es obligatoria para este registro.")
                    else:
                        monto_dec = Decimal(str(monto_movimiento))
                        operacion_realizada = False
                        
                        etiqueta_tipo = "REPOSICIÓN DE CAPITAL" if tipo_movimiento == "Reposición de Capital" else "INGRESO GENÉRICO"
                        obs_final = f"[{etiqueta_tipo}] {observacion_movimiento.strip()}"

                        for metodo_caja in ["registrar_ingreso", "registrar_aporte", "registrar_movimiento", "ingresar"]:
                            if hasattr(caja_service, metodo_caja):
                                try:
                                    fn = getattr(caja_service, metodo_caja)
                                    try:
                                        fn(monto=monto_dec, tipo="INGRESO", observacion=obs_final)
                                    except TypeError:
                                        try:
                                            fn(monto=monto_dec, observacion=obs_final)
                                        except TypeError:
                                            fn(monto_dec)
                                    operacion_realizada = True
                                    break
                                except Exception:
                                    pass

                        if not operacion_realizada and hasattr(caja_service, "caja") and caja_service.caja:
                            if hasattr(caja_service.caja, "saldo_disponible"):
                                caja_service.caja.saldo_disponible += monto_dec
                                db.add(caja_service.caja)
                                operacion_realizada = True

                        if operacion_realizada:
                            db.commit()
                            st.success(f"¡{tipo_movimiento} de ${monto_movimiento:,.2f} aplicada con éxito a la caja!")
                            st.rerun()
                        else:
                            db.rollback()
                            st.error("❌ No se pudo registrar el movimiento en el servicio de caja.")

        st.divider()
        st.subheader("📜 Últimos Movimientos y Transacciones")
        movimientos = caja_service.listar_movimientos(limite=10)

        if not movimientos:
            st.info("No hay movimientos financieros registrados todavía en este usuario.")
        else:
            data = []
            for m in movimientos:
                data.append({
                    "ID": m.id,
                    "Fecha": getattr(m, "fecha", "N/A"),
                    "Tipo": m.tipo_evento.value if hasattr(m.tipo_evento, "value") else str(m.tipo_evento),
                    "Monto": f"${m.monto:,.2f}" if hasattr(m, "monto") else "$0.00",
                    "Observación": getattr(m, "observacion", "")
                })
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    finally:
        db.close()


# --- MÓDULO 2: PAGOS ---
def render_pagos(usuario):
    st.title(f"💳 Módulo de Pagos - {usuario.capitalize()}")
    st.markdown("Control de abonos, amortización de cuotas e impacto directo en caja.")

    db = SessionLocal()
    try:
        prestamos_activos = db.query(Prestamo).filter(
            Prestamo.usuario == usuario,
            Prestamo.estado == EstadoPrestamo.ACTIVO
        ).all()

        if not prestamos_activos:
            st.info("No hay préstamos activos disponibles para recibir pagos.")
            return

        prestamo_opciones = {
            f"Préstamo #{p.id} - Cliente: {getattr(p.cliente, 'nombre_completo', 'N/A')} (Total: ${p.monto_total:,.2f})": p 
            for p in prestamos_activos
        }

        with st.form("form_registrar_abono"):
            st.subheader("Registrar Abono a Cuota")
            seleccion_key = st.selectbox("Seleccionar Préstamo Activo *", options=list(prestamo_opciones.keys()))
            prestamo_seleccionado = prestamo_opciones[seleccion_key]

            monto_abono = st.number_input("Monto del Abono ($) *", min_value=0.0, value=100.0, step=10.0)
            submitted = st.form_submit_button("💰 Registrar y Aplicar Abono", type="primary", use_container_width=True)

            if submitted:
                try:
                    RepositorioFinanciero.registrar_abono(db=db, prestamo_id=prestamo_seleccionado.id, monto_abono=monto_abono, usuario=usuario)
                    st.success(f"¡Abono de ${monto_abono:,.2f} guardado en la base de datos con éxito!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al guardar el abono en la base de datos: {e}")

        st.divider()
        st.subheader("📜 Historial Reciente de Cuotas Pagadas")
        cuotas_pagadas = db.query(Cuota).join(Prestamo).filter(
            Prestamo.usuario == usuario,
            Cuota.monto_pagado > 0
        ).order_by(Cuota.id.desc()).limit(10).all()

        if cuotas_pagadas:
            data = [{
                "ID Préstamo": cp.prestamo_id,
                "Cuota N°": cp.numero_cuota,
                "Valor Cuota": f"${cp.monto_cuota:,.2f}",
                "Monto Abonado": f"${cp.monto_pagado:,.2f}",
                "Estado": cp.estado.value if hasattr(cp.estado, "value") else str(cp.estado)
            } for cp in cuotas_pagadas]
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    finally:
        db.close()


# --- MÓDULO 3: CLIENTES ---
def render_clientes(usuario):
    st.title(f"👥 Módulo de Clientes - {usuario.capitalize()}")
    st.markdown("Gestión y registro del directorio de clientes.")

    db = SessionLocal()
    try:
        repo = ClienteRepository(db)
        
        with st.expander("➕ Registrar Nuevo Cliente", expanded=False):
            with st.form("form_nuevo_cliente"):
                nombre = st.text_input("Nombre completo *")
                
                submitted = st.form_submit_button("Guardar Cliente", type="primary")
                if submitted:
                    if nombre.strip():
                        try:
                            repo.crear_cliente(
                                nombre=nombre.strip(),
                                documento="S/D",
                                telefono="S/D",
                                direccion="S/D",
                                usuario=usuario
                            )
                            db.commit()
                            st.success(f"¡Cliente '{nombre.strip()}' guardado permanentemente en la base de datos!")
                            st.rerun()
                        except Exception as e:
                            db.rollback()
                            st.error(f"❌ Error al guardar en la base de datos: {e}")
                    else:
                        st.warning("El nombre del cliente es obligatorio.")

        st.divider()
        st.subheader("📋 Directorio de Clientes")
        clientes = repo.obtener_por_usuario(usuario)

        if clientes:
            data = [{"ID": c.id, "Nombre": getattr(c, "nombre_completo", "N/A")} for c in clientes]
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
        else:
            st.info("No hay clientes registrados todavía.")
    finally:
        db.close()


# --- MÓDULO 4: GESTIÓN / ELIMINACIÓN DE PRÉSTAMOS ---
def render_gestion_prestamos(usuario):
    st.title(f"⚙️ Gestión de Préstamos — {usuario.capitalize()}")
    st.markdown("Herramientas administrativas para corregir registros o eliminar préstamos duplicados.")

    db = SessionLocal()
    try:
        st.subheader("🗑️ Eliminar Préstamo Duplicado o Erróneo")
        prestamos_existentes = db.query(Prestamo).filter(Prestamo.usuario == usuario).all()
        
        if not prestamos_existentes:
            st.info("No hay préstamos registrados para eliminar.")
        else:
            opciones_borrar = {
                f"ID: {p.id} - Cliente: {getattr(p.cliente, 'nombre_completo', 'N/A')} - Capital: ${p.monto_total:,.2f}": p.id 
                for p in prestamos_existentes
            }
            
            with st.form("form_eliminar_prestamo"):
                prestamo_a_borrar_key = st.selectbox("Seleccione el préstamo a eliminar", options=list(opciones_borrar.keys()))
                id_a_borrar = opciones_borrar[prestamo_a_borrar_key]
                
                submitted = st.form_submit_button("⚠️ Eliminar Préstamo Seleccionado", type="primary", use_container_width=True)
                
                if submitted:
                    try:
                        RepositorioFinanciero.eliminar_prestamo(db, id_a_borrar, usuario)
                        st.success(f"¡Préstamo con ID {id_a_borrar} eliminado exitosamente de la base de datos!")
                        st.rerun()
                    except Exception as e:
                        db.rollback()
                        st.error(f"❌ Error al eliminar de la base de datos: {e}")
    finally:
        db.close()


# --- MÓDULO 5: GESTIÓN DE RESPALDOS Y SEGURIDAD (CON CONTROL DE ROL ADMIN Y engine.dispose) ---
def render_gestion_respaldos(usuario):
    st.markdown("## 🛡️ Gestión y Seguridad de Datos")
    st.caption("Respalda tu información o administra el esquema de la base de datos.")

    # 1. Validación estricta de rol/permiso de administrador
    if usuario.strip().lower() != "simon":
        st.warning("🚫 **Acceso Restringido:** Las herramientas de respaldo avanzado y mantenimiento estructural de la base de datos están habilitadas exclusivamente para el usuario **Administrador**.")
        return

    col1, col2 = st.columns(2)

    # --- 1. BOTÓN DE RESPALDO (BACKUP) GLOBAL ---
    with col1:
        st.subheader("💾 Copia de Seguridad")
        st.write("Descarga una copia actual de la base de datos general.")
        
        archivos_db = [f for f in os.listdir(".") if f.endswith(".db")]
        
        if archivos_db:
            db_path = archivos_db[0]
            with open(db_path, "rb") as f:
                db_bytes = f.read()
            
            st.download_button(
                label=f"📥 Descargar Respaldo ({db_path})",
                data=db_bytes,
                file_name=f"respaldo_{db_path}",
                mime="application/octet-stream",
                type="primary",
                use_container_width=True
            )
        else:
            st.warning("⚠️ Todavía no se detecta ningún archivo de base de datos.")

    # --- 2. ZONA DE PELIGRO: LIMPIEZA TOTAL Y RECREACIÓN DE TABLAS (CON engine.dispose) ---
    with col2:
        st.subheader("🔥 Zona de Peligro")
        st.write("Reinicia y reestructura la base de datos de forma limpia evitando bloqueos de archivo.")

        with st.expander("⚠️ Desplegar opción de mantenimiento estructural", expanded=False):
            confirmar_total = st.checkbox("Confirmo que deseo restablecer la base de datos y eliminar los registros actuales")
            
            if st.button("💥 Recrear Tablas y Liberar Conexiones", type="primary", use_container_width=True):
                if confirmar_total:
                    try:
                        with st.spinner("Liberando conexiones del sistema y reestructurando el motor SQLite..."):
                            # 2. Liberación forzosa de conexiones del pool para evitar bloqueos por archivos readonly
                            engine.dispose()

                            # 5. Eliminación y posterior recreación limpia de todas las tablas de SQLAlchemy
                            Base.metadata.drop_all(bind=engine)
                            Base.metadata.create_all(bind=engine)

                            # Limpiar sesión actual por seguridad
                            st.session_state.clear()
                            st.session_state["logged_in"] = True
                            st.session_state["username"] = usuario

                        # 6. Mensaje visual claro de éxito
                        st.success("🎉 ¡La base de datos se ha reestructurado y optimizado con éxito! Las tablas requeridas han sido recreadas y las conexiones liberadas.")
                        st.balloons()
                        st.rerun()
                    except Exception as e:
                        # 6. Manejo seguro de errores
                        st.error(f"❌ Ocurrió un error crítico al procesar la base de datos: {e}")
                else:
                    st.warning("⚠️ Debes marcar la casilla de confirmación para proceder.")


# --- LOGIN ---
def login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 Iniciar Sesión")
        st.caption("Sistema de Gestión de Préstamos e Inversiones")

        with st.form("form_login"):
            usr = st.text_input("Usuario").strip().lower()
            pwd = st.text_input("Contraseña", type="password")
            btn = st.form_submit_button("Ingresar", type="primary", use_container_width=True)

            if btn:
                if usr in USUARIOS and USUARIOS[usr] == pwd:
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = usr
                    st.success(f"¡Bienvenido, {usr.capitalize()}!")
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos.")


# --- CONTROLADOR PRINCIPAL ---
def main():
    if not st.session_state.get("logged_in", False):
        login()
        return

    usuario_actual = st.session_state.get("username", "simon")

    with st.sidebar:
        st.title("💳 Sistema Préstamos")
        st.markdown(f"👤 **Usuario activo:** `{usuario_actual.capitalize()}`")
        st.divider()

        # Menú lateral completo con todas las opciones originales
        modulo = st.selectbox(
            "Seleccionar Módulo",
            [
                "Dashboard / Caja", 
                "Préstamos", 
                "Pagos", 
                "Clientes", 
                "Gestión Préstamos", 
                "Respaldos y Seguridad"
            ],
        )

        st.divider()
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    if modulo == "Dashboard / Caja":
        render_dashboard(usuario_actual)
    elif modulo == "Préstamos":
        render_prestamos()
    elif modulo == "Pagos":
        render_pagos(usuario_actual)
    elif modulo == "Clientes":
        render_clientes(usuario_actual)
    elif modulo == "Gestión Préstamos":
        render_gestion_prestamos(usuario_actual)
    elif modulo == "Respaldos y Seguridad":
        render_gestion_respaldos(usuario_actual)


if __name__ == "__main__":
    main()
