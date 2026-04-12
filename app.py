import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import date, datetime
import calendar

st.set_page_config(page_title="Sistema de Vales", layout="wide")

SHEET_ID = "1nwfjyFdEG06T85HCmouFd279ImyimfcXFZebs07N1gQ"

# Denominaciones fijas (igual que en tu script)
DENOMINACIONES = [20000, 10000, 3000, 2000, 1000, 500, 100]

def conectar_gsheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)

def limpiar_numero(valor):
    if valor is None:
        return 0
    if isinstance(valor, (int, float)):
        return int(valor)
    valor_str = str(valor).strip()
    valor_str = valor_str.replace(".", "").replace(" ", "").replace("$", "").replace(",", "")
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
        st.error(f"Error: {e}")
        return False

def contar_miercoles(anio, mes):
    """Cuenta cuántos miércoles tiene un mes"""
    count = 0
    for dia in range(1, calendar.monthrange(anio, mes)[1] + 1):
        if calendar.weekday(anio, mes, dia) == 2:  # 2 = miércoles
            count += 1
    return count

def obtener_dependencias():
    """Obtiene las dependencias de la hoja 'dependencias'"""
    sheet = conectar_gsheets()
    ws = sheet.worksheet("dependencias")
    datos = ws.get_all_records()
    hoy = date.today()
    
    dependencias = []
    for d in datos:
        año_dato = limpiar_numero(d.get("año", 0))
        mes_dato = limpiar_numero(d.get("mes", 0))
        
        if año_dato == hoy.year and mes_dato == hoy.month:
            monto = limpiar_numero(d.get("monto_mensual", 0))
            dependencias.append({
                "id": limpiar_numero(d.get("dependencia_id", 0)),
                "nombre": str(d.get("nombre", "")),
                "monto_mensual": monto
            })
    return dependencias

def obtener_stock_actual():
    """Obtiene el stock actual de vales de la hoja 'vales_disponibles'"""
    sheet = conectar_gsheets()
    ws = sheet.worksheet("vales_disponibles")
    datos = ws.get_all_records()
    
    stock = {den: 0 for den in DENOMINACIONES}
    for row in datos:
        denom = limpiar_numero(row.get("denominacion", 0))
        cantidad = limpiar_numero(row.get("cantidad", 0))
        if denom in stock:
            stock[denom] = cantidad
    return stock

def actualizar_stock(stock_nuevo):
    """Actualiza la hoja 'vales_disponibles' con el nuevo stock"""
    sheet = conectar_gsheets()
    ws = sheet.worksheet("vales_disponibles")
    
    for i, denom in enumerate(DENOMINACIONES):
        # Buscar la fila de esa denominación
        celda = ws.find(str(denom))
        if celda:
            ws.update_cell(celda.row, 2, stock_nuevo[denom])

def distribuir_vales(dependencias, stock_actual, miercoles):
    """
    Lógica de distribución basada en tu script:
    - Redondeo hacia abajo (conservador)
    - Asigna la mayor cantidad posible sin exceder la cuota
    """
    # Calcular cuota semanal por dependencia
    reparto = []
    for dep in dependencias:
        cuota_semanal = dep["monto_mensual"] / miercoles
        reparto.append({
            "nombre": dep["nombre"],
            "cuota_objetivo": cuota_semanal,
            "vales": [0, 0, 0, 0, 0, 0, 0],  # 7 denominaciones
            "total": 0
        })
    
    # Copiar stock para no modificar el original hasta el final
    stock = stock_actual.copy()
    
    # Asignación: REDONDEO HACIA ABAJO (igual que tu script)
    for ofi in reparto:
        for j, valor_vale in enumerate(DENOMINACIONES):
            while stock[valor_vale] > 0:
                # Solo sumamos si no excede la cuota
                if ofi["total"] + valor_vale <= ofi["cuota_objetivo"]:
                    ofi["vales"][j] += 1
                    stock[valor_vale] -= 1
                    ofi["total"] += valor_vale
                else:
                    # Si este vale hace pasar la cuota, pasamos a la siguiente denominación
                    break
    
    return reparto, stock

def registrar_historial(fecha, reparto, tipo):
    """Registra la distribución en el historial (similar a tu script)"""
    sheet = conectar_gsheets()
    
    # Buscar o crear hoja de historial
    try:
        historial_ws = sheet.worksheet("entregas_semanales")
    except:
        historial_ws = sheet.add_worksheet(title="entregas_semanales", rows="1000", cols="20")
    
    # Calcular total de vales entregados por denominación
    totales = [0, 0, 0, 0, 0, 0, 0]
    for ofi in reparto:
        for j, cant in enumerate(ofi["vales"]):
            totales[j] += cant
    
    # Preparar fila: [FECHA, v20k, v10k, v3k, v2k, v1k, v500, v100, TOTAL_VALES, TIPO]
    nueva_fila = [
        str(fecha),
        totales[0],  # 20000
        totales[1],  # 10000
        totales[2],  # 3000
        totales[3],  # 2000
        totales[4],  # 1000
        totales[5],  # 500
        totales[6],  # 100
        sum(totales),
        tipo
    ]
    
    historial_ws.append_row(nueva_fila)

