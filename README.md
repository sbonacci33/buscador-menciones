# Análisis de menciones en la web

Este proyecto ofrece un script en Python para buscar un término en la web, extraer el texto de las páginas encontradas y obtener tanto el número de menciones del término como las palabras más frecuentes del contenido relacionado. Está pensado para principiantes: cada paso del flujo está comentado y explicado.

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
Instala todas las dependencias con:
```bash
pip install -r requirements.txt
```

## Uso básico
Ejecuta el script y completa los datos solicitados en consola:
```bash
python analisis_menciones.py
```
El programa pedirá:
1. **Término o nombre a analizar.**
2. **Fecha de inicio (YYYY-MM-DD).**
3. **Fecha de fin (YYYY-MM-DD).**
4. **Cantidad máxima de resultados web.**

## ¿Qué hace internamente?
1. **Búsqueda web con DuckDuckGo (`ddgs`).** Obtiene URLs, títulos y snippets. El filtro de fechas es aproximado porque la API no ofrece un filtro exacto por rango.
2. **Descarga de cada página.** Usa `requests` para obtener el HTML y `BeautifulSoup` para concatenar todos los párrafos (`<p>`).
3. **Filtro por término.** Solo se conservan las páginas cuyo texto contiene el término exacto (ignorando mayúsculas/minúsculas).
4. **Conteo de menciones.** Cuenta cuántas veces aparece el término completo en cada página.
5. **Limpieza de texto.** Convierte a minúsculas, quita URLs, hashtags, menciones, números, puntuación y acentos.
6. **Stopwords en español.** Se descargan automáticamente si no están disponibles (NLTK). También se excluyen las palabras que forman el término buscado y las palabras muy cortas (<=2 caracteres).
7. **Frecuencias.** Calcula las palabras más repetidas (por defecto las 30 más frecuentes) usando `collections.Counter`.
8. **Salida a archivos.**
   - `paginas_web.csv`: filas con fuente, título, URL, fecha (si se dispone), número de menciones y texto completo.
   - `frecuencias_palabras.csv`: ranking de palabras y sus frecuencias, ordenado de mayor a menor.

## Ejemplo breve de ejecución
```
=== Análisis de menciones en la web ===
Ingrese el término o nombre a analizar (ej: Lionel Messi): Lionel Messi
Ingrese la fecha de inicio (YYYY-MM-DD): 2024-01-01
Ingrese la fecha de fin (YYYY-MM-DD): 2024-12-31
Ingrese la cantidad máxima de resultados web (ej: 50): 50
```

## Archivos de salida
- **`paginas_web.csv`**: información detallada de cada página analizada.
- **`frecuencias_palabras.csv`**: listado de palabras frecuentes tras limpiar los textos.

## Nota sobre el respeto a los sitios consultados
Utiliza el script de forma responsable y respeta los términos de servicio de los sitios visitados. Evita cargas excesivas y cumple la normativa legal aplicable.
