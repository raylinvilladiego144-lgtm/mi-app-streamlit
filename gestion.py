import streamlit as st
import os
from app.database.database import SessionLocal
from app.repositories.prestamo_repository import PrestamoRepository

def render_gestion_respaldos():
    st.markdown("## 🛡️ Gestión y Seguridad de Datos")
    st.caption("Respalda tu información, limpia tus registros o reinicia el sistema.")

    db_path = "prestamos_v2.db"

    col1, col2 = st.columns(2)

    # --- 1. BOTÓN DE RESPALDO (BACKUP) GLOBAL ---
    with col1:
        st.subheader("💾 Copia de Seguridad")
        st.write("Descarga una copia actual de la base de datos general.")
        
        if os.path.exists(db_path):
            with open(db_path, "rb") as f:
                db_bytes = f.read()
            
            st.download_button(
                label="📥 Descargar Respaldo (.db)",
                data=db_bytes,
                file_name="respaldo_prestamos_v2.db",
                mime="application/octet-stream",
                type="primary"
            )
        else:
            st.warning("⚠️ Todavía no se detecta el archivo de la base de datos.")

    # --- 2. ELIMINAR HISTORIAL INDEPENDIENTE POR ADMINISTRADOR (OPCIÓN 1) ---
    with col2:
        st.subheader("🗑️ Limpiar Mi Historial de Préstamos")
        st.write("Elimina permanentemente solo los préstamos registrados bajo tu usuario.")

        # Identificar al administrador actual en sesión
        usuario_actual = st.session_state.get("username", "admin")
        st.info(f"👤 Administrador activo: **{usuario_actual}**")

        db = SessionLocal()
        try:
            prestamo_repo = PrestamoRepository(db)
            
            # FILTRO OPCIÓN 1: Obtener únicamente los préstamos de este usuario
            prestamos = prestamo_repo.obtener_por_usuario(usuario_actual)
            
            if not prestamos:
                st.info("No tienes préstamos registrados para eliminar.")
            else:
                prestamos_dict = {
                    f"Préstamo #{p.id} - Cliente: {getattr(p, 'cliente_nombre', 'N/A')} (${getattr(p, 'monto_total', 0):,.2f})": p.id 
                    for p in prestamos
                }
                
                prestamo_seleccionado = st.selectbox(
                    "Selecciona el préstamo tuyo que deseas eliminar",
                    options=list(prestamos_dict.keys())
                )
                
                confirmar_borrado = st.checkbox("Confirmo que deseo eliminar este préstamo y su historial permanentemente")
                
                if st.button("❌ Eliminar Mi Préstamo", type="secondary"):
                    if confirmar_borrado:
                        id_a_borrar = prestamos_dict[prestamo_seleccionado]
                        try:
                            prestamo_repo.eliminar_prestamo(id_a_borrar)
                            st.success(f"¡El Préstamo #{id_a_borrar} fue eliminado correctamente de tus registros!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al eliminar el préstamo: {e}")
                    else:
                        st.warning("⚠️ Debes marcar la casilla de confirmación.")
        finally:
            db.close()

    # --- 3. ZONA DE PELIGRO: LIMPIEZA TOTAL DE LA BASE DE DATOS ---
    st.divider()
    st.subheader("🔥 Zona de Peligro: Reiniciar Base de Datos por Completo")
    st.write("Si necesitas dejar el proyecto completamente en ceros (limpiando todos los registros de todos los usuarios), utiliza esta opción.")

    with st.expander("⚠️ Desplegar opción de limpieza general", expanded=False):
        confirmar_total = st.checkbox("Confirmo que deseo borrar ABSOLUTAMENTE TODO el contenido de la base de datos")
        
        if st.button("💥 Borrar Todo y Dejar en Ceros", type="primary"):
            if confirmar_total:
                try:
                    # Cerrar cualquier instancia activa de la BD si es necesario
                    if os.path.exists(db_path):
                        os.remove(db_path)
                        st.success("¡Base de datos limpiada y reiniciada con éxito! Recargando aplicación...")
                        st.rerun()
                    else:
                        st.warning("No se encontró el archivo de la base de datos para eliminar.")
                except Exception as e:
                    st.error(f"❌ Error al reiniciar la base de datos: {e}")
            else:
                st.warning("⚠️ Debes marcar la casilla de confirmación para ejecutar el reinicio total.")
