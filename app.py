import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import date, datetime, timedelta
import calendar
import time
import re
import io
import base64
from functools import lru_cache
import hashlib

st.set_page_config(page_title="Sistema de Vales", layout="wide")

SHEET_ID = "1nwfjyFdEG06T85HCmouFd279ImyimfcXFZebs07N1gQ"

DENOMINACIONES = [20000, 10000, 3000, 2000, 1000, 500, 100]

# ============================================
# CACHÉ PARA REDUCIR PETICIONES A LA API
# ============================================

class CacheManager:
    """Gestor de caché para reducir peticiones a la API"""
    def __init__(self):
        self.cache = {}
        self.timestamps = {}
        self.ttl = 60  # Tiempo de vida en segundos
    
    def get(self, key):
        """Obtener dato del caché si existe y no ha expirado"""
        if key in self.cache and key in self.timestamps:
            if (datetime.now() - self.timestamps[key]).seconds < self.ttl:
                return self.cache[key]
        return None
    
    def set(self, key, value):
        """Guardar dato en caché"""
        self.cache[key] = value
        self.timestamps[key] = datetime.now()
    
    def clear(self):
        """Limpiar caché"""
        self.cache.clear()
        self.timestamps.clear()

# Inicializar caché en session_state
if "cache_manager" not in st.session_state:
    st.session_state.cache_manager = CacheManager()

# ============================================
# CONFIGURACIÓN DE ESTILO
# ============================================

def aplicar_estilo():
    """Aplica estilos CSS personalizados"""
    st.markdown("""
    <style>
        /* Tarjetas */
        .card {
            background-color: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 15px;
        }
        .card-dark {
            background-color: #2d2d2d;
            color: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            margin-bottom: 15px;
        }
        .badge-success {
            background-color: #28a745;
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 14px;
        }
        .badge-danger {
            background-color: #dc3545;
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 14px;
        }
        .badge-warning {
            background-color: #ffc107;
            color: #212529;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 14px;
        }
        .stat-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
        }
        .stat-card-green {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }
        .stat-card-red {
            background: linear-gradient(135deg, #cb2d3e 0%, #ef473a 100%);
        }
        .stat-card-blue {
            background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
        }
        .main-title {
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .historial-detalle {
            background-color: #f0f2f6;
            border-radius: 10px;
            padding: 15px;
            margin: 10px 0;
        }
        .warning-box {
            background-color: #fff3cd;
            border: 1px solid #ffc107;
            border-radius: 10px;
            padding: 15px;
            margin: 10px 0;
        }
        .diferencia-positiva {
            color: #28a745;
            font-weight: bold;
        }
        .diferencia-negativa {
            color: #dc3545;
            font-weight: bold;
        }
        .diferencia-cero {
            color: #ffc107;
            font-weight: bold;
        }
        .cumplimiento-bueno {
            color: #28a745;
            font-weight: bold;
        }
        .cumplimiento-regular {
            color: #ffc107;
            font-weight: bold;
        }
        .cumplimiento-malo {
            color: #dc3545;
            font-weight: bold;
        }
    </style>
    """, unsafe_allow_html=True)

