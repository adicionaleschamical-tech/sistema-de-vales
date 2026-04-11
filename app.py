import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import date
import calendar
import re

st.set_page_config(page_title="Sistema de Vales", layout="wide")

SHEET_ID = "1nwfjyFdEG06T85HCmouFd279ImyimfcXFZebs07N1gQ"

def conectar_gsheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)

def limpiar_numero(valor):
    """Convierte un valor a número, eliminando puntos, espacios y caracteres especiales"""
    if valor is None:
        return 0
    if isinstance(valor, (int, float)):
        return int(valor)
    # Convertir a string y limpiar
    valor_str = str(valor).strip()
    # Eliminar puntos (separadores de miles)
    valor_str = valor_str.replace(".", "")
    # Eliminar espacios
    valor_str = valor_str.replace(" ", "")
    # Eliminar signos de $
    valor_str = valor_str.replace("$", "")
    # Eliminar comas
    valor_str = valor_str.replace(",", "")
    try:
        return int(float(valor_str))
    except:
        return 0

def verificar_login(username, password):
    try:
        sheet = conectar_gsheets()
        ws = sheet.worksheet("usuarios")
        datos = ws.get_all_records()
        
        for user in datos:
            if str(user["username"]).strip() == str(username).strip() and str(user["password_hash"]).strip() == str(password).strip():
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
        # Verificar año y mes
        año_dato = limpiar_numero(d.get("año", 0))
        mes_dato = limpiar_numero(d.get("mes", 0))
        
        if año_dato == hoy.year and mes_dato == hoy.month:
            monto = limpiar_numero(d.get("monto_mensual", 0))
            dependencias.append({
                "dependencia_id": limpiar_numero(d.get("dependencia_id", 0)),
                "nombre": str(d.get("nombre", "")),
                "monto_mensual": monto,
                "año": año_dato,
                "mes": mes_dato
            })
    return dependencias

def obtener_stock_vales():
    sheet = conectar_gsheets()
    ws = sheet.worksheet("vales_disponibles")
    datos = ws.get_all_records()
    stock = {}
    for row in datos:
        denom = limpiar_numero(row.get("denominacion", 0))
        cantidad = limpiar_numero(row.get("cantidad", 0))
        if denom > 0:
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
            st.info("Verifica que en la hoja 'dependencias' los valores de 'año' y 'mes' coincidan con la fecha actual")
            st.stop()
        
        miercoles = contar_miercoles(hoy.year, hoy.month)
        st.info(f"📆 Este mes tiene **{miercoles} miércoles**")
        
        st.subheader("📊 Dependencias")
        tabla = []
        for dep in dependencias:
            if dep["monto_mensual"] > 0:
                monto_semanal = dep["monto_mensual"] / miercoles
                tabla.append({
                    "ID": dep["dependencia_id"],
                    "Dependencia": dep["nombre"],
                    "Monto Mensual": f"${dep['monto_mensual']:,.0f}",
                    "Monto Semanal": f"${monto_semanal:,.0f}"
                })
        
        if tabla:
            st.dataframe(pd.DataFrame(tabla), use_container_width=True)
        else:
            st.warning("No hay datos válidos en la hoja 'dependencias'")
        
        st.subheader("💰 Stock de Vales")
        stock = obtener_stock_vales()
        if stock:
            stock_df = pd.DataFrame([
                {"Denominación": f"${d:,.0f}", "Cantidad": c}
                for d, c in sorted(stock.items())
            ])
            st.dataframe(stock_df, use_container_width=True)
        else:
            st.warning("No hay datos de stock en la hoja 'vales_disponibles'")
            
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        st.info("Verifica que las hojas de Google Sheets tengan los datos correctos")
