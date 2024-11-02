# app.py

from flask import Flask, render_template, jsonify, request
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import traceback
import numpy as np
from scipy import stats
import os
from functools import lru_cache
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)

# Cache configuration
CACHE_DURATION = 300  # 5 minutos en segundos

# Símbolos populares de la BMV
SIMBOLOS_SUGERIDOS = {
    'FEMSA': 'KOFUBL.MX',
    'WALMEX': 'WALMEX.MX',
    'BIMBO': 'BIMBOA.MX',
    'TLEVISA': 'TLEVISACPO.MX',
    'AMX': 'AMXB.MX',
    'CEMEX': 'CEMEXCPO.MX',
    'GFNORTE': 'GFNORTEO.MX',
    'GMXT': 'GMXT.MX',
    'ORBIA': 'ORBIA.MX',
    'ELEKTRA': 'ELEKTRA.MX'
}

class DataCache:
    def __init__(self):
        self.cache = {}
        self.timestamps = {}

    def get(self, key):
        if key in self.cache:
            if datetime.now() - self.timestamps[key] < timedelta(seconds=CACHE_DURATION):
                return self.cache[key]
            else:
                del self.cache[key]
                del self.timestamps[key]
        return None

    def set(self, key, value):
        self.cache[key] = value
        self.timestamps[key] = datetime.now()

cache = DataCache()

def formatear_simbolo(simbolo, mercado=None):
    """
    Formatea el símbolo según el mercado especificado
    """
    try:
        simbolo = simbolo.upper().strip()

        if simbolo in SIMBOLOS_SUGERIDOS:
            return SIMBOLOS_SUGERIDOS[simbolo]

        if not mercado:
            return simbolo

        sufijos_mercado = {
            'BMV': '.MX',
            'NYSE': '',
            'NASDAQ': '',
            'LON': '.L',
            'TSX': '.TO',
        }

        sufijo = sufijos_mercado.get(mercado.upper(), '')
        return f"{simbolo}{sufijo}"
    except Exception as e:
        app.logger.error(f"Error al formatear símbolo: {str(e)}")
        return simbolo

def calcular_recomendacion(hist, info):
    """
    Calcula la recomendación de inversión basada en análisis técnico y fundamental
    """
    try:
        # Calcular volatilidad
        rendimientos_diarios = hist['Close'].pct_change()
        volatilidad = rendimientos_diarios.std() * np.sqrt(252)

        # Calcular tendencia
        x = np.arange(len(hist['Close']))
        slope, _, r_value, _, _ = stats.linregress(x, hist['Close'])
        tendencia = slope > 0
        r_squared = r_value ** 2

        # Métricas fundamentales
        pe_ratio = info.get('forwardPE', 0)
        dividend_yield = info.get('dividendYield', 0) if info.get('dividendYield') else 0

        # Sistema de puntuación
        score = 0
        razones = []

        if tendencia:
            score += 2
            razones.append("La acción muestra una tendencia alcista")

        if r_squared > 0.7:
            score += 1
            razones.append("La tendencia es consistente")

        if volatilidad < 0.3:
            score += 2
            razones.append("La volatilidad es moderada")

        if 10 < pe_ratio < 25:
            score += 1
            razones.append("El ratio P/E está en un rango saludable")

        if dividend_yield > 0.02:
            score += 1
            razones.append("Ofrece un dividendo atractivo")

        # Determinar recomendación
        if score >= 5:
            recomendacion = "Comprar"
            nivel_riesgo = "Bajo"
            inversion_sugerida = "Se sugiere invertir hasta un 5% de tu portafolio"
        elif score >= 3:
            recomendacion = "Mantener"
            nivel_riesgo = "Moderado"
            inversion_sugerida = "Se sugiere invertir hasta un 3% de tu portafolio"
        else:
            recomendacion = "Esperar"
            nivel_riesgo = "Alto"
            inversion_sugerida = "No se recomienda invertir en este momento"

        return {
            "recomendacion": recomendacion,
            "nivel_riesgo": nivel_riesgo,
            "inversion_sugerida": inversion_sugerida,
            "razones": razones,
            "score": score
        }
    except Exception as e:
        app.logger.error(f"Error en cálculo de recomendación: {str(e)}")
        return {
            "recomendacion": "No disponible",
            "nivel_riesgo": "No determinado",
            "inversion_sugerida": "No es posible hacer una recomendación",
            "razones": ["Error en el análisis"],
            "score": 0
        }