def conectar_gsheets():
    """Conectar a Google Sheets con reintentos"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
            client = gspread.authorize(creds)
            return client.open_by_key(SHEET_ID)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Backoff exponencial
            else:
                raise e

def limpiar_numero(valor):
    """Limpia y convierte números de diferentes formatos a enteros"""
    if valor is None:
        return 0
    if isinstance(valor, (int, float)):
        return int(valor)
    
    # Si es string, limpiar
    if isinstance(valor, str):
        valor_str = valor.strip()
        if not valor_str:
            return 0
        
        # Eliminar símbolos de moneda y espacios
        valor_str = valor_str.replace("$", "").replace("$ ", "").replace(" ", "").strip()
        
        if not valor_str:
            return 0
        
        try:
            # Manejar diferentes formatos de números
            if "," in valor_str and "." in valor_str:
                if valor_str.rfind(",") > valor_str.rfind("."):
                    valor_str = valor_str.replace(".", "").replace(",", ".")
                else:
                    valor_str = valor_str.replace(",", "")
            elif "," in valor_str:
                partes = valor_str.split(",")
                if len(partes) == 2 and len(partes[1]) <= 2:
                    valor_str = valor_str.replace(",", ".")
                else:
                    valor_str = valor_str.replace(",", "")
            elif "." in valor_str:
                partes = valor_str.split(".")
                if len(partes) == 2 and len(partes[1]) <= 2:
                    pass
                else:
                    valor_str = valor_str.replace(".", "")
            
            # Intentar convertir
            if "." in valor_str:
                return int(float(valor_str))
            else:
                return int(valor_str)
                
        except (ValueError, TypeError):
            # Si falla, intentar extraer solo números
            try:
                numeros = re.findall(r'\d+', valor_str)
                if numeros:
                    return int(''.join(numeros))
            except:
                pass
            return 0
    
    # Si es otro tipo, intentar convertir
    try:
        return int(float(valor))
    except:
        return 0

def calcular_total_caja(stock):
    total = 0
    for denom, cantidad in stock.items():
        total += denom * cantidad
    return total

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
        st.error(f"Error de login: {e}")
        return False

def contar_miercoles(anio, mes):
    count = 0
    for dia in range(1, calendar.monthrange(anio, mes)[1] + 1):
        if calendar.weekday(anio, mes, dia) == 2:
            count += 1
    return count

@st.cache_data(ttl=60)
def obtener_dependencias_cached(anio, mes):
    """Versión cacheada de obtener_dependencias"""
    try:
        sheet = conectar_gsheets()
        ws = sheet.worksheet("dependencias")
        datos = ws.get_all_records()
        dependencias = []
        for d in datos:
            año_dato = limpiar_numero(d.get("año", 0))
            mes_dato = limpiar_numero(d.get("mes", 0))
            monto = limpiar_numero(d.get("monto_mensual", 0))
            nombre = str(d.get("nombre", "")).strip()
            if nombre and año_dato == anio and mes_dato == mes:
                dependencias.append({
                    "id": limpiar_numero(d.get("dependencia_id", 0)),
                    "nombre": nombre,
                    "monto_mensual": monto
                })
        return dependencias
    except Exception as e:
        st.error(f"Error al leer dependencias: {e}")
        return []

def obtener_dependencias(anio=None, mes=None):
    if anio is None or mes is None:
        hoy = date.today()
        anio = hoy.year
        mes = hoy.month
    return obtener_dependencias_cached(anio, mes)

@st.cache_data(ttl=30)
def obtener_stock_cached():
    """Versión cacheada de obtener_stock_actual"""
    try:
        sheet = conectar_gsheets()
        ws = sheet.worksheet("vales_disponibles")
        todos_los_datos = ws.get_all_values()
        stock = {den: 0 for den in DENOMINACIONES}
        for fila in todos_los_datos:
            if len(fila) >= 2:
                col_a = str(fila[0]).strip() if fila[0] else ""
                col_b = str(fila[1]).strip() if len(fila) > 1 and fila[1] else ""
                if not col_a or col_a.lower() in ["denominacion", "denominación", "cantidad", "denomination"]:
                    continue
                denom_limpio = limpiar_numero(col_a)
                cantidad = limpiar_numero(col_b)
                if denom_limpio in stock:
                    stock[denom_limpio] = cantidad
        return stock
    except Exception as e:
        st.error(f"Error al leer stock: {e}")
        return {den: 0 for den in DENOMINACIONES}

def obtener_stock_actual():
    return obtener_stock_cached()

@st.cache_data(ttl=60)
def obtener_detalle_entregas_cached():
    """Versión cacheada de obtener_detalle_entregas"""
    try:
        sheet = conectar_gsheets()
        try:
            detalle_ws = sheet.worksheet("detalle_entregas")
            datos = detalle_ws.get_all_records()
            
            # Limpiar datos - convertir strings a números donde sea posible
            if datos and len(datos) > 0:
                # Identificar columnas numéricas
                columnas_numericas = ["cuota_objetivo", "total_entregado"]
                for d in DENOMINACIONES:
                    columnas_numericas.append(f"vale_{d}")
                
                for fila in datos:
                    for col in columnas_numericas:
                        if col in fila and fila[col] is not None:
                            try:
                                # Intentar convertir a float
                                if isinstance(fila[col], str):
                                    fila[col] = limpiar_numero(fila[col])
                                else:
                                    fila[col] = float(fila[col])
                            except:
                                fila[col] = 0
            
            return datos
        except Exception as e:
            st.warning(f"No se pudo acceder a la hoja detalle_entregas: {e}")
            return []
    except Exception as e:
        st.warning(f"Error al leer detalle de entregas: {e}")
        return []

def obtener_detalle_entregas():
    return obtener_detalle_entregas_cached()

def actualizar_stock(stock_nuevo):
    """Actualiza el stock en Google Sheets"""
    try:
        sheet = conectar_gsheets()
        ws = sheet.worksheet("vales_disponibles")
        
        # Verificar que no haya cantidades negativas
        for denom, cantidad in stock_nuevo.items():
            if cantidad < 0:
                st.error(f"Error: Stock negativo para ${denom}: {cantidad}")
                return False
        
        # Actualizar cada denominación
        for denom, cantidad in stock_nuevo.items():
            cell = ws.find(str(denom))
            if cell:
                ws.update_cell(cell.row, 2, cantidad)
                time.sleep(0.5)  # Pausa para evitar límites de API
        
        # Limpiar caché después de actualizar
        st.cache_data.clear()
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
            return False, f"No hay suficientes vales de ${desde_denom:,.0f}"
        stock_actual[desde_denom] -= desde_cant
        stock_actual[hasta_denom] += hasta_cant
        actualizar_stock(stock_actual)
        registrar_cambio_historial(desde_denom, desde_cant, hasta_denom, hasta_cant)
        return True, "Cambio exitoso"
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
        nueva_fila = [str(date.today()), desde_denom, desde_cant, hasta_denom, hasta_cant, f"Cambio: {desde_cant} x ${desde_denom} por {hasta_cant} x ${hasta_denom}"]
        cambios_ws.append_row(nueva_fila)
        return True
    except Exception as e:
        return False

def registrar_entrega_detallada(fecha, reparto, tipo):
    try:
        sheet = conectar_gsheets()
        try:
            detalle_ws = sheet.worksheet("detalle_entregas")
        except:
            detalle_ws = sheet.add_worksheet(title="detalle_entregas", rows="1000", cols="15")
            encabezados = ["fecha", "dependencia_id", "dependencia_nombre", "cuota_objetivo", "total_entregado", "tipo"]
            for d in DENOMINACIONES:
                encabezados.append(f"vale_{d}")
            detalle_ws.append_row(encabezados)
        
        for ofi in reparto:
            nueva_fila = [
                str(fecha), 
                ofi.get("id", 0), 
                ofi["nombre"], 
                ofi.get("cuota_objetivo", 0), 
                ofi["total"],
                tipo
            ]
            for j, denom in enumerate(DENOMINACIONES):
                nueva_fila.append(ofi["vales"][j])
            detalle_ws.append_row(nueva_fila)
            time.sleep(0.3)
        
        # Limpiar caché después de registrar
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error al registrar detalle: {e}")
        return False

def distribuir_vales_auto(dependencias, stock_actual, miercoles):
    """Distribuye vales automáticamente de forma equitativa"""
    reparto = []
    
    # Calcular cuota semanal para cada dependencia
    for dep in dependencias:
        cuota_semanal = dep["monto_mensual"] / miercoles
        reparto.append({
            "id": dep["id"],
            "nombre": dep["nombre"],
            "cuota_objetivo": cuota_semanal,
            "vales": [0, 0, 0, 0, 0, 0, 0],
            "total": 0,
            "diferencia": 0,
            "porcentaje_cumplido": 0
        })
    
    stock = stock_actual.copy()
    
    # Calcular total a distribuir
    total_cuotas = sum(ofi["cuota_objetivo"] for ofi in reparto)
    total_stock = sum(denom * cantidad for denom, cantidad in stock.items())
    
    # Si no hay suficiente stock, ajustar proporcionalmente
    factor_ajuste = min(1.0, total_stock / total_cuotas) if total_cuotas > 0 else 0
    
    # Función para distribuir vales de una denominación específica
    def distribuir_denominacion(valor_vale, cantidad_disponible, deudores):
        """Distribuye una denominación específica entre los deudores"""
        if cantidad_disponible <= 0 or not deudores:
            return
        
        # Calcular cuántos vales necesita cada deudor
        necesidades = []
        for ofi in deudores:
            deuda = ofi["cuota_objetivo"] * factor_ajuste - ofi["total"]
            if deuda > 0:
                vales_necesarios = int(deuda // valor_vale)
                if vales_necesarios > 0:
                    necesidades.append({
                        "ofi": ofi,
                        "vales_necesarios": vales_necesarios,
                        "deuda": deuda
                    })
        
        if not necesidades:
            return
        
        # Ordenar por deuda mayor (priorizar a los que más deben)
        necesidades.sort(key=lambda x: x["deuda"], reverse=True)
        
        # Distribuir los vales disponibles
        vales_restantes = cantidad_disponible
        for necesidad in necesidades:
            if vales_restantes <= 0:
                break
            
            # Dar la cantidad necesaria o lo que quede
            vales_a_dar = min(necesidad["vales_necesarios"], vales_restantes)
            if vales_a_dar > 0:
                ofi = necesidad["ofi"]
                # Encontrar el índice de la denominación
                idx = DENOMINACIONES.index(valor_vale)
                ofi["vales"][idx] += vales_a_dar
                ofi["total"] += vales_a_dar * valor_vale
                vales_restantes -= vales_a_dar
        
        # Actualizar stock
        stock[valor_vale] = vales_restantes
    
    # Primera pasada: distribuir los vales más grandes primero
    for valor_vale in DENOMINACIONES:
        cantidad_disponible = stock[valor_vale]
        if cantidad_disponible <= 0:
            continue
        
        # Identificar quiénes aún necesitan vales
        deudores = [
            ofi for ofi in reparto 
            if ofi["total"] < ofi["cuota_objetivo"] * factor_ajuste
        ]
        
        if not deudores:
            break
        
        distribuir_denominacion(valor_vale, cantidad_disponible, deudores)
    
    # Segunda pasada: ajustar con los vales más pequeños si sobraron
    for valor_vale in reversed(DENOMINACIONES):
        cantidad_disponible = stock[valor_vale]
        if cantidad_disponible <= 0:
            continue
        
        deudores = [
            ofi for ofi in reparto 
            if ofi["total"] < ofi["cuota_objetivo"] * factor_ajuste
        ]
        
        if not deudores:
            break
        
        distribuir_denominacion(valor_vale, cantidad_disponible, deudores)
    
    # Calcular diferencias y porcentajes
    for ofi in reparto:
        ofi["diferencia"] = ofi["cuota_objetivo"] - ofi["total"]
        ofi["porcentaje_cumplido"] = (ofi["total"] / ofi["cuota_objetivo"] * 100) if ofi["cuota_objetivo"] > 0 else 0
    
    return reparto, stock

def validar_distribucion(reparto, stock_inicial, stock_final):
    """Valida que la distribución sea correcta"""
    # Verificar que el stock final no sea negativo
    for denom, cantidad in stock_final.items():
        if cantidad < 0:
            return False, f"Stock negativo para ${denom}: {cantidad}"
    
    # Verificar que el total entregado no exceda el stock inicial
    total_entregado = sum(ofi["total"] for ofi in reparto)
    total_stock_inicial = sum(denom * cantidad for denom, cantidad in stock_inicial.items())
    total_stock_final = sum(denom * cantidad for denom, cantidad in stock_final.items())
    
    # Permitir una diferencia de hasta $100 por redondeo
    tolerancia = 100
    
    if total_entregado > total_stock_inicial + tolerancia:
        return False, f"Total entregado (${total_entregado:,.0f}) excede stock inicial (${total_stock_inicial:,.0f}) por ${total_entregado - total_stock_inicial:,.0f}"
    
    if abs((total_stock_inicial - total_stock_final) - total_entregado) > tolerancia:
        return False, f"Diferencia de stock (${total_stock_inicial - total_stock_final:,.0f}) no coincide con entregado (${total_entregado:,.0f})"
    
    # Verificar que todas las dependencias tengan al menos algo
    for ofi in reparto:
        if ofi["total"] <= 0 and ofi["cuota_objetivo"] > 0:
            return False, f"La dependencia {ofi['nombre']} no recibió vales"
    
    return True, "Distribución válida"

def registrar_historial(fecha, reparto, tipo, es_ingreso=False, vales_ingresados=None):
    try:
        sheet = conectar_gsheets()
        try:
            historial_ws = sheet.worksheet("entregas_semanales")
        except:
            historial_ws = sheet.add_worksheet(title="entregas_semanales", rows="1000", cols="20")
            historial_ws.append_row(["fecha", "dependencia_id", "vale_100", "vale_500", "vale_1000", "vale_2000", "vale_3000", "vale_10000", "vale_20000", "descripcion"])
        
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
        time.sleep(0.3)
        return True
    except Exception as e:
        st.error(f"Error al registrar historial: {e}")
        return False

# ============================================
# FUNCIONES DE MEJORAS
# ============================================

def mostrar_dashboard(dependencias, stock, total_caja, miercoles):
    st.markdown("---")
    st.subheader("📊 Dashboard Ejecutivo")
    
    total_mensual = sum(dep["monto_mensual"] for dep in dependencias)
    total_semanal = sum(dep["monto_mensual"] / miercoles for dep in dependencias)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <h3>${total_caja:,.0f}</h3>
            <p>💰 Total en Caja</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="stat-card stat-card-green">
            <h3>${total_mensual:,.0f}</h3>
            <p>📅 Total Mensual</p>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="stat-card stat-card-blue">
            <h3>${total_semanal:,.0f}</h3>
            <p>📊 Total Semanal</p>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        diferencia = total_caja - total_semanal
        color = "stat-card-green" if diferencia >= 0 else "stat-card-red"
        st.markdown(f"""
        <div class="stat-card {color}">
            <h3>${diferencia:,.0f}</h3>
            <p>{'✅ Disponible' if diferencia >= 0 else '⚠️ Faltante'}</p>
        </div>
        """, unsafe_allow_html=True)

def mostrar_graficos(reparto):
    if not reparto:
        st.info("No hay datos para mostrar gráficos")
        return
    
    try:
        import plotly.express as px
        
        if not all(isinstance(ofi, dict) and "nombre" in ofi and "total" in ofi and "cuota_objetivo" in ofi for ofi in reparto):
            st.warning("Los datos de distribución no tienen el formato esperado")
            return
        
        st.subheader("📈 Gráfico de Distribución")
        
        df_grafico = pd.DataFrame([
            {
                "Dependencia": str(ofi.get("nombre", "Sin nombre")),
                "Total Entregado": float(ofi.get("total", 0)),
                "Cuota": float(ofi.get("cuota_objetivo", 0))
            }
            for ofi in reparto
        ])
        
        if df_grafico.empty:
            st.info("No hay datos para mostrar en el gráfico")
            return
        
        fig = px.bar(
            df_grafico, 
            x="Dependencia", 
            y=["Total Entregado", "Cuota"],
            title="Distribución por Dependencia",
            barmode="group",
            color_discrete_sequence=["#667eea", "#38ef7d"],
            text_auto=True
        )
        
        fig.update_layout(
            xaxis_tickangle=-45,
            yaxis_title="Monto ($)",
            legend_title="Métrica"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
    except ImportError:
        st.info("📊 Instala plotly para ver gráficos: pip install plotly")
    except Exception as e:
        st.error(f"Error al generar gráfico: {e}")

def descargar_reporte_csv(reparto, fecha):
    if reparto:
        try:
            df_reporte = []
            for ofi in reparto:
                fila = {
                    "Dependencia": ofi.get("nombre", ""),
                    "Cuota_Objetivo": ofi.get("cuota_objetivo", 0),
                    "Total_Entregado": ofi.get("total", 0),
                    "Porcentaje_Cumplido": ofi.get("porcentaje_cumplido", 0)
                }
                for i, denom in enumerate(DENOMINACIONES):
                    if "vales" in ofi and len(ofi["vales"]) > i:
                        fila[f"Vale_{denom}"] = ofi["vales"][i]
                    else:
                        fila[f"Vale_{denom}"] = 0
                df_reporte.append(fila)
            
            df = pd.DataFrame(df_reporte)
            csv = df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            b64 = base64.b64encode(csv).decode()
            href = f'<a href="data:file/csv;base64,{b64}" download="distribucion_{fecha}.csv">⬇️ Descargar Reporte CSV</a>'
            st.markdown(href, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Error al generar reporte CSV: {e}")

def simular_notificacion(mensaje):
    st.success(f"📧 {mensaje}")

def mostrar_historial_detallado():
    """Muestra el historial detallado por dependencia"""
    st.header("📜 Historial Detallado por Dependencia")
    
    try:
        detalle = obtener_detalle_entregas()
    except Exception as e:
        st.error(f"Error al cargar el historial: {e}")
        return
    
    if not detalle:
        st.info("No hay registros de entregas detalladas")
        return
    
    # Convertir a DataFrame y limpiar datos
    df_detalle = pd.DataFrame(detalle)
    
    # Verificar que tiene los datos esperados
    if df_detalle.empty:
        st.info("No hay registros de entregas detalladas")
        return
    
    # Asegurar que las columnas numéricas sean float/int
    columnas_numericas = ["cuota_objetivo", "total_entregado"] + [f"vale_{d}" for d in DENOMINACIONES]
    for col in columnas_numericas:
        if col in df_detalle.columns:
            df_detalle[col] = pd.to_numeric(df_detalle[col], errors='coerce').fillna(0)
    
    # Convertir fecha
    if "fecha" in df_detalle.columns:
        try:
            df_detalle["fecha"] = pd.to_datetime(df_detalle["fecha"])
        except:
            pass
    
    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        if not df_detalle.empty and "fecha" in df_detalle.columns:
            fechas_disponibles = sorted(df_detalle["fecha"].unique(), reverse=True)
            fecha_seleccionada = st.selectbox(
                "📅 Filtrar por fecha",
                options=["Todas"] + [str(f.date()) for f in fechas_disponibles[:20]]
            )
    with col2:
        if not df_detalle.empty and "dependencia_nombre" in df_detalle.columns:
            dependencias_uniq = sorted(df_detalle["dependencia_nombre"].unique())
            dep_seleccionada = st.selectbox(
                "🏢 Filtrar por dependencia",
                options=["Todas"] + dependencias_uniq
            )
    
    # Aplicar filtros
    df_filtrado = df_detalle.copy()
    if fecha_seleccionada and fecha_seleccionada != "Todas":
        df_filtrado = df_filtrado[df_filtrado["fecha"].astype(str).str.contains(fecha_seleccionada)]
    if dep_seleccionada and dep_seleccionada != "Todas":
        df_filtrado = df_filtrado[df_filtrado["dependencia_nombre"] == dep_seleccionada]
    
    if df_filtrado.empty:
        st.info("No hay registros con los filtros seleccionados")
        return
    
    # Mostrar resumen
    st.subheader("📊 Resumen de la Distribución")
    
    total_general = float(df_filtrado["total_entregado"].sum()) if "total_entregado" in df_filtrado.columns else 0
    total_cuotas = float(df_filtrado["cuota_objetivo"].sum()) if "cuota_objetivo" in df_filtrado.columns else 0
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💰 Total Entregado", f"${total_general:,.0f}")
    with col2:
        st.metric("📊 Total Cuotas", f"${total_cuotas:,.0f}")
    with col3:
        st.metric("📈 Diferencia", f"${total_cuotas - total_general:,.0f}")
    
    # Mostrar tabla detallada
    st.subheader("📋 Detalle por Dependencia")
    
    columnas_mostrar = ["fecha", "dependencia_nombre", "cuota_objetivo", "total_entregado", "tipo"]
    for denom in DENOMINACIONES:
        col_name = f"vale_{denom}"
        if col_name in df_filtrado.columns:
            columnas_mostrar.append(col_name)
    
    columnas_existentes = [col for col in columnas_mostrar if col in df_filtrado.columns]
    df_mostrar = df_filtrado[columnas_existentes].copy()
    
    for col in df_mostrar.columns:
        if col not in ["fecha", "dependencia_nombre", "tipo"]:
            try:
                df_mostrar[col] = df_mostrar[col].apply(lambda x: f"${float(x):,.0f}" if pd.notnull(x) and x != 0 else "$0")
            except:
                df_mostrar[col] = df_mostrar[col].apply(lambda x: "$0")
    
    st.dataframe(df_mostrar, use_container_width=True, height=400)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 Descargar historial filtrado (CSV)"):
            try:
                df_descarga = df_filtrado.copy()
                csv = df_descarga.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                b64 = base64.b64encode(csv).decode()
                href = f'<a href="data:file/csv;base64,{b64}" download="historial_detallado.csv">⬇️ Descargar CSV</a>'
                st.markdown(href, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Error al descargar: {e}")
    
    with col2:
        if st.button("📊 Ver gráfico de distribución"):
            try:
                import plotly.express as px
                
                if len(df_filtrado) > 0 and "dependencia_nombre" in df_filtrado.columns and "total_entregado" in df_filtrado.columns:
                    df_agrupado = df_filtrado.groupby("dependencia_nombre").agg({
                        "total_entregado": "sum",
                        "cuota_objetivo": "sum"
                    }).reset_index()
                    
                    df_agrupado["total_entregado"] = pd.to_numeric(df_agrupado["total_entregado"], errors='coerce').fillna(0)
                    df_agrupado["cuota_objetivo"] = pd.to_numeric(df_agrupado["cuota_objetivo"], errors='coerce').fillna(0)
                    
                    if not df_agrupado.empty:
                        fig = px.bar(
                            df_agrupado,
                            x="dependencia_nombre",
                            y=["total_entregado", "cuota_objetivo"],
                            title="Total por Dependencia",
                            barmode="group",
                            color_discrete_sequence=["#667eea", "#38ef7d"],
                            labels={
                                "dependencia_nombre": "Dependencia",
                                "value": "Monto ($)",
                                "variable": "Métrica"
                            }
                        )
                        fig.update_layout(
                            xaxis_tickangle=-45,
                            yaxis_title="Monto ($)"
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("No hay suficientes datos para generar el gráfico")
                else:
                    st.warning("No hay datos suficientes para generar el gráfico")
            except ImportError:
                st.info("📊 Instala plotly para ver gráficos: pip install plotly")
            except Exception as e:
                st.error(f"Error al generar gráfico: {e}")

# ============================================
# FUNCIÓN PARA FORZAR ACTUALIZACIÓN DE CACHÉ
# ============================================

def forzar_actualizacion():
    """Limpia el caché y recarga los datos"""
    st.cache_data.clear()
    if "cache_manager" in st.session_state:
        st.session_state.cache_manager.clear()
    st.rerun()

# ============================================
# INTERFAZ PRINCIPAL
# ============================================

aplicar_estilo()

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
    st.markdown('<p class="main-title">🎫 Sistema de Gestión de Vales</p>', unsafe_allow_html=True)
    st.sidebar.success(f"✅ Usuario: {st.session_state.username}")
    
    if st.sidebar.button("🚪 Cerrar sesión"):
        st.session_state.logged_in = False
        st.rerun()
    
    # Botón para forzar actualización
    if st.sidebar.button("🔄 Forzar actualización de datos"):
        forzar_actualizacion()
        st.success("✅ Datos actualizados")
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 Seleccionar Mes")
    
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    
    hoy = date.today()
    mes_actual = hoy.month
    año_actual = hoy.year
    
    mes_seleccionado = st.sidebar.selectbox("Mes", options=range(1, 13), 
                                            format_func=lambda x: meses[x-1],
                                            index=mes_actual-1)
    año_seleccionado = st.sidebar.number_input("Año", min_value=2020, max_value=2030, value=año_actual)
    
    st.sidebar.markdown("---")
    modo_oscuro = st.sidebar.toggle("🌙 Modo Oscuro", value=False)
    if modo_oscuro:
        st.markdown("""
        <style>
            .stApp {
                background-color: #1a1a2e;
                color: #ffffff;
            }
            .stDataFrame {
                background-color: #16213e;
                color: #ffffff;
            }
            .stMetric {
                background-color: #16213e;
                border-radius: 10px;
                padding: 10px;
            }
            .card {
                background-color: #16213e;
                color: #ffffff;
            }
            .main-title {
                color: #ffffff !important;
                -webkit-text-fill-color: #ffffff !important;
            }
            .historial-detalle {
                background-color: #16213e;
                color: #ffffff;
            }
        </style>
        """, unsafe_allow_html=True)
    
    st.sidebar.markdown("---")
    st.sidebar.info(f"📆 Mostrando datos de {meses[mes_seleccionado-1]} {año_seleccionado}")
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📦 Ingresar Vales", "🔄 Cambiar Vales", "🤖 Distribución Auto", "✏️ Distribución Manual", "💰 Stock Actual", "📜 Historial"])
    
    # ========== TAB 1: INGRESAR VALES ==========
    with tab1:
        st.header("📥 Ingreso de nuevos vales")
        stock_actual = obtener_stock_actual()
        total_caja = calcular_total_caja(stock_actual)
        st.metric("💰 Total en caja", f"${total_caja:,.0f}")
        
        with st.form("ingreso_vales"):
            col1, col2 = st.columns(2)
            with col1:
                v20000 = st.number_input("Vales de $20.000", min_value=0, value=0, step=1)
                v10000 = st.number_input("Vales de $10.000", min_value=0, value=0, step=1)
                v3000 = st.number_input("Vales de $3.000", min_value=0, value=0, step=1)
                v2000 = st.number_input("Vales de $2.000", min_value=0, value=0, step=1)
            with col2:
                v1000 = st.number_input("Vales de $1.000", min_value=0, value=0, step=1)
                v500 = st.number_input("Vales de $500", min_value=0, value=0, step=1)
                v100 = st.number_input("Vales de $100", min_value=0, value=0, step=1)
            fecha_ingreso = st.date_input("Fecha de ingreso", value=date.today())
            total_ingreso = v20000*20000 + v10000*10000 + v3000*3000 + v2000*2000 + v1000*1000 + v500*500 + v100*100
            st.metric("💰 Total a ingresar", f"${total_ingreso:,.0f}")
            if st.form_submit_button("✅ Confirmar Ingreso", type="primary"):
                if total_ingreso > 0:
                    vales_ingreso = {20000: v20000, 10000: v10000, 3000: v3000, 2000: v2000, 1000: v1000, 500: v500, 100: v100}
                    agregar_vales(vales_ingreso)
                    registrar_historial(fecha_ingreso, None, "MANUAL", es_ingreso=True, vales_ingresados=vales_ingreso)
                    st.success(f"✅ Se ingresaron ${total_ingreso:,.0f}")
                    simular_notificacion(f"Ingreso de ${total_ingreso:,.0f} registrado correctamente")
                    forzar_actualizacion()
                else:
                    st.warning("Ingresa al menos un vale")
    
    # ========== TAB 2: CAMBIAR VALES ==========
    with tab2:
        st.header("🔄 Cambiar Vales")
        with st.form("cambio_vales"):
            col1, col2 = st.columns(2)
            with col1:
                desde_denom = st.selectbox("Denominación origen", options=DENOMINACIONES, format_func=lambda x: f"${x:,.0f}")
                desde_cant = st.number_input("Cantidad a sacar", min_value=1, value=1, step=1)
            with col2:
                hasta_denom = st.selectbox("Denominación destino", options=DENOMINACIONES, format_func=lambda x: f"${x:,.0f}")
                hasta_cant = st.number_input("Cantidad a agregar", min_value=1, value=1, step=1)
            if st.form_submit_button("🔄 Ejecutar Cambio", type="primary"):
                if desde_denom == hasta_denom:
                    st.error("No puedes cambiar la misma denominación")
                else:
                    exito, mensaje = cambiar_vales(desde_denom, desde_cant, hasta_denom, hasta_cant)
                    if exito:
                        st.success(mensaje)
                        simular_notificacion(f"Cambio de vales registrado: {mensaje}")
                        forzar_actualizacion()
                    else:
                        st.error(mensaje)
    
    # ========== TAB 3: DISTRIBUCIÓN AUTOMÁTICA ==========
    with tab3:
        st.header("🤖 Distribución Automática Semanal")
        
        dependencias = obtener_dependencias(año_seleccionado, mes_seleccionado)
        stock = obtener_stock_actual()
        total_caja = calcular_total_caja(stock)
        miercoles = contar_miercoles(año_seleccionado, mes_seleccionado)
        
        if dependencias:
            mostrar_dashboard(dependencias, stock, total_caja, miercoles)
        
        if not dependencias:
            st.warning(f"⚠️ No hay dependencias para {meses[mes_seleccionado-1]} {año_seleccionado}")
        else:
            st.info(f"📆 {meses[mes_seleccionado-1]} {año_seleccionado} tiene **{miercoles} miércoles**")
            
            st.subheader("📊 Dependencias")
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
            
            st.subheader("💰 Stock Actual")
            stock_df = pd.DataFrame([{"Denominación": f"${d:,.0f}", "Cantidad": stock.get(d, 0)} for d in DENOMINACIONES])
            st.dataframe(stock_df, use_container_width=True)
            
            fecha_dist = st.date_input("Fecha de distribución (miércoles)", value=date.today())
            if st.button("📦 Calcular Distribución Auto", type="primary"):
                if fecha_dist.weekday() != 2:
                    st.warning("⚠️ La distribución debe hacerse en un miércoles")
                else:
                    reparto, stock_nuevo = distribuir_vales_auto(dependencias, stock, miercoles)
                    st.success("✅ Distribución calculada")
                    
                    mostrar_graficos(reparto)
                    
                    # Mostrar tabla con detalles y porcentajes
                    datos_tabla = []
                    for ofi in reparto:
                        cuota = ofi['cuota_objetivo']
                        total = ofi['total']
                        diferencia = cuota - total
                        porcentaje = ofi.get('porcentaje_cumplido', 0)
                        
                        # Color según el porcentaje
                        if porcentaje >= 100:
                            color = "🟢"  # Verde
                        elif porcentaje >= 80:
                            color = "🟡"  # Amarillo
                        else:
                            color = "🔴"  # Rojo
                        
                        datos_tabla.append({
                            "Dependencia": ofi["nombre"],
                            "Cuota": f"${cuota:,.0f}",
                            "Entregado": f"${total:,.0f}",
                            "Diferencia": f"${diferencia:,.0f}",
                            "% Cumplido": f"{porcentaje:.1f}% {color}",
                            "$20k": ofi["vales"][0],
                            "$10k": ofi["vales"][1],
                            "$3k": ofi["vales"][2],
                            "$2k": ofi["vales"][3],
                            "$1k": ofi["vales"][4],
                            "$500": ofi["vales"][5],
                            "$100": ofi["vales"][6]
                        })
                    st.dataframe(
                        pd.DataFrame(datos_tabla), 
                        use_container_width=True,
                        column_config={
                            "% Cumplido": st.column_config.TextColumn(
                                "% Cumplido",
                                help="Porcentaje de la cuota cumplido"
                            )
                        }
                    )
                    
                    # Mostrar estadísticas de cumplimiento
                    st.subheader("📊 Estadísticas de Cumplimiento")
                    cumplidos = sum(1 for ofi in reparto if ofi["total"] >= ofi["cuota_objetivo"])
                    total_deps = len(reparto)
                    porcentaje_cumplidos = (cumplidos / total_deps * 100) if total_deps > 0 else 0
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("✅ Dependencias cumplidas", f"{cumplidos}/{total_deps}")
                    with col2:
                        st.metric("📊 Porcentaje de cumplimiento", f"{porcentaje_cumplidos:.1f}%")
                    with col3:
                        st.metric("💰 Total entregado", f"${sum(ofi['total'] for ofi in reparto):,.0f}")
                    
                    descargar_reporte_csv(reparto, fecha_dist.strftime("%Y-%m-%d"))
                    
                    st.session_state.reparto = reparto
                    st.session_state.stock_nuevo = stock_nuevo
                    st.session_state.fecha_dist = fecha_dist
            
            # Confirmación antes de guardar
            if 'reparto' in st.session_state:
                with st.container():
                    st.markdown("---")
                    st.subheader("📋 Confirmar Distribución")
                    
                    # Validar la distribución
                    es_valido, mensaje = validar_distribucion(
                        st.session_state.reparto,
                        stock,  # stock inicial
                        st.session_state.stock_nuevo  # stock final
                    )
                    
                    if es_valido:
                        st.success(f"✅ {mensaje}")
                    else:
                        st.error(f"❌ {mensaje}")
                        st.warning("⚠️ Revisa la distribución antes de guardar")
                    
                    # Mostrar resumen
                    total_entregado = sum(ofi["total"] for ofi in st.session_state.reparto)
                    total_cuotas = sum(ofi["cuota_objetivo"] for ofi in st.session_state.reparto)
                    total_diferencia = total_cuotas - total_entregado
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total a entregar", f"${total_entregado:,.0f}")
                    with col2:
                        st.metric("Total cuotas", f"${total_cuotas:,.0f}")
                    with col3:
                        st.metric("Diferencia", f"${total_diferencia:,.0f}")
                    with col4:
                        st.metric("Stock restante", f"${calcular_total_caja(st.session_state.stock_nuevo):,.0f}")
                    
                    # Mostrar detalle de vales usados
                    st.subheader("📊 Resumen de Vales Utilizados")
                    vales_usados = {denom: 0 for denom in DENOMINACIONES}
                    for ofi in st.session_state.reparto:
                        for i, denom in enumerate(DENOMINACIONES):
                            vales_usados[denom] += ofi["vales"][i]
                    
                    vales_df = pd.DataFrame([
                        {
                            "Denominación": f"${d:,.0f}",
                            "Usados": vales_usados[d],
                            "Stock Inicial": stock.get(d, 0),
                            "Stock Final": st.session_state.stock_nuevo.get(d, 0)
                        }
                        for d in DENOMINACIONES
                    ])
                    st.dataframe(vales_df, use_container_width=True)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("❌ Cancelar", use_container_width=True):
                            del st.session_state.reparto
                            del st.session_state.stock_nuevo
                            del st.session_state.fecha_dist
                            st.rerun()
                    with col2:
                        if st.button("✅ Confirmar y Guardar", type="primary", use_container_width=True):
                            if actualizar_stock(st.session_state.stock_nuevo):
                                registrar_historial(st.session_state.fecha_dist, st.session_state.reparto, "AUTO")
                                registrar_entrega_detallada(st.session_state.fecha_dist, st.session_state.reparto, "AUTO")
                                st.success("🎉 Distribución guardada exitosamente")
                                simular_notificacion(f"Distribución del {st.session_state.fecha_dist.strftime('%d/%m/%Y')} guardada")
                                del st.session_state.reparto
                                del st.session_state.stock_nuevo
                                del st.session_state.fecha_dist
                                forzar_actualizacion()
                            else:
                                st.error("❌ Error al guardar la distribución")
    
    # ========== TAB 4: DISTRIBUCIÓN MANUAL ==========
    with tab4:
        st.header("✏️ Distribución Manual Semanal")
        
        dependencias = obtener_dependencias(año_seleccionado, mes_seleccionado)
        if not dependencias:
            st.warning(f"No hay dependencias para {meses[mes_seleccionado-1]} {año_seleccionado}")
        else:
            miercoles = contar_miercoles(año_seleccionado, mes_seleccionado)
            st.info(f"📆 {meses[mes_seleccionado-1]} {año_seleccionado} tiene **{miercoles} miércoles**")
            stock = obtener_stock_actual()
            total_caja = calcular_total_caja(stock)
            st.metric("💰 Total en caja", f"${total_caja:,.0f}")
            st.subheader("💰 Stock Disponible")
            stock_df = pd.DataFrame([{"Denominación": f"${d:,.0f}", "Cantidad": stock.get(d, 0)} for d in DENOMINACIONES])
            st.dataframe(stock_df, use_container_width=True)
            
            if 'manual_asignaciones' not in st.session_state:
                st.session_state.manual_asignaciones = {}
            
            reparto_manual = []
            for dep in dependencias:
                cuota = dep["monto_mensual"] / miercoles
                st.markdown(f"### {dep['nombre']} - Cuota: ${cuota:,.0f}")
                cols = st.columns(7)
                vales_asignados = []
                total_asignado = 0
                for i, denom in enumerate(DENOMINACIONES):
                    with cols[i]:
                        key = f"{dep['id']}_{denom}"
                        cantidad = st.number_input(f"${denom:,.0f}", min_value=0, value=st.session_state.manual_asignaciones.get(key, 0), step=1, key=key)
                        vales_asignados.append(cantidad)
                        total_asignado += cantidad * denom
                st.metric("Total asignado", f"${total_asignado:,.0f}")
                reparto_manual.append({
                    "id": dep["id"], 
                    "nombre": dep["nombre"], 
                    "cuota_objetivo": cuota, 
                    "vales": vales_asignados, 
                    "total": total_asignado
                })
            
            if st.button("✅ Guardar Distribución Manual", type="primary"):
                stock_temp = stock.copy()
                for ofi in reparto_manual:
                    for j, denom in enumerate(DENOMINACIONES):
                        if ofi["vales"][j] > stock_temp.get(denom, 0):
                            st.error(f"No hay suficientes vales de ${denom:,.0f}")
                            st.stop()
                        stock_temp[denom] -= ofi["vales"][j]
                actualizar_stock(stock_temp)
                registrar_historial(date.today(), reparto_manual, "MANUAL")
                registrar_entrega_detallada(date.today(), reparto_manual, "MANUAL")
                st.success("Distribución guardada")
                forzar_actualizacion()
    
    # ========== TAB 5: STOCK ACTUAL ==========
    with tab5:
        st.header("💰 Stock Actual de Vales")
        if st.button("🔄 Refrescar stock"):
            forzar_actualizacion()
        stock = obtener_stock_actual()
        total_caja = calcular_total_caja(stock)
        stock_display = pd.DataFrame([
            {
                "Denominación": f"${d:,.0f}", 
                "Cantidad": stock.get(d, 0), 
                "Total": f"${d * stock.get(d, 0):,.0f}"
            } 
            for d in DENOMINACIONES
        ])
        st.dataframe(stock_display, use_container_width=True)
        st.metric("💵 Total en caja", f"${total_caja:,.0f}")
    
    # ========== TAB 6: HISTORIAL ==========
    with tab6:
        mostrar_historial_detallado()
