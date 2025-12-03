# Buscador de menciones web (MVP estilo SaaS)

Plataforma modular en Python para monitorear menciones de marcas, personas o proyectos en la web. Utiliza DuckDuckGo (`ddgs`) como fuente inicial, persiste resultados en SQLite y ofrece un tablero profesional en Streamlit listo para evolucionar hacia un producto SaaS.

## Arquitectura de carpetas

- `analisis_core.py`: lógica de negocio (búsqueda, conteo de menciones, estadísticas y palabras asociadas).
- `fuentes_web.py`: integración con motores de búsqueda (ddgs real + stubs para Brave, Bing, Google CSE y SerpAPI).
- `datos_repository.py`: capa de persistencia con SQLAlchemy/SQLite (paginas, terminos, menciones).
- `config.py`: configuración vía variables de entorno o `.env` (URL de BD y claves futuras).
- `analisis_menciones_app.py`: tablero Streamlit con filtros, KPIs, tablas y descargas.
- `requirements.txt`: dependencias necesarias.

### Diagrama simple (texto)
```
[Streamlit UI]
      |
      v
[analisis_core] --- [fuentes_web] (ddgs, stubs otras APIs)
      |
      v
[datos_repository] -> SQLite (persistencia y métricas históricas)
```

## Requisitos
- Python 3.11+
- Acceso a Internet para búsquedas con ddgs y descarga de páginas.

## Instalación y ejecución
1. Crear entorno virtual (ejemplo Linux/macOS):
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
   En Windows (PowerShell):
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   ```
2. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. (Opcional) Configurar `.env` para cambiar la base de datos o agregar claves de API:
   ```env
   DATABASE_URL=sqlite:///menciones.db
   BRAVE_API_KEY=...
   BING_API_KEY=...
   SERPAPI_KEY=...
   ```
4. Ejecutar el tablero:
   ```bash
   python -m streamlit run analisis_menciones_app.py
   ```

## Uso del tablero
- Define hasta cinco términos asociados (se combinan en la query).
- Elige profundidad (`Rápido`, `Normal`, `Profundo`) que mapea a 50/100/200 resultados.
- Selecciona modo de coincidencia: frase exacta, todas las palabras o cualquiera.
- (Opcional) Filtra por dominio (ej. `clarin.com`).
- Pulsa **Analizar** para ver KPIs, top de palabras asociadas, páginas, dominios y descargas CSV/JSON.

## Comportamiento y consideraciones
- Se usa `ddgs` con `safesearch="moderate"` y sin parámetros obsoletos.
- Cada URL se descarga una vez y se guarda en SQLite con su dominio, título y texto para construir memoria histórica.
- Los conteos de menciones se almacenan por página y término (relación página–término).
- La limpieza de texto elimina URLs, menciones, números y tildes; se usan stopwords en español (NLTK) y se excluyen palabras de los términos buscados.
- El análisis trabaja sobre una muestra de resultados (no toda la web) para un crawling respetuoso.

## Extensiones futuras
- Implementar llamadas reales a Brave, Bing, Google CSE o SerpAPI en `fuentes_web.py` usando las claves de configuración.
- Añadir TF-IDF o n-gramas avanzados para relevancia de términos.
- Migrar SQLite a PostgreSQL cambiando `DATABASE_URL` en `.env`.

## Nota de uso responsable
Utiliza la herramienta respetando términos de servicio de los buscadores y sitios web. Evita ráfagas de peticiones y considera backoff o caché adicional si amplías la profundidad.
