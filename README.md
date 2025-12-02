# Análisis de menciones (web + redes sociales)

Script en Python para buscar menciones de un término (persona, marca, concepto) en la web y opcionalmente en X/Twitter, limpiar los textos y obtener las palabras más frecuentes.

## Requisitos
- Python 3.11 o superior recomendado.

## Crear y activar un entorno virtual
### Windows (PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

### macOS / Linux
```bash
python -m venv .venv
source .venv/bin/activate
```

## Instalación de dependencias
```bash
pip install -r requirements.txt
```

## Uso
Ejecuta el script y responde a las preguntas en consola:
```bash
python analisis_menciones.py
```

El programa solicita:
1. Término o nombre a analizar.
2. Fecha de inicio (YYYY-MM-DD).
3. Fecha de fin (YYYY-MM-DD).
4. Cantidad máxima de resultados web.
5. Si deseas incluir redes sociales (s/n). Si respondes "s", se solicitará la cantidad máxima de resultados de redes.

## Fuentes de datos
- **Web:** Usa `duckduckgo-search` para obtener resultados y extrae texto de las páginas con `requests` + `BeautifulSoup`.
- **Redes sociales (opcional X/Twitter):** Usa `twscrape`. Debes tener cuentas configuradas en la base de datos local de la librería (consulta la documentación de twscrape para loguear cuentas antes de ejecutar el script). Si no se configuran o falla la autenticación, el programa continúa solo con datos web.

## Archivos de salida
- `resultados_fuentes_crudos.csv`: contiene todos los textos obtenidos (web y redes) con columnas de fuente, título/snippet, texto y URL.
- `frecuencias_palabras.csv`: ranking completo de palabras con sus frecuencias después de la limpieza y exclusiones.

## Notas y consideraciones
- Respeta los términos de servicio de cada sitio o plataforma al recolectar información.
- El uso de datos debe cumplir las normativas legales aplicables (protección de datos, propiedad intelectual, etc.).
- La calidad de los resultados depende de la disponibilidad de contenido público y de la configuración de credenciales en el caso de X/Twitter.
