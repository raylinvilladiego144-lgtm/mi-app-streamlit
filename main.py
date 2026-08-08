from datetime import datetime, timedelta
from decimal import Decimal
import os
import math
import pandas as pd
import streamlit as st

# --- IMPORTACIÓN DE MÓDULOS PLANOS Y MOTOR DE BASE DE DATOS ---
from database import SessionLocal, init_db, engine
from base import Base
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
    "simon": "12345**",
    "raylin": "Barcelona12*",
    "luis": "123456",
}


# --- CLASE / LÓGICA FINANCIERA (Garantía de Persistencia y Temporalidad Independiente) ---
class RepositorioFinanciero:

    @staticmethod
    def registrar_abono(db: SessionLocal, prestamo_id: int, monto_abono: float | Decimal, usuario: str):
        """
        Distribuye de forma inteligente el monto abonado a través de las cuotas pendientes 
        en orden cronológico y registra el ingreso limpio en la caja.
        """
        monto_restante = Decimal(str(monto_abono))
        if monto_restante <= 0:
            raise ValueError("El monto del abono debe ser mayor a cero.")

        prestamo = db.query(Prestamo).filter(
            Prestamo.id == prestamo_id,
            Prestamo.usuario == usuario
        ).first()

        if not prestamo:
            raise ValueError("El préstamo seleccionado no existe o no pertenece al usuario activo.")

        cuotas_pendientes = db.query(Cuota).filter(
            Cuota.prestamo_id == prestamo_id,
            Cuota.estado.in_([EstadoCuota.PENDIENTE, EstadoCuota.PARCIAL])
        ).order_by(Cuota.numero_cuota.asc()).all()

        if not cuotas_pendientes:
            raise ValueError("No hay cuotas pendientes o parciales para este préstamo. ¡El crédito está totalmente al día o pagado!")

        cuotas_afectadas = []

        for cuota in cuotas_pendientes:
            if monto_restante <= 0:
                break

            saldo_pendiente_cuota = cuota.monto_cuota - cuota.monto_pagado

            if monto_restante >= saldo_pendiente_cuota:
                monto_restante -= saldo_pendiente_cuota
                cuota.monto_pagado = cuota.monto_cuota
                cuota.estado = EstadoCuota.PAGADA
            else:
                cuota.monto_pagado += monto_restante
                cuota.estado = EstadoCuota.PARCIAL
                monto_restante = Decimal("0.00")

            db.add(cuota)
            cuotas_afectadas.append(cuota.numero_cuota)

        # --- REGISTRO LIMPIO EN CAJA USANDO EL MÉTODO ESPECÍFICO ---
        caja_service = CajaService(db, usuario_actual=usuario)
        detalle_cuotas_str = ", ".join([str(c) for c in cuotas_afectadas])
        obs_caja = f"Pago distribuido en cuota(s) #{detalle_cuotas_str} (Préstamo #{prestamo_id})."

        # Llamada directa y sin ambigüedades al servicio de caja actualizado
        caja_service.registrar_pago_cuota(
            monto=Decimal(str(monto_abono)), 
            observacion=obs_caja
        )

        db.commit()
        return cuotas_afectadas

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

    @staticmethod
    def procesar_refinanciacion(db: SessionLocal, prestamo_id: int, nuevo_plazo: int, nueva_tasa: float, usuario: str):
        prestamo = db.query(Prestamo).filter(Prestamo.id == prestamo_id, Prestamo.usuario == usuario).first()
        if not prestamo:
            raise ValueError("El préstamo no existe o no pertenece al usuario.")
        
        cuotas_pendientes = db.query(Cuota).filter(
            Cuota.prestamo_id == prestamo_id,
            Cuota.estado.in_([EstadoCuota.PENDIENTE, EstadoCuota.PARCIAL])
        ).all()
        
        saldo_pendiente = sum([c.monto_cuota - c.monto_pagado for c in cuotas_pendientes])
        
        if saldo_pendiente <= 0:
            raise ValueError("El préstamo no tiene saldo pendiente para refinanciar.")

        for c in cuotas_pendientes:
            c.estado = EstadoCuota.PAGADA
            db.add(c)
        
        monto_nueva_cuota = saldo_pendiente / Decimal(str(nuevo_plazo))
        for i in range(1, nuevo_plazo + 1):
            nueva_cuota = Cuota(
                prestamo_id=prestamo.id,
                numero_cuota=i,
                monto_cuota=monto_nueva_cuota,
                monto_pagado=Decimal("0.00"),
                fecha_pago_esperada=datetime.now().date() + timedelta(days=i * 30),
                estado=EstadoCuota.PENDIENTE
            )
            db.add(nueva_cuota)
        
        db.commit()
        return True


