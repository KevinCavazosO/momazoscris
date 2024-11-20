from flask import Flask, render_template, jsonify, request
import yfinance as yf
import pandas as pd
from datetime import datetime
import traceback
import numpy as np
from scipy import stats

app = Flask(__name__)

# Sugerencias de símbolos populares de la BMV
SIMBOLOS_SUGERIDOS = {
    'FEMSA': 'FEMSA.MX',
    'WALMEX': 'WALMEX.MX',
    'BIMBO': 'BIMBOA.MX',
    'TLEVISA': 'TLEVICPO.MX',
    'AMX': 'AMXL.MX',
    'CEMEX': 'CEMEXCPO.MX',
    'GFNORTE': 'GFNORTEO.MX',
    'GMXT': 'GMXT.MX',
    'ORBIA': 'ORBIA.MX',
    'ELEKTRA': 'ELEKTRA.MX'
}


def formatear_simbolo(simbolo, mercado=None):
    """
    Formatea el símbolo según el mercado especificado
    """
    simbolo = simbolo.upper().strip()

    # Si es un símbolo sugerido de BMV, usar el mapeo existente
    if simbolo in SIMBOLOS_SUGERIDOS:
        return SIMBOLOS_SUGERIDOS[simbolo]

    # Si no se especifica mercado, intentar sin sufijo
    if not mercado:
        return simbolo

    # Mapeo de mercados a sufijos
    sufijos_mercado = {
        'BMV': '.MX',
        'NYSE': '',
        'NASDAQ': '',
        'LON': '.L',
        'TSX': '.TO',
    }

    sufijo = sufijos_mercado.get(mercado.upper(), '')
    return f"{simbolo}{sufijo}"


def calcular_recomendacion(hist, info):
    """
    Calcula la recomendación de inversión basada en análisis técnico y fundamental
    """
    # Calcular volatilidad
    rendimientos_diarios = hist['Close'].pct_change()
    volatilidad = rendimientos_diarios.std() * np.sqrt(252)  # Anualizada

    # Calcular tendencia (usando regresión lineal)
    x = np.arange(len(hist['Close']))
    slope, _, r_value, _, _ = stats.linregress(x, hist['Close'])
    tendencia = slope > 0
    r_squared = r_value ** 2

    # Calcular métricas fundamentales
    pe_ratio = info.get('forwardPE', 0)
    dividend_yield = info.get('dividendYield', 0) if info.get('dividendYield') else 0

    # Sistema de puntuación
    score = 0
    razones = []

    # Evaluar tendencia
    if tendencia:
        score += 2
        razones.append("La acción muestra una tendencia alcista")

    # Evaluar consistencia de la tendencia
    if r_squared > 0.7:
        score += 1
        razones.append("La tendencia es consistente")

    # Evaluar volatilidad
    if volatilidad < 0.3:  # 30% es un umbral común
        score += 2
        razones.append("La volatilidad es moderada")

    # Evaluar ratio P/E
    if 10 < pe_ratio < 25:  # Rango PE razonable
        score += 1
        razones.append("El ratio P/E está en un rango saludable")

    # Evaluar dividendos
    if dividend_yield > 0.02:  # 2% o más
        score += 1
        razones.append("Ofrece un dividendo atractivo")

    # Determinar recomendación basada en el score total
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


def analizar_accion(simbolo, mercado=None):
    """
    Analiza una acción y retorna información detallada sobre ella
    """
    try:
        simbolo_formateado = formatear_simbolo(simbolo, mercado)
        print(f"Intentando obtener datos para: {simbolo_formateado}")

        # Obtener datos de Yahoo Finance
        accion = yf.Ticker(simbolo_formateado)
        hist = accion.history(period="6mo")
        info = accion.info

        # Verificar si se encontraron datos
        if hist.empty:
            return {
                "error": f"No se encontraron datos para el símbolo {simbolo_formateado}. " +
                         "Verifica que el símbolo y el mercado sean correctos."
            }

        # Calcular métricas básicas
        precio_actual = hist['Close'][-1]
        precio_inicial = hist['Close'][0]
        rendimiento = ((precio_actual - precio_inicial) / precio_inicial) * 100

        # Obtener información adicional de la empresa
        nombre_empresa = info.get('longName', simbolo_formateado)
        descripcion = info.get('longBusinessSummary', 'Información no disponible')
        logo_url = info.get('logo_url', '')

        # Calcular recomendación
        analisis = calcular_recomendacion(hist, info)

        # Preparar respuesta
        return {
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
    except Exception as e:
        print(f"Error completo: {traceback.format_exc()}")
        return {
            "error": "Error al analizar la acción. Por favor, verifica el símbolo y el mercado e intenta de nuevo."
        }


@app.route('/')
def home():
    """Ruta principal que muestra la interfaz de usuario"""
    return render_template('index.html', simbolos=SIMBOLOS_SUGERIDOS)


@app.route('/api/analizar')
def api_analizar():
    """API endpoint para analizar una acción"""
    simbolo = request.args.get('simbolo', '')
    mercado = request.args.get('mercado', None)

    if not simbolo:
        return jsonify({"error": "Por favor, proporciona un símbolo de acción."})

    resultado = analizar_accion(simbolo, mercado)
    return jsonify(resultado)


if __name__ == '__main__':
    app.run(debug=True)