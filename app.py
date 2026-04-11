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
        
        for user in datos:
            if str(user["username"]) == str(username) and str(user["password_hash"]) == str(password):
                return True
        return False
    except Exception as e:
        st.error(f"Error de conexión: {e}")
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
    
    dependencias = []
    for d in datos:
        if d["año"] == hoy.year and d["mes"] == hoy.month:
            # Convertir a número si es necesario
            monto = d["monto_mensual"]
            if isinstance(monto, str):
                monto = int(monto.replace(",", "").replace("$", ""))
            
            dependencias.append({
                "dependencia_id": int(d["dependencia_id"]),
                "nombre": d["nombre"],
                "monto_mensual": monto,
                "año": d["año"],
                "mes": d["mes"]
            })
    return dependencias

def obtener_stock_vales():
    sheet = conectar_gsheets()
    ws = sheet.worksheet("vales_disponibles")
    datos = ws.get_all_records()
    stock = {}
    for row in datos:
        denom = row["denominacion"]
        if isinstance(denom, str):
            denom = int(denom.replace(",", "").replace("$", ""))
        cantidad = row["cantidad"]
        if isinstance(cantidad, str):
            cantidad = int(cantidad)
        stock[denom] = cantidad
    return stock

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 Sistema de Vales")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login"):
            st.subheader("Iniciar sesión")
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            submit = st.form_submit_button("Ingresar", use_container_width=True)
            if submit:
                if verificar_login(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos")
else:
    st.title("🎫 Sistema de Gestión de Vales")
    st.sidebar.success(f"✅ Usuario: {st.session_state.username}")
    
    if st.sidebar.button("🚪 Cerrar sesión"):
        st.session_state.logged_in = False
        st.rerun()
    
    hoy = date.today()
    st.header(f"📅 {hoy.strftime('%B %Y')}")
    
    try:
        dependencias = obtener_dependencias()
        
        if not dependencias:
            st.warning("No hay dependencias para el mes actual")
            st.stop()
        
        miercoles = contar_miercoles(hoy.year, hoy.month)
        st.info(f"📆 Este mes tiene **{miercoles} miércoles**")
        
        st.subheader("📊 Dependencias")
        tabla = []
        for dep in dependencias:
            monto_semanal = dep["monto_mensual"] / miercoles
            tabla.append({
                "ID": dep["dependencia_id"],
                "Dependencia": dep["nombre"],
                "Monto Mensual": f"${dep['monto_mensual']:,.0f}",
                "Monto Semanal": f"${monto_semanal:,.0f}"
            })
        st.dataframe(pd.DataFrame(tabla), use_container_width=True)
        
        st.subheader("💰 Stock de Vales")
        stock = obtener_stock_vales()
        if stock:
            stock_df = pd.DataFrame([
                {"Denominación": f"${d:,.0f}", "Cantidad": c}
                for d, c in stock.items()
            ])
            st.dataframe(stock_df, use_container_width=True)
        else:
            st.warning("No hay datos de stock")
            
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        st.info("Verifica que las hojas de Google Sheets tengan los datos correctos")
