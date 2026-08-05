"""
app/pages/dashboard.py

Pantalla principal de indicadores clave y lista de últimos movimientos,
totalmente sincronizada con la sesión activa del usuario y control de caja.
"""

import streamlit as st
from decimal import Decimal

from app.database.database import SessionLocal
from app.services.caja_service import CajaService
from app.repositories.cliente_repository import ClienteRepository
from app.repositories.prestamo_repository import PrestamoRepository


def render_dashboard(usuario_actual: str = "admin"):
    # Normalización limpia del usuario actual para respetar las sesiones del sistema
    current_user = str(usuario_actual or "admin").strip().lower()

    st.markdown(f"## 📊 Dashboard Financiero — {usuario_actual.capitalize()}")
    st.caption("Resumen en tiempo real del estado de caja, capital en la calle y flujos de efectivo.")

    db = SessionLocal()

    try:
        # Se pasa el usuario actual a los servicios y repositorios para mantener el aislamiento correcto
        caja_service = CajaService(db, usuario_actual=current_user)
        cliente_repo = ClienteRepository(db)
        prestamo_repo = PrestamoRepository(db)

        # Obtener información financiera y de cartera
        resumen = caja_service.obtener_resumen_financiero()
        clientes = cliente_repo.listar_todos()
        
        # Filtro de préstamos activos según el usuario activo o administrador global
        prestamos_activos = prestamo_repo.obtener_por_usuario(current_user) if current_user != "admin" else prestamo_repo.listar_activos()
        
        # Validación segura para eventos recientes del usuario
        ultimos_eventos = []
        try:
            from app.models.evento import EventoFinanciero
            query_ev = db.query(EventoFinanciero)
            if current_user != "admin":
                query_ev = query_ev.filter(EventoFinanciero.usuario == current_user)
            ultimos_eventos = query_ev.order_by(EventoFinanciero.creado_en.desc()).limit(8).all()
        except Exception:
            if hasattr(prestamo_repo, "listar_ultimos_eventos"):
                ultimos_eventos = prestamo_repo.listar_ultimos_eventos(limite=8)

        total_clientes = len(clientes)
        clientes_activos = len(
            [c for c in clientes if hasattr(c, "estado") and (c.estado.value == "ACTIVO" if hasattr(c.estado, "value") else c.estado == "ACTIVO")]
        )
        clientes_bloqueados = len(
            [c for c in clientes if hasattr(c, "estado") and (c.estado.value == "BLOQUEADO" if hasattr(c.estado, "value") else c.estado == "BLOQUEADO")]
        )

        st.divider()

        # ==========================
        # MÉTRICAS FINANCIERAS
        # ==========================

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "💵 Caja Disponible",
                f"${resumen.get('caja_disponible', 0.0):,.2f}"
            )

        with col2:
            st.metric(
                "📈 Capital Prestado (Activo)",
                f"${resumen.get('capital_prestado', 0.0):,.2f}"
            )

        with col3:
            st.metric(
                "🏦 Capital Total (Caja + Cartera)",
                f"${resumen.get('capital_total', 0.0):,.2f}"
            )

        st.divider()

        # ==========================
        # ACCIÓN RÁPIDA: APORTE / CAJA INICIAL
        # ==========================
        with st.expander("⚙️ Registrar Movimiento de Caja (Ingreso Genérico o Aporte Inicial)"):
            with st.form("form_aporte_rapido", clear_on_submit=True):
                col_monto, col_obs = st.columns([1, 2])
                with col_monto:
                    monto_aporte = st.number_input("Monto ($)", min_value=1.0, step=1000.0, format="%.2f")
                with col_obs:
                    obs_aporte = st.text_input("Descripción / Motivo", value="Aporte inicial de capital o base en caja")
                
                btn_guardar_aporte = st.form_submit_button("Registrar Ingreso en Caja", type="primary", use_container_width=True)
                if btn_guardar_aporte:
                    try:
                        caja_service.registrar_aporte(Decimal(str(monto_aporte)), obs_aporte)
                        st.success("✅ ¡Ingreso registrado con éxito en tu caja!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al registrar el movimiento: {e}")

        st.divider()

        # ==========================
        # MÉTRICAS OPERATIVAS
        # ==========================

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.metric(
                "👥 Clientes",
                total_clientes
            )

        with c2:
            st.metric(
                "✅ Activos",
                clientes_activos
            )

        with c3:
            st.metric(
                "🚫 Bloqueados",
                clientes_bloqueados
            )

        with c4:
            st.metric(
                "📄 Préstamos Activos",
                len(prestamos_activos)
            )

        st.divider()

        # ==========================
        # ÚLTIMOS MOVIMIENTOS
        # ==========================

        st.subheader("🕒 Últimos Movimientos y Transacciones")

        if not ultimos_eventos:
            st.info("ℹ️ No hay movimientos financieros registrados todavía en este usuario. Utiliza el panel superior para registrar tu capital base.")

        else:
            for evento in ultimos_eventos:
                fecha_creacion = getattr(evento, "creado_en", None) or getattr(evento, "fecha", None)
                fecha = fecha_creacion.strftime("%d/%m/%Y %H:%M") if fecha_creacion else "N/A"

                monto_val = getattr(evento, "monto", 0.0)
                monto = f"${monto_val:,.2f}" if monto_val else "-"

                tipo_evento = getattr(evento, "tipo_evento", "MOVIMIENTO")
                tipo_evento_str = tipo_evento.value if hasattr(tipo_evento, "value") else str(tipo_evento)

                with st.container():
                    col_ev1, col_ev2 = st.columns([4, 1])

                    with col_ev1:
                        st.markdown(f"**{tipo_evento_str}**")
                        st.caption(f"Fecha: {fecha}")

                        observacion = getattr(evento, "observacion", "")
                        if observacion:
                            st.write(observacion)
                            st.caption(f"Usuario: {getattr(evento, 'usuario', current_user)}")

                    with col_ev2:
                        st.markdown(f"### {monto}")

                    st.divider()

    finally:
        db.close()