# --- MÓDULO 1: DASHBOARD / CAJA ---
def render_dashboard(usuario):
    current_user = str(usuario or "admin").strip().lower()

    st.title(f"📊 Dashboard Financiero — {current_user.capitalize()}")
    st.markdown("Resumen general del estado de caja, capital en la calle y flujos de efectivo.")

    db = SessionLocal()
    try:
        caja_service = CajaService(db, usuario_actual=current_user)
        cliente_repo = ClienteRepository(db)

        resumen = caja_service.obtener_resumen_financiero()
        clientes = cliente_repo.obtener_por_usuario(current_user) if hasattr(cliente_repo, "obtener_por_usuario") else cliente_repo.listar_todos()
        
        prestamos_activos = db.query(Prestamo).filter(
            Prestamo.usuario == current_user,
            Prestamo.estado == EstadoPrestamo.ACTIVO
        ).all()

        total_clientes = len(clientes)
        clientes_activos = len([c for c in clientes if getattr(c, "estado", "ACTIVO") == "ACTIVO"])
        clientes_bloqueados = len([c for c in clientes if getattr(c, "estado", "") == "BLOQUEADO"])

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="💵 Caja Disponible", value=f"${resumen.get('caja_disponible', Decimal('0.00')):,.2f}")
        with col2:
            st.metric(label="📈 Capital Prestado (Activo)", value=f"${resumen.get('capital_prestado', Decimal('0.00')):,.2f}")
        with col3:
            st.metric(label="🏦 Capital Total (Caja + Cartera)", value=f"${resumen.get('capital_total', Decimal('0.00')):,.2f}")

        st.divider()

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("👥 Clientes", total_clientes)
        with c2:
            st.metric("✅ Activos", clientes_activos)
        with c3:
            st.metric("🚫 Bloqueados", clientes_bloqueados)
        with c4:
            st.metric("📄 Préstamos Activos", len(prestamos_activos))

        st.divider()

        st.subheader("📜 Últimos Movimientos y Transacciones")
        movimientos = caja_service.listar_movimientos(limite=10)

        if not movimientos:
            st.info("No hay movimientos financieros registrados todavía en este usuario.")
        else:
            data = []
            for m in movimientos:
                fila_mov = {
                    "ID": m.id,
                    "Fecha": getattr(m, "creado_en", None) or getattr(m, "fecha", "N/A"),
                    "Tipo": m.tipo_evento.value if hasattr(m.tipo_evento, "value") else str(m.tipo_evento),
                    "Monto": f"${m.monto:,.2f}" if hasattr(m, "monto") else "$0.00",
                    "Observación": getattr(m, "observacion", "")
                }
                data.append(fila_mov)
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    finally:
        db.close()


