# PyAppy-ML-Consultora
Fidelización de clientes con potencial a convertirse en clientes de alto valor mediante un sistema de recomendación

## Requisitos

- **Python 3.12 o superior.** La versión de numpy de `requirements.txt` no se instala en 3.11 ni en versiones anteriores. Revisa la tuya con `python3 --version` (en Windows, `python --version`).
- El dataset [Pakistan's Largest E-Commerce Dataset (Kaggle)](https://www.kaggle.com/datasets/zusmani/pakistans-largest-ecommerce-dataset). No se sube al repo.

## Instalación

Desde la raíz del repo:

```bash
# Mac / Linux
python3 -m venv PyAppy
source PyAppy/bin/activate

# Windows
python -m venv PyAppy
PyAppy\Scripts\activate

# Ambos
pip install -r requirements.txt
```

Después descarga el CSV de Kaggle y guárdalo **con este nombre exacto**:

```
data/raw/Pakistan Largest Ecommerce Dataset.csv
```

## ETL: generar el dataset limpio

Abre `notebooks/01_ETL.ipynb` y ejecútalo de principio a fin. **En VS Code o Jupyter, elige como kernel el Python del entorno `PyAppy/`.** Con otro Python va a faltar `pyarrow` y el guardado falla.

También se puede ejecutar desde la terminal, con el entorno activado:

```bash
jupyter nbconvert --to notebook --execute --inplace notebooks/01_ETL.ipynb
```

Genera `data/processed/transacciones_limpias.parquet` (582.701 filas), que es la entrada del EDA y del modelado. Para leerlo:

```python
import pandas as pd
df = pd.read_parquet("data/processed/transacciones_limpias.parquet")
compras = df[df["es_compra_valida"]]   # solo compras concretadas
```

La documentación del ETL está en `docs/`:
- `diccionario_datos.md`: qué significa cada columna.
- `decisiones_etl.md`: cada decisión de limpieza, su criterio y su impacto.
- `bitacora_etl.md`: filas afectadas en cada paso (la regenera el notebook).

## Tests

Desde la raíz del repo, con el entorno activado:

```bash
pytest              # todos los tests
pytest -v           # con el nombre de cada test
pytest -m "not datos"   # solo los casos borde (no necesitan el dataset)
```

El test de integridad del dataset real se salta solo si todavía no se ejecutó el notebook.

## Estructura

```
data/raw/        # CSV de Kaggle (no se sube)
data/processed/  # salida del ETL (no se sube)
notebooks/       # 01_ETL, 02_EDA, 03_modelado
src/             # funciones reutilizables (limpieza.py)
tests/           # tests de src/
docs/            # diccionario de datos y decisiones
```