def analizar_accion(simbolo, mercado=None):
    """
    Analiza una acción y retorna información detallada
    """
    try:
        simbolo_formateado = formatear_simbolo(simbolo, mercado)
        cache_key = f"{simbolo_formateado}_{mercado}"
        
        # Intentar obtener del cache
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result

        app.logger.info(f"Obteniendo datos para: {simbolo_formateado}")
        
        accion = yf.Ticker(simbolo_formateado)
        hist = accion.history(period="6mo")
        info = accion.info

        if hist.empty:
            return {
                "error": f"No se encontraron datos para el símbolo {simbolo_formateado}."
            }

        # Calcular métricas
        precio_actual = hist['Close'][-1]
        precio_inicial = hist['Close'][0]
        rendimiento = ((precio_actual - precio_inicial) / precio_inicial) * 100

        # Información de la empresa
        nombre_empresa = info.get('longName', simbolo_formateado)
        descripcion = info.get('longBusinessSummary', 'Información no disponible')
        logo_url = info.get('logo_url', '')

        # Calcular recomendación
        analisis = calcular_recomendacion(hist, info)

        resultado = {
            "simbolo": simbolo_formateado,
            "nombre_empresa": nombre_empresa,
            "precio_actual": round(precio_actual, 2),
            "rendimiento_periodo": round(rendimiento, 2),
            "volumen_promedio": int(hist['Volume'].mean()),
            "precio_maximo": round(hist['High'].max(), 2),
            "precio_minimo": round(hist['Low'].min(), 2),
            "precios": hist['Close'].tolist(),
            "fechas": hist.index.strftime('%Y-%m-%d').tolist(),
            "descripcion": descripcion,
            "logo_url": logo_url,
            "recomendacion": analisis["recomendacion"],
            "nivel_riesgo": analisis["nivel_riesgo"],
            "inversion_sugerida": analisis["inversion_sugerida"],
            "razones_analisis": analisis["razones"]
        }

        # Guardar en cache
        cache.set(cache_key, resultado)
        
        return resultado

    except Exception as e:
        app.logger.error(f"Error en análisis de acción: {traceback.format_exc()}")
        return {
            "error": "Error al analizar la acción. Por favor, verifica el símbolo y el mercado."
        }

@app.route('/')
def home():
    """Ruta principal"""
    return render_template('index.html', simbolos=SIMBOLOS_SUGERIDOS)

@app.route('/api/analizar')
def api_analizar():
    """API endpoint para análisis"""
    simbolo = request.args.get('simbolo', '')
    mercado = request.args.get('mercado', None)

    if not simbolo:
        return jsonify({"error": "Por favor, proporciona un símbolo de acción."}), 400

    resultado = analizar_accion(simbolo, mercado)
    if "error" in resultado:
        return jsonify(resultado), 404
    return jsonify(resultado)

@app.route('/health')
def health_check():
    """Health check endpoint para monitoreo"""
    return jsonify({'status': 'healthy'}), 200

@app.errorhandler(404)
def not_found_error(error):
    """Manejador de error 404"""
    return jsonify({'error': 'Recurso no encontrado'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Manejador de error 500"""
    app.logger.error(f'Error del servidor: {error}')
    return jsonify({'error': 'Error interno del servidor'}), 500

if __name__ == '__main__':
    # Configuración para desarrollo
    if os.environ.get('FLASK_ENV') == 'development':
        app.run(debug=True)
    else:
        # Configuración para producción
        port = int(os.environ.get("PORT", 5000))
        app.run(host='0.0.0.0', port=port)