# --- MÓDULO 2: PAGOS ---
def render_pagos(usuario):
    st.title(f"💳 Módulo de Pagos - {usuario.capitalize()}")
    st.markdown("Control de abonos, amortización inteligente de cuotas y calendario de pagos.")

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

            monto_abono = st.number_input("Monto del Abono ($) *", min_value=0.0, value=25000.0, step=1000.0)
            submitted = st.form_submit_button("💰 Registrar y Aplicar Abono Inteligente", type="primary", use_container_width=True)

            if submitted:
                try:
                    cuotas_afectadas = RepositorioFinanciero.registrar_abono(
                        db=db, 
                        prestamo_id=prestamo_seleccionado.id, 
                        monto_abono=monto_abono, 
                        usuario=usuario
                    )
                    st.success(f"¡Abono de ${monto_abono:,.2f} aplicado con éxito al préstamo #{prestamo_seleccionado.id}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al registrar el abono en la base de datos: {e}")

        st.divider()
        st.subheader("📅 Calendario de Cuotas (Diseño Matricial)")
        
        prestamo_calendario_key = st.selectbox(
            "Seleccionar Préstamo para Ver Calendario", 
            options=list(prestamo_opciones.keys()),
            key="select_calendario_prestamo"
        )
        prestamo_cal = prestamo_opciones[prestamo_calendario_key]

        cuotas_prestamo = db.query(Cuota).filter(Cuota.prestamo_id == prestamo_cal.id).order_by(Cuota.numero_cuota.asc()).all()
        mapa_cuotas = {c.numero_cuota: c for c in cuotas_prestamo}

        st.markdown("""
            <style>
            .cuota-box {
                background-color: #ffeb3b;
                border: 1px solid #cddc39;
                padding: 8px;
                text-align: center;
                border-radius: 4px;
                color: #000000;
                font-weight: bold;
                margin-bottom: 6px;
            }
            .cuota-box-pagada {
                background-color: #d4edda;
                border: 1px solid #c3e6cb;
                padding: 8px;
                text-align: center;
                border-radius: 4px;
                color: #155724;
                font-weight: bold;
                margin-bottom: 6px;
            }
            .cuota-box-libre {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                padding: 8px;
                text-align: center;
                border-radius: 4px;
                color: #6c757d;
                font-weight: bold;
                margin-bottom: 6px;
            }
            </style>
        """, unsafe_allow_html=True)

        total_cuotas_cal = int(getattr(prestamo_cal, "numero_cuotas", None) or len(cuotas_prestamo) or 0)
        columnas_por_fila = 6
        filas_necesarias = math.ceil(total_cuotas_cal / columnas_por_fila) if total_cuotas_cal > 0 else 0

        if total_cuotas_cal == 0:
            st.info("ℹ️ Este préstamo no tiene cuotas generadas.")

        for fila in range(filas_necesarias):
            cols = st.columns(columnas_por_fila)
            for col_idx in range(columnas_por_fila):
                num_espacio = (fila * columnas_por_fila) + col_idx + 1
                if num_espacio > total_cuotas_cal:
                    continue

                with cols[col_idx]:
                    cuota_obj = mapa_cuotas.get(num_espacio)
                    
                    if cuota_obj:
                        estado_str = cuota_obj.estado.value if hasattr(cuota_obj.estado, "value") else str(cuota_obj.estado)
                        monto_pagado = float(cuota_obj.monto_pagado)
                        monto_cuota = float(cuota_obj.monto_cuota)
                        
                        if estado_str == "PAGADA" or monto_pagado >= monto_cuota:
                            st.markdown(f'<div class="cuota-box-pagada">C{num_espacio}<br>${monto_pagado:,.0f}</div>', unsafe_allow_html=True)
                        elif monto_pagado > 0:
                            st.markdown(f'<div class="cuota-box" style="background-color: #fff3cd;">C{num_espacio}<br>Parcial: ${monto_pagado:,.0f}</div>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<div class="cuota-box">C{num_espacio}<br>${monto_cuota:,.0f}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="cuota-box-libre">C{num_espacio}<br>Sin datos</div>', unsafe_allow_html=True)

        st.divider()
        st.subheader("📜 Historial Reciente de Cuotas Pagadas")
        cuotas_pagadas = db.query(Cuota).join(Prestamo).filter(
            Prestamo.usuario == usuario,
            Cuota.monto_pagado > 0
        ).order_by(Cuota.id.desc()).limit(10).all()

        if cuotas_pagadas:
            data_historial = []
            for cp in cuotas_pagadas:
                fila_historial = {
                    "ID Préstamo": cp.prestamo_id,
                    "Cuota N°": cp.numero_cuota,
                    "Valor Cuota": f"${cp.monto_cuota:,.2f}",
                    "Monto Abonado": f"${cp.monto_pagado:,.2f}",
                    "Estado": cp.estado.value if hasattr(cp.estado, "value") else str(cp.estado)
                }
                data_historial.append(fila_historial)
            st.dataframe(pd.DataFrame(data_historial), use_container_width=True, hide_index=True)
        else:
            st.info("No hay cuotas con abonos registrados todavía.")
    finally:
        db.close()


