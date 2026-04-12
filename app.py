import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import date
import calendar

# ============================================
# CONFIGURACIÓN DE LA PÁGINA
# ============================================
st.set_page_config(
    page_title="Sistema de Vales", 
    page_icon="🎫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================
# CONFIGURACIÓN PWA SIMPLIFICADA
# ============================================
st.markdown("""
    <link rel="manifest" href="manifest.json">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-title" content="Sistema Vales">
    <meta name="application-name" content="Sistema Vales">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#1f77b4">
    <title>Sistema de Vales</title>
""", unsafe_allow_html=True)

# ============================================
# CSS PERSONALIZADO - MEJORAS VISUALES
# ============================================
st.markdown("""
<style>
    /* Fuente y fondo principal */
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }
    
    /* Títulos principales */
    h1, h2, h3 {
        color: #1f77b4 !important;
        font-weight: 600 !important;
    }
    
    /* Tarjetas para métricas */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 15px;
        padding: 20px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        margin: 10px 0;
    }
    
    .metric-card h3 {
        color: white !important;
        font-size: 14px;
        margin-bottom: 10px;
    }
    
    .metric-card .value {
        font-size: 32px;
        font-weight: bold;
    }
    
    /* Botones personalizados */
    .stButton > button {
        background: linear-gradient(135deg, #1f77b4 0%, #17becf 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 10px 25px;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        color: white;
    }
    
    /* Tarjetas para dependencias */
    .dependencia-card {
        background: white;
        border-radius: 15px;
        padding: 20px;
        margin: 10px 0;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        border-left: 5px solid #1f77b4;
        transition: all 0.3s ease;
    }
    
    .dependencia-card:hover {
        transform: translateX(5px);
        box-shadow: 0 5px 20px rgba(0,0,0,0.1);
    }
    
    .dependencia-card h4 {
        color: #1f77b4;
        margin-bottom: 10px;
    }
    
    .dependencia-card .monto {
        font-size: 24px;
        font-weight: bold;
        color: #2c3e50;
    }
    
    /* Tablas personalizadas */
    .dataframe {
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }
    
    .dataframe thead th {
        background: linear-gradient(135deg, #1f77b4 0%, #17becf 100%);
        color: white !important;
        font-weight: bold;
        padding: 12px;
    }
    
    /* Sidebar personalizado */
    .css-1d391kg {
        background: linear-gradient(180deg, #1f77b4 0%, #0f5a8a 100%);
    }
    
    /* Notificaciones */
    .stAlert {
        border-radius: 10px;
        border-left: 4px solid;
    }
    
    /* Inputs */
    .stTextInput > div > div > input, .stNumberInput > div > div > input {
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        padding: 10px;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background-color: #f8f9fa;
        border-radius: 10px;
        font-weight: bold;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px;
        padding: 10px 20px;
        background-color: #f0f2f6;
        font-weight: bold;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #1f77b4 0%, #17becf 100%);
        color: white;
    }
    
    /* Animaciones */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .stApp {
        animation: fadeIn 0.5s ease-out;
    }
    
    /* Badges para estados */
    .badge-success {
        background-color: #27ae60;
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: bold;
        display: inline-block;
    }
    
    .badge-warning {
        background-color: #f39c12;
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: bold;
        display: inline-block;
    }
    
    .badge-danger {
        background-color: #e74c3c;
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: bold;
        display: inline-block;
    }
    
    /* Footer */
    .footer {
        text-align: center;
        padding: 20px;
        margin-top: 40px;
        color: #7f8c8d;
        font-size: 12px;
        border-top: 1px solid #e0e0e0;
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# CONSTANTES Y CONFIGURACIÓN
# ============================================
SHEET_ID = "1nwfjyFdEG06T85HCmouFd279ImyimfcXFZebs07N1gQ"
DENOMINACIONES = [20000, 10000, 3000, 2000, 1000, 500, 100]

# ============================================
# FUNCIONES AUXILIARES DE VISUALIZACIÓN
# ============================================
def mostrar_metricas_destacadas(stock_actual):
    """Muestra métricas destacadas en tarjetas visuales"""
    total_dinero = sum(den * stock_actual[den] for den in DENOMINACIONES)
    total_vales = sum(stock_actual.values())
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <h3>💰 Total en Caja</h3>
            <div class="value">${total_dinero:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <h3>🎫 Total de Vales</h3>
            <div class="value">{total_vales:,}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <h3>📊 Denominaciones</h3>
            <div class="value">{len(DENOMINACIONES)}</div>
        </div>
        """, unsafe_allow_html=True)

def mostrar_tarjeta_dependencia(nombre, monto, cuota_semanal):
    """Muestra cada dependencia como tarjeta visual"""
    st.markdown(f"""
    <div class="dependencia-card">
        <h4>🏢 {nombre}</h4>
        <div class="monto">${monto:,.0f} <span style="font-size: 14px;">mensual</span></div>
        <div style="margin-top: 10px;">
            <span class="badge-success">💰 ${cuota_semanal:,.0f} semanal</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

def mostrar_badge_estado(diferencia):
    """Muestra badges de estado según la diferencia de cuota"""
    if diferencia > 0:
        return '<span class="badge-warning">⚠️ Incompleto</span>'
    elif diferencia < 0:
        return '<span class="badge-danger">⚠️ Excede</span>'
    else:
        return '<span class="badge-success">✅ Completo</span>'

# ============================================
# FUNCIONES PRINCIPALES (sin cambios)
# ============================================
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
        try:
            ws = sheet.worksheet("usuarios")
        except:
            st.error("❌ No se encuentra la hoja 'usuarios'")
            return False
        
        datos = ws.get_all_records()
        for user in datos:
            if str(user["username"]).strip() == str(username).strip() and str(user["password_hash"]).strip() == str(password).strip():
                return True
        return False
    except Exception as e:
        st.error(f"Error de login: {e}")
        return False

def contar_miercoles(anio, mes):
    count = 0
    for dia in range(1, calendar.monthrange(anio, mes)[1] + 1):
        if calendar.weekday(anio, mes, dia) == 2:
            count += 1
    return count

def obtener_dependencias():
    try:
        sheet = conectar_gsheets()
        try:
            ws = sheet.worksheet("dependencias")
        except:
            st.error("❌ No se encuentra la hoja 'dependencias'")
            return []
        
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
    except Exception as e:
        st.error(f"Error al leer dependencias: {e}")
        return []

def obtener_stock_actual():
    try:
        sheet = conectar_gsheets()
        try:
            ws = sheet.worksheet("vales_disponibles")
        except:
            st.error("❌ No se encuentra la hoja 'vales_disponibles'")
            return {den: 0 for den in DENOMINACIONES}
        
        datos = ws.get_all_records()
        
        stock = {den: 0 for den in DENOMINACIONES}
        for row in datos:
            denom = limpiar_numero(row.get("denominacion", 0))
            cantidad = limpiar_numero(row.get("cantidad", 0))
            if denom in stock:
                stock[denom] = cantidad
        return stock
    except Exception as e:
        st.error(f"Error al leer stock: {e}")
        return {den: 0 for den in DENOMINACIONES}

def actualizar_stock(stock_nuevo):
    try:
        sheet = conectar_gsheets()
        ws = sheet.worksheet("vales_disponibles")
        
        for denom, cantidad in stock_nuevo.items():
            cell = ws.find(str(denom))
            if cell:
                ws.update_cell(cell.row, 2, cantidad)
        return True
    except Exception as e:
        st.error(f"Error al actualizar stock: {e}")
        return False

def agregar_vales(vales_ingreso):
    stock_actual = obtener_stock_actual()
    for denom, cantidad in vales_ingreso.items():
        if cantidad > 0:
            stock_actual[denom] += cantidad
    actualizar_stock(stock_actual)
    return stock_actual

def cambiar_vales(desde_denom, desde_cant, hasta_denom, hasta_cant):
    try:
        stock_actual = obtener_stock_actual()
        
        if stock_actual[desde_denom] < desde_cant:
            return False, f"No hay suficientes vales de ${desde_denom:,.0f}. Disponibles: {stock_actual[desde_denom]}"
        
        stock_actual[desde_denom] -= desde_cant
        stock_actual[hasta_denom] += hasta_cant
        
        actualizar_stock(stock_actual)
        registrar_cambio_historial(desde_denom, desde_cant, hasta_denom, hasta_cant)
        
        return True, f"Cambio exitoso: {desde_cant} x ${desde_denom:,.0f} → {hasta_cant} x ${hasta_denom:,.0f}"
    except Exception as e:
        return False, f"Error: {e}"

def registrar_cambio_historial(desde_denom, desde_cant, hasta_denom, hasta_cant):
    try:
        sheet = conectar_gsheets()
        
        try:
            cambios_ws = sheet.worksheet("cambios_vales")
        except:
            cambios_ws = sheet.add_worksheet(title="cambios_vales", rows="1000", cols="10")
            cambios_ws.append_row(["fecha", "desde_denominacion", "desde_cantidad", "hasta_denominacion", "hasta_cantidad", "descripcion"])
        
        nueva_fila = [
            str(date.today()),
            desde_denom,
            desde_cant,
            hasta_denom,
            hasta_cant,
            f"Cambio: {desde_cant} x ${desde_denom} por {hasta_cant} x ${hasta_denom}"
        ]
        cambios_ws.append_row(nueva_fila)
        return True
    except Exception as e:
        st.error(f"Error al registrar cambio: {e}")
        return False

def registrar_entrega_detallada(fecha, reparto, tipo):
    try:
        sheet = conectar_gsheets()
        
        try:
            detalle_ws = sheet.worksheet("detalle_entregas")
        except:
            detalle_ws = sheet.add_worksheet(title="detalle_entregas", rows="1000", cols="15")
            encabezados = ["fecha", "dependencia_id", "dependencia_nombre", "cuota_objetivo", "total_entregado"]
            for d in DENOMINACIONES:
                encabezados.append(f"vale_{d}")
            detalle_ws.append_row(encabezados)
        
        for ofi in reparto:
            nueva_fila = [
                str(fecha),
                ofi.get("id", 0),
                ofi["nombre"],
                ofi.get("cuota_objetivo", 0),
                ofi["total"]
            ]
            for j, denom in enumerate(DENOMINACIONES):
                nueva_fila.append(ofi["vales"][j])
            detalle_ws.append_row(nueva_fila)
        
        return True
    except Exception as e:
        st.error(f"Error al registrar detalle: {e}")
        return False

def distribuir_vales_auto(dependencias, stock_actual, miercoles):
    reparto = []
    for dep in dependencias:
        cuota_semanal = dep["monto_mensual"] / miercoles
        reparto.append({
            "id": dep["id"],
            "nombre": dep["nombre"],
            "cuota_objetivo": cuota_semanal,
            "vales": [0, 0, 0, 0, 0, 0, 0],
            "total": 0
        })
    
    stock = stock_actual.copy()
    
    def calcular_combinacion_exacta(monto, stock_disponible):
        combinacion = [0, 0, 0, 0, 0, 0, 0]
        resto = monto
        
        for j, valor_vale in enumerate(DENOMINACIONES):
            if resto <= 0:
                break
            if stock_disponible[valor_vale] > 0:
                max_posibles = min(stock_disponible[valor_vale], resto // valor_vale)
                if max_posibles > 0:
                    usar = max_posibles
                    if j < len(DENOMINACIONES) - 1:
                        siguiente_valor = DENOMINACIONES[j + 1]
                        resto_despues = resto - (usar * valor_vale)
                        if resto_despues > 0 and resto_despues % siguiente_valor != 0:
                            usar = max(0, usar - 1)
                    combinacion[j] = usar
                    resto -= usar * valor_vale
        
        for j, valor_vale in enumerate(DENOMINACIONES):
            if resto <= 0:
                break
            if stock_disponible[valor_vale] > combinacion[j]:
                disponibles = stock_disponible[valor_vale] - combinacion[j]
                if resto >= valor_vale:
                    necesarios = min(disponibles, resto // valor_vale)
                    combinacion[j] += necesarios
                    resto -= necesarios * valor_vale
        
        return combinacion, resto
    
    for ofi in reparto:
        monto_necesario = ofi["cuota_objetivo"]
        combinacion, resto = calcular_combinacion_exacta(monto_necesario, stock)
        
        ofi["vales"] = combinacion
        ofi["total"] = monto_necesario - resto
        
        for j, valor_vale in enumerate(DENOMINACIONES):
            stock[valor_vale] -= combinacion[j]
    
    return reparto, stock

def registrar_historial(fecha, reparto, tipo, es_ingreso=False, vales_ingresados=None):
    try:
        sheet = conectar_gsheets()
        
        try:
            historial_ws = sheet.worksheet("entregas_semanales")
        except:
            historial_ws = sheet.add_worksheet(title="entregas_semanales", rows="1000", cols="20")
        
        if es_ingreso and vales_ingresados:
            nueva_fila = [
                str(fecha),
                0,
                vales_ingresados.get(100, 0),
                vales_ingresados.get(500, 0),
                vales_ingresados.get(1000, 0),
                vales_ingresados.get(2000, 0),
                vales_ingresados.get(3000, 0),
                vales_ingresados.get(10000, 0),
                vales_ingresados.get(20000, 0),
                f"INGRESO - {tipo}"
            ]
        else:
            totales = [0, 0, 0, 0, 0, 0, 0]
            for ofi in reparto:
                totales[0] += ofi["vales"][6]
                totales[1] += ofi["vales"][5]
                totales[2] += ofi["vales"][4]
                totales[3] += ofi["vales"][3]
                totales[4] += ofi["vales"][2]
                totales[5] += ofi["vales"][1]
                totales[6] += ofi["vales"][0]
            
            nueva_fila = [
                str(fecha),
                0,
                totales[0],
                totales[1],
                totales[2],
                totales[3],
                totales[4],
                totales[5],
                totales[6],
                f"DISTRIBUCION - {tipo}"
            ]
        
        historial_ws.append_row(nueva_fila)
        return True
    except Exception as e:
        st.error(f"Error al registrar historial: {e}")
        return False

# ============================================
# INTERFAZ DE USUARIO MEJORADA
# ============================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    # Login con diseño mejorado
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style="text-align: center; margin-bottom: 30px;">
            <h1>🎫 Sistema de Vales</h1>
            <p style="color: #666;">Gestión profesional de vales y distribuciones</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("login"):
            username = st.text_input("👤 Usuario", placeholder="Ingresa tu usuario")
            password = st.text_input("🔒 Contraseña", type="password", placeholder="Ingresa tu contraseña")
            submit = st.form_submit_button("🚀 Ingresar al Sistema", use_container_width=True)
            if submit:
                if verificar_login(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos")
else:
    # Header con bienvenida personalizada
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #1f77b4 0%, #17becf 100%); 
                border-radius: 15px; padding: 20px; margin-bottom: 30px; color: white;">
        <h1 style="color: white; margin: 0;">🎫 Sistema de Gestión de Vales</h1>
        <p style="margin: 10px 0 0 0; opacity: 0.9;">Bienvenido, {st.session_state.username} | 
        📅 {date.today().strftime('%d/%m/%Y')}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar mejorado
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 👤 Usuario")
        st.info(f"✅ {st.session_state.username}")
        
        st.markdown("---")
        st.markdown("### 📊 Resumen Rápido")
        stock_resumen = obtener_stock_actual()
        total_vales_resumen = sum(stock_resumen.values())
        st.metric("🎫 Total Vales", f"{total_vales_resumen:,}")
        
        st.markdown("---")
        if st.button("🚪 Cerrar sesión", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()
        
        st.markdown("---")
        st.markdown("""
        <div style="text-align: center; font-size: 12px; color: #666;">
            <p>© 2024 Sistema de Vales</p>
            <p>Versión 2.0</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Verificar conexión (colapsado por defecto)
    with st.expander("🔧 Verificar conexión con Google Sheets", expanded=False):
        try:
            sheet = conectar_gsheets()
            st.success("✅ Conexión exitosa con Google Sheets")
            st.info(f"📄 Documento: {sheet.title}")
        except Exception as e:
            st.error(f"❌ Error de conexión: {e}")
    
    # Tabs con mejor diseño
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📦 Ingresar Vales", 
        "🔄 Cambiar Vales", 
        "🤖 Distribución Auto", 
        "✏️ Distribución Manual", 
        "💰 Stock Actual", 
        "📜 Historial"
    ])
    
    # ========== TAB 1: INGRESAR VALES ==========
    with tab1:
        st.header("📥 Ingreso de nuevos vales")
        
        # Mostrar stock actual
        stock_actual_tab1 = obtener_stock_actual()
        mostrar_metricas_destacadas(stock_actual_tab1)
        
        with st.form("ingreso_vales"):
            st.subheader("📝 Complete las cantidades a ingresar")
            col1, col2 = st.columns(2)
            with col1:
                v20000 = st.number_input("💰 Vales de $20.000", min_value=0, value=0, step=1, help="Vales de mayor denominación")
                v10000 = st.number_input("💰 Vales de $10.000", min_value=0, value=0, step=1)
                v3000 = st.number_input("💰 Vales de $3.000", min_value=0, value=0, step=1)
                v2000 = st.number_input("💰 Vales de $2.000", min_value=0, value=0, step=1)
            with col2:
                v1000 = st.number_input("💰 Vales de $1.000", min_value=0, value=0, step=1)
                v500 = st.number_input("💰 Vales de $500", min_value=0, value=0, step=1)
                v100 = st.number_input("💰 Vales de $100", min_value=0, value=0, step=1)
            
            fecha_ingreso = st.date_input("📅 Fecha de ingreso", value=date.today())
            total_ingreso = v20000*20000 + v10000*10000 + v3000*3000 + v2000*2000 + v1000*1000 + v500*500 + v100*100
            
            # Mostrar total con formato
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); 
                        border-radius: 10px; padding: 15px; margin: 10px 0; text-align: center;">
                <span style="color: white; font-size: 18px;">💰 Total a ingresar</span>
                <div style="color: white; font-size: 32px; font-weight: bold;">${total_ingreso:,.0f}</div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.form_submit_button("✅ Confirmar Ingreso", type="primary", use_container_width=True):
                if total_ingreso > 0:
                    vales_ingreso = {20000: v20000, 10000: v10000, 3000: v3000, 2000: v2000, 1000: v1000, 500: v500, 100: v100}
                    agregar_vales(vales_ingreso)
                    registrar_historial(fecha_ingreso, None, "MANUAL", es_ingreso=True, vales_ingresados=vales_ingreso)
                    st.balloons()
                    st.success(f"✅ ¡Éxito! Se ingresaron ${total_ingreso:,.0f}")
                    st.rerun()
                else:
                    st.warning("⚠️ Ingresa al menos un vale para continuar")
    
    # ========== TAB 2: CAMBIAR VALES ==========
    with tab2:
        st.header("🔄 Cambiar Vales")
        st.info("💡 Ejemplo: Cambiar 1 vale de $10.000 por 5 vales de $2.000")
        
        with st.form("cambio_vales"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### 📤 De (sacar):")
                desde_denom = st.selectbox("Denominación origen", options=DENOMINACIONES, format_func=lambda x: f"${x:,.0f}")
                desde_cant = st.number_input("Cantidad a sacar", min_value=1, value=1, step=1)
            with col2:
                st.markdown("### 📥 A (agregar):")
                hasta_denom = st.selectbox("Denominación destino", options=DENOMINACIONES, format_func=lambda x: f"${x:,.0f}")
                hasta_cant = st.number_input("Cantidad a agregar", min_value=1, value=1, step=1)
            
            if st.form_submit_button("🔄 Ejecutar Cambio", type="primary", use_container_width=True):
                if desde_denom == hasta_denom:
                    st.error("❌ No puedes cambiar la misma denominación")
                else:
                    exito, mensaje = cambiar_vales(desde_denom, desde_cant, hasta_denom, hasta_cant)
                    if exito:
                        st.success(f"✅ {mensaje}")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(f"❌ {mensaje}")
    
    # ========== TAB 3: DISTRIBUCIÓN AUTOMÁTICA ==========
    with tab3:
        st.header("🤖 Distribución Automática Semanal")
        
        hoy = date.today()
        dependencias = obtener_dependencias()
        
        if not dependencias:
            st.warning("⚠️ No hay dependencias configuradas para el mes actual")
        else:
            miercoles = contar_miercoles(hoy.year, hoy.month)
            st.info(f"📆 Este mes tiene **{miercoles} miércoles** para distribución")
            
            # Mostrar dependencias como tarjetas
            st.subheader("🏢 Dependencias Activas")
            cols_deps = st.columns(2)
            for idx, dep in enumerate(dependencias):
                monto_semanal = dep["monto_mensual"] / miercoles
                with cols_deps[idx % 2]:
                    mostrar_tarjeta_dependencia(dep["nombre"], dep["monto_mensual"], monto_semanal)
            
            stock = obtener_stock_actual()
            st.subheader("💰 Stock Disponible")
            mostrar_metricas_destacadas(stock)
            
            st.markdown("---")
            fecha_dist = st.date_input("📅 Fecha de distribución (miércoles)", value=hoy)
            
            if st.button("📦 Calcular Distribución", type="primary", use_container_width=True):
                if fecha_dist.weekday() != 2:
                    st.warning("⚠️ La distribución debe hacerse en un miércoles")
                else:
                    reparto, stock_nuevo = distribuir_vales_auto(dependencias, stock, miercoles)
                    st.success("✅ Distribución calculada exitosamente")
                    
                    # Mostrar resultados
                    for ofi in reparto:
                        diferencia = ofi["cuota_objetivo"] - ofi["total"]
                        badge = mostrar_badge_estado(diferencia)
                        with st.expander(f"📋 {ofi['nombre']}"):
                            col_a, col_b, col_c = st.columns(3)
                            with col_a:
                                st.metric("🎯 Cuota objetivo", f"${ofi['cuota_objetivo']:,.0f}")
                            with col_b:
                                st.metric("✅ Total entregado", f"${ofi['total']:,.0f}")
                            with col_c:
                                st.markdown(f"**Estado:** {badge}", unsafe_allow_html=True)
                            
                            # Mostrar desglose de vales
                            st.markdown("**📊 Desglose de vales:**")
                            vales_dict = {denom: ofi["vales"][i] for i, denom in enumerate(DENOMINACIONES)}
                            st.json(vales_dict)
                    
                    st.session_state.reparto = reparto
                    st.session_state.stock_nuevo = stock_nuevo
                    st.session_state.fecha_dist = fecha_dist
            
            if 'reparto' in st.session_state:
                if st.button("💾 Guardar Distribución", type="primary", use_container_width=True):
                    with st.spinner("Actualizando stock y registrando..."):
                        if actualizar_stock(st.session_state.stock_nuevo):
                            registrar_historial(st.session_state.fecha_dist, st.session_state.reparto, "AUTO")
                            registrar_entrega_detallada(st.session_state.fecha_dist, st.session_state.reparto, "AUTO")
                            st.success("🎉 Distribución guardada exitosamente")
                            st.balloons()
                            del st.session_state.reparto
                            del st.session_state.stock_nuevo
                            del st.session_state.fecha_dist
                            st.rerun()
                        else:
                            st.error("❌ Error al actualizar el stock")
    
    # ========== TAB 4: DISTRIBUCIÓN MANUAL ==========
    with tab4:
        st.header("✏️ Distribución Manual Semanal")
        
        hoy = date.today()
        dependencias = obtener_dependencias()
        
        if not dependencias:
            st.warning("⚠️ No hay dependencias para el mes actual")
        else:
            miercoles = contar_miercoles(hoy.year, hoy.month)
            st.info(f"📆 Este mes tiene **{miercoles} miércoles**")
            
            # Mostrar cuotas semanales
            st.subheader("📊 Cuotas Semanales")
            cuotas = {}
            for dep in dependencias:
                cuota = dep["monto_mensual"] / miercoles
                cuotas[dep["id"]] = cuota
            
            cols_cuotas = st.columns(3)
            for idx, dep in enumerate(dependencias):
                with cols_cuotas[idx % 3]:
                    st.metric(f"🏢 {dep['nombre']}", f"${cuotas[dep['id']]:,.0f}", help="Cuota semanal")
            
            # Stock actual
            stock = obtener_stock_actual()
            st.subheader("💰 Stock Disponible")
            mostrar_metricas_destacadas(stock)
            
            st.markdown("---")
            st.subheader("✏️ Asignación Manual")
            
            fecha_manual = st.date_input("📅 Fecha de distribución", value=hoy)
            
            if 'manual_asignaciones' not in st.session_state:
                st.session_state.manual_asignaciones = {}
            
            reparto_manual = []
            for dep in dependencias:
                with st.expander(f"🏢 {dep['nombre']} - Cuota: ${cuotas[dep['id']]:,.0f}", expanded=True):
                    cols = st.columns(7)
                    vales_asignados = []
                    total_asignado = 0
                    
                    for i, denom in enumerate(DENOMINACIONES):
                        with cols[i]:
                            key = f"{dep['id']}_{denom}"
                            cantidad = st.number_input(
                                f"${denom:,.0f}",
                                min_value=0,
                                value=st.session_state.manual_asignaciones.get(key, 0),
                                step=1,
                                key=key,
                                help=f"Vales de ${denom:,.0f}"
                            )
                            vales_asignados.append(cantidad)
                            total_asignado += cantidad * denom
                    
                    diferencia = cuotas[dep["id"]] - total_asignado
                    if diferencia > 0:
                        st.warning(f"⚠️ Faltan ${diferencia:,.0f} para completar la cuota")
                    elif diferencia < 0:
                        st.error(f"⚠️ Excede la cuota en ${abs(diferencia):,.0f}")
                    else:
                        st.success("✅ Monto exacto de la cuota")
                    
                    st.metric("💰 Total asignado", f"${total_asignado:,.0f}")
                    
                    reparto_manual.append({
                        "id": dep["id"],
                        "nombre": dep["nombre"],
                        "cuota_objetivo": cuotas[dep["id"]],
                        "vales": vales_asignados,
                        "total": total_asignado
                    })
            
            if st.button("💾 Guardar Distribución Manual", type="primary", use_container_width=True):
                stock_temp = stock.copy()
                error_stock = False
                
                for ofi in reparto_manual:
                    for j, denom in enumerate(DENOMINACIONES):
                        if ofi["vales"][j] > stock_temp[denom]:
                            st.error(f"❌ No hay suficientes vales de ${denom:,.0f} para {ofi['nombre']}. Disponibles: {stock_temp[denom]}")
                            error_stock = True
                        else:
                            stock_temp[denom] -= ofi["vales"][j]
                
                if error_stock:
                    st.stop()
                
                with st.spinner("Guardando distribución manual..."):
                    actualizar_stock(stock_temp)
                    registrar_historial(fecha_manual, reparto_manual, "MANUAL")
                    registrar_entrega_detallada(fecha_manual, reparto_manual, "MANUAL")
                    st.success("🎉 Distribución manual guardada exitosamente")
                    st.balloons()
                    st.session_state.manual_asignaciones = {}
                    st.rerun()
    
    # ========== TAB 5: STOCK ACTUAL ==========
    with tab5:
        st.header("💰 Stock Actual de Vales")
        
        if st.button("🔄 Refrescar stock", use_container_width=True):
            st.rerun()
        
        stock = obtener_stock_actual()
        mostrar_metricas_destacadas(stock)
        
        # Tabla de stock con formato mejorado
        stock_data = []
        for d in DENOMINACIONES:
            cantidad = stock[d]
            total = d * cantidad
            # Barra de progreso visual
            porcentaje = min(cantidad / 100 * 100, 100) if cantidad > 0 else 0
            stock_data.append({
                "Denominación": f"${d:,.0f}",
                "Cantidad": cantidad,
                "Total": f"${total:,.0f}",
                "Distribución": f"{'█' * int(porcentaje/5)}{'░' * (20 - int(porcentaje/5))} {porcentaje:.0f}%"
            })
        
        df_stock = pd.DataFrame(stock_data)
        st.dataframe(df_stock, use_container_width=True, hide_index=True)
        
        # Gráfico de distribución (opcional, requiere plotly)
        try:
            import plotly.express as px
            fig = px.bar(x=[f"${d:,.0f}" for d in DENOMINACIONES], 
                        y=[stock[d] for d in DENOMINACIONES],
                        title="Distribución de Vales por Denominación",
                        labels={'x': 'Denominación', 'y': 'Cantidad'},
                        color=[stock[d] for d in DENOMINACIONES],
                        color_continuous_scale='Blues')
            fig.update_layout(showlegend=False, height=400)
            st.plotly_chart(fig, use_container_width=True)
        except:
            pass  # Si no está instalado plotly, omitir gráfico
    
    # ========== TAB 6: HISTORIAL ==========
    with tab6:
        st.header("📜 Historial de Movimientos")
        
        sub_tab1, sub_tab2, sub_tab3 = st.tabs(["📋 Resumen General", "📋 Detalle por Dependencia", "🔄 Cambios de Vales"])
        
        with sub_tab1:
            st.subheader("Resumen de Ingresos y Distribuciones")
            try:
                sheet = conectar_gsheets()
                historial_ws = sheet.worksheet("entregas_semanales")
                historial_datos = historial_ws.get_all_records()
                if historial_datos:
                    df = pd.DataFrame(historial_datos)
                    st.dataframe(df.tail(30), use_container_width=True, hide_index=True)
                else:
                    st.info("📭 No hay movimientos registrados aún")
            except Exception as e:
                st.info("📭 No hay historial disponible")
        
        with sub_tab2:
            st.subheader("Detalle de Entregas por Dependencia")
            try:
                sheet = conectar_gsheets()
                detalle_ws = sheet.worksheet("detalle_entregas")
                detalle_datos = detalle_ws.get_all_records()
                if detalle_datos:
                    df = pd.DataFrame(detalle_datos)
                    st.dataframe(df.tail(30), use_container_width=True, hide_index=True)
                else:
                    st.info("📭 No hay entregas detalladas aún")
            except Exception as e:
                st.info("📭 No hay detalle disponible")
        
        with sub_tab3:
            st.subheader("Historial de Cambios de Vales")
            try:
                sheet = conectar_gsheets()
                cambios_ws = sheet.worksheet("cambios_vales")
                cambios_datos = cambios_ws.get_all_records()
                if cambios_datos:
                    df = pd.DataFrame(cambios_datos)
                    st.dataframe(df.tail(30), use_container_width=True, hide_index=True)
                else:
                    st.info("📭 No hay cambios registrados aún")
            except Exception as e:
                st.info("📭 No hay historial de cambios")
    
    # Footer
    st.markdown("""
    <div class="footer">
        <p>💡 Sistema de Gestión de Vales | Distribución automatizada semanal</p>
        <p>📊 Datos sincronizados con Google Sheets en tiempo real</p>
    </div>
    """, unsafe_allow_html=True)
