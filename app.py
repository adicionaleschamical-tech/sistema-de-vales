import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import date
import calendar

st.set_page_config(page_title="Sistema de Vales", layout="wide")

SHEET_ID = "1nwfjyFdEG06T85HCmouFd279ImyimfcXFZebs07N1gQ"

def conectar_gsheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)

def verificar_login(username, password):
    try:
        sheet = conectar_gsheets()
        ws = sheet.worksheet("usuarios")
        datos = ws.get_all_records()
        
        # Mostrar información de depuración
        st.write("### 🔍 Depuración - Revisando login")
        st.write(f"**Usuario ingresado:** `{username}`")
        st.write(f"**Contraseña ingresada:** `{password}`")
        st.write("---")
        st.write("**Usuarios encontrados en la hoja 'usuarios':**")
        
        for user in datos:
            st.write(f"- Usuario: `{user['username']}`, Contraseña guardada: `{user['password_hash']}`")
            if str(user["username"]) == str(username) and str(user["password_hash"]) == str(password):
                st.success("✅ ¡Match encontrado! Iniciando sesión...")
                return True
        
        st.warning("❌ No se encontró ningún usuario que coincida")
        st.info("Verifica que en la hoja 'usuarios' los datos estén escritos exactamente igual sin espacios")
        return False
    except Exception as e:
        st.error(f"Error de conexión con Google Sheets: {e}")
        return False

def contar_miercoles(anio, mes):
    count = 0
    for dia in range(1, calendar.monthrange(anio, mes)[1] + 1):
        if calendar.weekday(anio, mes, dia) == 2:
            count += 1
    return count

def obtener_dependencias():
    sheet = conectar_gsheets()
    ws = sheet.worksheet("dependencias")
    datos = ws.get_all_records()
    hoy = date.today()
    return [d for d in datos if d["año"] == hoy.year and d["mes"] == hoy.month]

def obtener_stock_vales():
    sheet = conectar_gsheets()
    ws = sheet.worksheet("vales_disponibles")
    datos = ws.get_all_records()
    return {int(row["denominacion"]): int(row["cantidad"]) for row in datos}

def calcular_distribucion_semanal():
    """Calcula la distribución de vales por dependencia"""
    try:
        sheet = conectar_gsheets()
        dependencias = obtener_dependencias()
        stock = obtener_stock_vales()
        hoy = date.today()
        miercoles = contar_miercoles(hoy.year, hoy.month)
        
        if not dependencias:
            return "No hay dependencias para el mes actual"
        
        resultados = []
        for dep in dependencias:
            monto_semanal = dep["monto_mensual"] / miercoles
            resultados.append({
                "dependencia": dep["nombre"],
                "monto_semanal": monto_semanal,
                "estado": "Pendiente"
            })
        
        return resultados
    except Exception as e:
        return f"Error: {e}"

# Inicializar estado de sesión
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None

# ============================================
# PANTALLA DE LOGIN
# ============================================
if not st.session_state.logged_in:
    st.title("🔐 Sistema de Gestión de Vales")
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("Iniciar sesión")
        with st.form("login_form"):
            username = st.text_input("Usuario", placeholder="Ej: 30588807")
            password = st.text_input("Contraseña", type="password", placeholder="Ej: 124578")
            submit = st.form_submit_button("Ingresar", use_container_width=True, type="primary")
            
            if submit:
                if username and password:
                    if verificar_login(username, password):
                        st.session_state.logged_in = True
                        st.session_state.username = username
                        st.rerun()
                else:
                    st.warning("Por favor ingresa usuario y contraseña")

# ============================================
# APP PRINCIPAL (después del login)
# ============================================
else:
    # Sidebar
    st.sidebar.title("🎫 Sistema de Vales")
    st.sidebar.markdown("---")
    st.sidebar.success(f"✅ Conectado como: **{st.session_state.username}**")
    
    if st.sidebar.button("🚪 Cerrar sesión", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.caption("Versión 1.0")
    
    # Main content
    st.title("🎫 Sistema de Gestión de Vales")
    
    # Fecha actual
    hoy = date.today()
    st.header(f"📅 {hoy.strftime('%B %Y')}")
    
    # Obtener datos
    dependencias = obtener_dependencias()
    
    if not dependencias:
        st.warning("⚠️ No hay dependencias configuradas para el mes actual")
        st.info("Ve a tu Google Sheet y asegúrate que en la hoja 'dependencias' haya datos con el año y mes actual")
        st.stop()
    
    # Calcular miércoles del mes
    miercoles = contar_miercoles(hoy.year, hoy.month)
    st.info(f"📆 Este mes tiene **{miercoles} miércoles**")
    
    # Mostrar tabla de dependencias
    st.subheader("📊 Dependencias y Montos Semanales")
    
    tabla_dependencias = []
    for dep in dependencias:
        monto_semanal = dep["monto_mensual"] / miercoles
        tabla_dependencias.append({
            "ID": dep["dependencia_id"],
            "Dependencia": dep["nombre"],
            "Monto Mensual": f"${dep['monto_mensual']:,.0f}",
            "Monto Semanal": f"${monto_semanal:,.0f}"
        })
    
    st.dataframe(pd.DataFrame(tabla_dependencias), use_container_width=True)
    
    # Mostrar stock de vales
    st.subheader("💰 Stock de Vales Disponible")
    stock = obtener_stock_vales()
    
    if stock:
        stock_df = pd.DataFrame([
            {"Denominación": f"${d:,.0f}", "Cantidad": c}
            for d, c in stock.items()
        ])
        st.dataframe(stock_df, use_container_width=True)
    else:
        st.warning("No hay datos de stock en la hoja 'vales_disponibles'")
    
    # Sección de distribución
    st.subheader("🎯 Distribución Semanal")
    st.markdown("---")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        semana = st.selectbox("Selecciona la semana", ["Semana 1", "Semana 2", "Semana 3", "Semana 4"])
        
        if st.button("📦 Calcular Distribución", type="primary", use_container_width=True):
            with st.spinner("Calculando distribución..."):
                resultado = calcular_distribucion_semanal()
                if isinstance(resultado, list):
                    st.success("✅ Cálculo completado")
                    st.dataframe(pd.DataFrame(resultado), use_container_width=True)
                else:
                    st.error(resultado)
    
    with col2:
        st.info("""
        **Instrucciones:**
        1. Cada miércoles se entregan los vales
        2. El monto semanal = Monto Mensual / Cantidad de miércoles del mes
        3. Se distribuirán los vales según disponibilidad
        """)
    
    # Mostrar última línea de tiempo
    st.markdown("---")
    st.caption("💡 Los datos se sincronizan automáticamente con Google Sheets")