# --- MÓDULO 3: CLIENTES ---
def render_clientes(usuario):
    st.title(f"👥 Módulo de Clientes - {usuario.capitalize()}")
    st.markdown("Gestión de directorio y control general de clientes registrados.")

    db = SessionLocal()
    try:
        repo = ClienteRepository(db)
        
        with st.expander("➕ Registrar Nuevo Cliente", expanded=False):
            with st.form("form_nuevo_cliente"):
                nombre = st.text_input("Nombre completo *", key="input_nuevo_cliente_nombre_main")
                documento = st.text_input("Documento de Identidad", key="input_nuevo_cliente_doc_main")
                telefono = st.text_input("Teléfono de Contacto", key="input_nuevo_cliente_tel_main")
                direccion = st.text_input("Dirección", key="input_nuevo_cliente_dir_main")
                
                submitted = st.form_submit_button("Guardar Cliente", type="primary")
                if submitted:
                    if nombre.strip():
                        try:
                            repo.crear_cliente(
                                nombre=nombre.strip(),
                                documento=documento.strip() or "S/D",
                                telefono=telefono.strip() or "S/D",
                                direccion=direccion.strip() or "S/D",
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
        clientes = repo.obtener_por_usuario(usuario) if hasattr(repo, "obtener_por_usuario") else repo.listar_todos()

        if not clientes:
            st.info("No hay clientes registrados todavía.")
            return

        data_clientes = []
        for c in clientes:
            prestamos_cliente = db.query(Prestamo).filter(
                Prestamo.cliente_id == c.id, 
                Prestamo.usuario == usuario,
                Prestamo.estado == EstadoPrestamo.ACTIVO
            ).all()

            data_clientes.append({
                "ID": c.id,
                "Nombre Completo": getattr(c, 'nombre_completo', 'N/A'),
                "Documento": getattr(c, 'documento', 'S/D'),
                "Teléfono": getattr(c, 'telefono', 'S/D'),
                "Préstamos Activos": len(prestamos_cliente)
            })

        st.dataframe(pd.DataFrame(data_clientes), use_container_width=True, hide_index=True)

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

    st.divider()
    st.subheader("💰 Ajuste Manual de Caja (Cuadre con Dinero Físico)")
    st.caption(
        "Usa esto para que la Caja Disponible de la app coincida con el efectivo "
        "que realmente tienes en la mano — por ejemplo, cuando prestas dinero en "
        "físico y necesitas descontarlo de caja, o cuando metes capital nuevo."
    )

    db = SessionLocal()
    try:
        caja_service_ajuste = CajaService(db, usuario_actual=usuario)
        resumen_actual = caja_service_ajuste.obtener_resumen_financiero()

        col_res1, col_res2 = st.columns(2)
        with col_res1:
            st.metric("💵 Caja Disponible (en la app)", f"${resumen_actual.get('caja_disponible', Decimal('0.00')):,.2f}")
        with col_res2:
            st.metric("📈 Capital Prestado (Activo)", f"${resumen_actual.get('capital_prestado', Decimal('0.00')):,.2f}")

        tab_aporte, tab_retiro = st.tabs(["➕ Registrar Aporte (sube caja)", "➖ Registrar Retiro (baja caja)"])

        with tab_aporte:
            with st.form("form_aporte_caja"):
                monto_aporte = st.number_input("Monto del Aporte ($) *", min_value=1.0, step=100.0, format="%.2f", key="input_monto_aporte")
                obs_aporte = st.text_input(
                    "Observación *",
                    placeholder="Ej. Capital inicial no registrado / Ajuste de cuadre físico",
                    key="input_obs_aporte"
                )
                btn_aporte = st.form_submit_button("➕ Registrar Aporte", type="primary", use_container_width=True)

                if btn_aporte:
                    if not obs_aporte.strip():
                        st.warning("La observación es obligatoria para mantener trazabilidad.")
                    else:
                        try:
                            caja_service_ajuste.registrar_aporte(
                                monto=Decimal(str(monto_aporte)),
                                observacion=obs_aporte.strip()
                            )
                            st.success(f"✅ Aporte de ${monto_aporte:,.2f} registrado. Caja actualizada.")
                            st.rerun()
                        except Exception as e:
                            db.rollback()
                            st.error(f"❌ Error al registrar el aporte: {e}")

        with tab_retiro:
            with st.form("form_retiro_caja"):
                monto_retiro = st.number_input("Monto del Retiro ($) *", min_value=1.0, step=100.0, format="%.2f", key="input_monto_retiro")
                obs_retiro = st.text_input(
                    "Observación *",
                    placeholder="Ej. Dinero prestado en físico a cliente / Ajuste de cuadre físico",
                    key="input_obs_retiro"
                )
                btn_retiro = st.form_submit_button("➖ Registrar Retiro", type="primary", use_container_width=True)

                if btn_retiro:
                    if not obs_retiro.strip():
                        st.warning("La observación es obligatoria para mantener trazabilidad.")
                    else:
                        try:
                            caja_service_ajuste.registrar_retiro(
                                monto=Decimal(str(monto_retiro)),
                                observacion=obs_retiro.strip()
                            )
                            st.success(f"✅ Retiro de ${monto_retiro:,.2f} registrado. Caja actualizada.")
                            st.rerun()
                        except Exception as e:
                            db.rollback()
                            st.error(f"❌ Error al registrar el retiro: {e}")
    finally:
        db.close()
def render_gestion_respaldos(usuario):
    st.markdown("## 🛡️ Gestión y Seguridad de Datos")
    st.caption("Respalda tu información o administra el esquema de la base de datos.")

    if usuario.strip().lower() not in ["simon", "raylin"]:
        st.warning("🚫 **Acceso Restringido:** Las herramientas de respaldo avanzado y mantenimiento estructural están habilitadas exclusivamente para administradores autorizados.")
        return

    col1, col2 = st.columns(2)

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

    with col2:
        st.subheader("🔥 Zona de Peligro")
        st.write("Reinicia y reestructura la base de datos de forma limpia evitando bloqueos de archivo.")

        with st.expander("⚠️ Desplegar opción de mantenimiento estructural", expanded=False):
            confirmar_total = st.checkbox("Confirmo que deseo restablecer la estructura de la base de datos y borrar los datos actuales")
            
            if st.button("💥 Recrear Tablas y Liberar Conexiones", type="primary", use_container_width=True):
                if confirmar_total:
                    try:
                        with st.spinner("Liberando conexiones del sistema y reestructurando el motor SQLite..."):
                            engine.dispose()
                            Base.metadata.drop_all(bind=engine)
                            Base.metadata.create_all(bind=engine)

                            st.session_state.clear()
                            st.session_state["logged_in"] = True
                            st.session_state["username"] = usuario

                        st.success("🎉 ¡La base de datos se ha reestructurado y optimizado con éxito!")
                        st.balloons()
                        st.rerun()
                    except Exception as e:
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
            usr = st.text_input("Usuario", key="input_login_usuario").strip().lower()
            pwd = st.text_input("Contraseña", type="password", key="input_login_password")
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
        render_prestamos(usuario_actual)
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
