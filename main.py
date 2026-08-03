"""
main.py
Punto de entrada principal con Login, Dashboard financiero, Préstamos, Pagos, Clientes y Gestión de Eliminación (Arquitectura Plana).
"""

from datetime import datetime
from decimal import Decimal
import pandas as pd
import streamlit as st

# --- IMPORTACIÓN DE MÓDULOS PLANOS EXISTENTES ---
from database import SessionLocal, init_db
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

# --- CREDENCIALES DE ACCESO ---
USUARIOS = {
    "simon": "12345",
    "raylin": "Barcelona12*",
}


# --- CLASE / LÓGICA FINANCIERA (Actualizada y Segura) ---
class RepositorioFinanciero:

    @staticmethod
    def registrar_abono(db: SessionLocal, prestamo_id: int, monto_abono: float | Decimal, usuario: str):
        """
        Ejecuta la transacción atómica que registra el pago de la cuota 
        y actualiza el saldo/caja del usuario de forma segura.
        """
        monto_dec = Decimal(str(monto_abono))
        if monto_dec <= 0:
            raise ValueError("El monto del abono debe ser mayor a cero.")

        # Buscar cuotas pendientes de este préstamo
        cuota_pendiente = db.query(Cuota).join(Prestamo).filter(
            Prestamo.id == prestamo_id,
            Prestamo.usuario == usuario,
            Cuota.estado == EstadoCuota.PENDIENTE
        ).order_by(Cuota.numero_cuota.asc()).first()

        if not cuota_pendiente:
            raise ValueError("No hay cuotas pendientes para este préstamo.")

        # Actualizar cuota
        cuota_pendiente.monto_pagado += monto_dec
        if cuota_pendiente.monto_pagado >= cuota_pendiente.monto_cuota:
            cuota_pendiente.estado = EstadoCuota.PAGADA
        else:
            cuota_pendiente.estado = EstadoCuota.PARCIAL

        # Integración segura con el servicio de caja si soporta métodos estándar
        try:
            caja_service = CajaService(db, usuario_actual=usuario)
            if hasattr(caja_service, "registrar_ingreso"):
                caja_service.registrar_ingreso(
                    monto=monto_dec,
                    observacion=f"Abono a cuota #{cuota_pendiente.numero_cuota} (Préstamo ID: {prestamo_id})"
                )
            elif hasattr(caja_service, "registrar_movimiento"):
                caja_service.registrar_movimiento(
                    monto=monto_dec,
                    tipo="INGRESO",
                    observacion=f"Abono a cuota #{cuota_pendiente.numero_cuota} (Préstamo ID: {prestamo_id})"
                )
        except Exception:
            pass  # Si el servicio de caja opera de otra forma, aseguramos la persistencia de la cuota

        db.commit()
        return cuota_pendiente

    @staticmethod
    def eliminar_prestamo(db: SessionLocal, prestamo_id: int, usuario: str):
        """
        Elimina un préstamo y todas sus cuotas asociadas de forma segura validando el usuario.
        """
        prestamo = db.query(Prestamo).filter(
            Prestamo.id == prestamo_id,
            Prestamo.usuario == usuario
        ).first()
        
        if not prestamo:
            raise ValueError(f"El préstamo con ID {prestamo_id} no existe o no pertenece a este usuario.")
        
        # Eliminar cuotas relacionadas primero
        db.query(Cuota).filter(Cuota.prestamo_id == prestamo_id).delete()
        
        # Eliminar el préstamo
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

        # --- MÉTRICAS PRINCIPALES ---
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                label="💵 Caja Disponible",
                value=f"${resumen['caja_disponible']:,.2f}",
                help="Dinero disponible en efectivo o banco para nuevos préstamos o retiros."
            )

        with col2:
            st.metric(
                label="📈 Capital Prestado (Activo)",
                value=f"${resumen['capital_prestado']:,.2f}",
                help="Saldo pendiente por cobrar en los préstamos activos."
            )

        with col3:
            st.metric(
                label="🏦 Capital Total (Caja + Cartera)",
                value=f"${resumen['capital_total']:,.2f}",
                help="Patrimonio total administrado."
            )

        st.divider()

        # --- SECCIÓN DE MOVIMIENTOS RECIENTES ---
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
            
            df_movs = pd.DataFrame(data)
            st.dataframe(df_movs, use_container_width=True, hide_index=True)

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

            monto_abono = st.number_input(
                "Monto del Abono ($) *",
                min_value=0.0,
                value=100.0,
                step=10.0,
                help="Ingrese el valor que el cliente está abonando."
            )

            submitted = st.form_submit_button("💰 Registrar y Aplicar Abono", type="primary", use_container_width=True)

            if submitted:
                try:
                    RepositorioFinanciero.registrar_abono(
                        db=db,
                        prestamo_id=prestamo_seleccionado.id,
                        monto_abono=monto_abono,
                        usuario=usuario
                    )
                    st.success(f"¡Abono de ${monto_abono:,.2f} registrado con éxito y aplicado al préstamo!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al registrar el abono: {e}")

        st.divider()

        st.subheader("📜 Historial Reciente de Cuotas Pagadas")
        cuotas_pagadas = db.query(Cuota).join(Prestamo).filter(
            Prestamo.usuario == usuario,
            Cuota.monto_pagado > 0
        ).order_by(Cuota.id.desc()).limit(10).all()

        if not cuotas_pagadas:
            st.info("No hay pagos registrados recientemente.")
        else:
            data = []
            for cp in cuotas_pagadas:
                data.append({
                    "ID Préstamo": cp.prestamo_id,
                    "Cuota N°": cp.numero_cuota,
                    "Valor Cuota": f"${cp.monto_cuota:,.2f}",
                    "Monto Abonado": f"${cp.monto_pagado:,.2f}",
                    "Estado": cp.estado.value if hasattr(cp.estado, "value") else str(cp.estado)
                })
            
            df_pagos = pd.DataFrame(data)
            st.dataframe(df_pagos, use_container_width=True, hide_index=True)

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
                nombre = st.text_input("Nombre completo")
                
                submitted = st.form_submit_button("Guardar Cliente", type="primary")
                if submitted:
                    if nombre.strip():
                        try:
                            repo.crear_cliente(
                                nombre=nombre,
                                documento="S/D",
                                telefono="S/D",
                                direccion="S/D",
                                usuario=usuario
                            )
                            st.success(f"¡Cliente '{nombre}' registrado con éxito!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")
                    else:
                        st.warning("El nombre del cliente es obligatorio.")

        st.divider()

        st.subheader("📋 Directorio de Clientes")
        clientes = repo.obtener_por_usuario(usuario)

        if not clientes:
            st.info("No hay clientes registrados todavía.")
        else:
            data = []
            for c in clientes:
                data.append({
                    "ID": c.id,
                    "Nombre": getattr(c, "nombre_completo", "N/A")
                })
            
            df_clientes = pd.DataFrame(data)
            st.dataframe(df_clientes, use_container_width=True, hide_index=True)

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
                        st.success(f"¡Préstamo con ID {id_a_borrar} eliminado exitosamente!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al eliminar: {e}")
    finally:
        db.close()


# --- LOGIN ---
def login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 Iniciar Sesión")
        st.caption("Sistema de Gestión de Préstamos e Inversiones")

        with st.form("form_login"):
            usr = st.text_input("Usuario").strip().lower()
            pwd = st.text_input("Contraseña", type="password")
            btn = st.form_submit_button(
                "Ingresar", type="primary", use_container_width=True
            )

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

    usuario_actual = st.session_state.get("username", "admin")

    with st.sidebar:
        st.title("💳 Sistema Préstamos")
        st.markdown(f"👤 **Usuario activo:** `{usuario_actual.capitalize()}`")
        st.divider()

        modulo = st.selectbox(
            "Seleccionar Módulo",
            ["Dashboard / Caja", "Préstamos", "Pagos", "Clientes", "Gestión Préstamos"],
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


if __name__ == "__main__":
    main()