def mostrar_reparto_en_tabla(reparto):
    """Muestra el reparto en una tabla formateada"""
    datos_tabla = []
    for ofi in reparto:
        fila = {
            "Dependencia": ofi["nombre"],
            "Cuota Objetivo": f"${ofi['cuota_objetivo']:,.0f}",
            "Total Entregado": f"${ofi['total']:,.0f}",
            "Diferencia": f"${ofi['cuota_objetivo'] - ofi['total']:,.0f}",
            "Vales 20k": ofi["vales"][0],
            "Vales 10k": ofi["vales"][1],
            "Vales 3k": ofi["vales"][2],
            "Vales 2k": ofi["vales"][3],
            "Vales 1k": ofi["vales"][4],
            "Vales 500": ofi["vales"][5],
            "Vales 100": ofi["vales"][6],
        }
        datos_tabla.append(fila)
    return pd.DataFrame(datos_tabla)

# ============================================
# INTERFAZ DE STREAMLIT
# ============================================

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
    
    # Mostrar información del mes actual
    hoy = date.today()
    st.header(f"📅 {hoy.strftime('%B %Y')}")
    
    # Obtener datos
    dependencias = obtener_dependencias()
    
    if not dependencias:
        st.warning("No hay dependencias para el mes actual")
        st.stop()
    
    miercoles = contar_miercoles(hoy.year, hoy.month)
    st.info(f"📆 Este mes tiene **{miercoles} miércoles**")
    
    # Mostrar dependencias
    st.subheader("📊 Dependencias y Montos Semanales")
    tabla_deps = []
    for dep in dependencias:
        monto_semanal = dep["monto_mensual"] / miercoles
        tabla_deps.append({
            "ID": dep["id"],
            "Dependencia": dep["nombre"],
            "Monto Mensual": f"${dep['monto_mensual']:,.0f}",
            "Monto Semanal": f"${monto_semanal:,.0f}"
        })
    st.dataframe(pd.DataFrame(tabla_deps), use_container_width=True)
    
    # Mostrar stock actual
    st.subheader("💰 Stock Actual de Vales")
    stock = obtener_stock_actual()
    stock_df = pd.DataFrame([
        {"Denominación": f"${d:,.0f}", "Cantidad": stock[d]}
        for d in DENOMINACIONES
    ])
    st.dataframe(stock_df, use_container_width=True)
    
    # SECCIÓN DE DISTRIBUCIÓN
    st.markdown("---")
    st.subheader("🎯 Distribución Semanal")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        fecha_dist = st.date_input("Fecha de distribución (miércoles)", value=hoy)
        
        if st.button("📦 Ejecutar Distribución Automática", type="primary", use_container_width=True):
            with st.spinner("Calculando distribución..."):
                # Verificar que la fecha sea miércoles
                if fecha_dist.weekday() != 2:
                    st.warning("⚠️ La distribución debe hacerse en un miércoles")
                else:
                    reparto, stock_nuevo = distribuir_vales(dependencias, stock, miercoles)
                    
                    # Mostrar resultados
                    st.success("✅ Distribución calculada exitosamente")
                    
                    df_reparto = mostrar_reparto_en_tabla(reparto)
                    st.dataframe(df_reparto, use_container_width=True)
                    
                    # Resumen de stock después de la distribución
                    st.subheader("📦 Stock después de la distribución")
                    stock_despues_df = pd.DataFrame([
                        {"Denominación": f"${d:,.0f}", "Stock Anterior": stock[d], "Stock Actual": stock_nuevo[d], "Entregado": stock[d] - stock_nuevo[d]}
                        for d in DENOMINACIONES
                    ])
                    st.dataframe(stock_despues_df, use_container_width=True)
                    
                    # Botón para confirmar y guardar
                    if st.button("✅ Confirmar y Guardar Distribución", type="primary"):
                        # Actualizar stock en Google Sheets
                        actualizar_stock(stock_nuevo)
                        # Registrar en historial
                        registrar_historial(fecha_dist, reparto, "AUTO")
                        st.success("🎉 Distribución guardada exitosamente")
                        st.rerun()
    
    with col2:
        st.info("""
        **📋 Estrategia de Distribución (Redondeo hacia abajo):**
        
        1. Se calcula la cuota semanal de cada dependencia
        2. Se asignan vales de mayor a menor denominación
        3. No se excede la cuota objetivo
        4. Si un vale hace superar la cuota, se intenta con la siguiente denominación
        
        **Ejemplo:** Si la cuota es $502,500 y solo quedan vales de $1,000, se entregan $502,000 y quedan $500 pendientes.
        """)
    
    # Mostrar historial reciente
    st.markdown("---")
    st.subheader("📜 Historial de Entregas")
    try:
        sheet = conectar_gsheets()
        historial_ws = sheet.worksheet("entregas_semanales")
        historial_datos = historial_ws.get_all_records()
        if historial_datos:
            df_historial = pd.DataFrame(historial_datos.tail(10))
            st.dataframe(df_historial, use_container_width=True)
        else:
            st.info("No hay entregas registradas aún")
    except:
        st.info("No hay historial disponible")
