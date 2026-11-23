"""Tests de src/limpieza.py.

Ejecutar desde la raíz del repo:
    pytest                # todos los tests
    pytest -m "not datos" # solo los casos borde (no necesitan el CSV)

1. Casos borde: un CSV sintético de pocas filas en el que cada fila es un caso
   raro a propósito. Se procesa con `pipeline_etl`, el mismo punto de entrada
   que el notebook, así que también se prueba la lectura con `read_csv`.
2. Integridad del dataset real (marca `datos`): se saltean si no está el
   parquet generado por notebooks/01_ETL.ipynb.
"""

from pathlib import Path

import pandas as pd
import pytest

from src import limpieza as lp

RAIZ = Path(__file__).resolve().parents[1]
PARQUET = RAIZ / "data/processed/transacciones_limpias.parquet"

# Mismo encabezado que el CSV de Kaggle (incluye ' MV ' con espacios y las
# columnas vacías del final).
ENCABEZADO = ("item_id,status,created_at,sku,price,qty_ordered,grand_total,increment_id,"
              "category_name_1,sales_commission_code,discount_amount,payment_method,"
              "Working Date,BI Status, MV ,Year,Month,Customer Since,M-Y,FY,Customer ID,,,,,")

# item, status, fecha, sku, price, qty, grand_total, pedido, categoría, comisión,
# descuento, pago, customer_since, customer_id  →  qué caso borde representa
FILAS = [
    (1, "complete", "7/1/2016", "A", 100, 1, 90, "10", "Books", r"\N", 10, "COD", "2016-7", 1),       # normal
    (2, " canceled ", "12/31/2017", "B", 50, 2, 100, "11", r"\N", "R-1", -3, "Easypay", "2017-12", 2),  # espacios, \N, desc < 0
    (3, r"\N", "1/5/2018", "C", 10, 1, 10, "12", "Soghaat", r"\N", 0, "cod", "2016-1", 3),            # status \N
    (4, "received", "2/28/2018", "A", 100, 200, -5, "13", "", r"\N", 30000, "cod", "2016-7", 1),       # desc > bruto, qty 200, total < 0
    (5, "complete", "8/28/2018", " D ", 0, 1, 0, "14", r"\N", "NA", 0, "cod", "2018-8", 4),           # precio 0, sku con espacios
    (6, "cod", "3/1/2017", "E", 20, 1, 20, "15-1", "Others", "X", 0, "cod", "#N/A", "#N/A"),          # cliente '#N/A' (error de Excel)
    (8, "complete", "7/1/2016", "test-product-3", 5, 1, 5, "16", "", r"\N", 0, "cod", "2016-7", 9),   # producto de prueba
    (9, "complete", "7/1/2016", "Z", 100, 1, 100, "17", "Books", r"\N", 0, "cod", "2016-7", 9),       # cliente 9: 50 % prueba
    (10, "complete", "7/1/2016", "SKMT_Blood Test", 500, 1, 500, "18", "Others", r"\N", 0, "cod", "2016-7", 1),  # real con "test"
]


def _linea(f):
    item, st, fecha, sku, p, q, gt, ped, cat, com, desc, pago, desde, cli = f
    cols = [item, st, fecha, sku, p, q, gt, ped, cat, com, desc, pago,
            fecha, "Net", f" {p * q} ", 2016, 7, desde, "7-2016", "FY17", cli, "", "", "", "", ""]
    return ",".join(f'"{c}"' if isinstance(c, str) and c.strip() != c else str(c) for c in cols)


@pytest.fixture(scope="module")
def resultado(tmp_path_factory):
    """Corre el pipeline completo sobre el CSV sintético (más una fila vacía)."""
    ruta = tmp_path_factory.mktemp("datos") / "crudo.csv"
    vacia = "," * (ENCABEZADO.count(","))
    ruta.write_text("\n".join([ENCABEZADO, *map(_linea, FILAS), vacia]) + "\n", encoding="utf-8")
    df, log = lp.pipeline_etl(str(ruta))
    return df.set_index("item_id"), log


# ---------------------------------------------------------------- filas eliminadas
def test_elimina_fila_vacia_y_columnas_vacias(resultado):
    df, _ = resultado
    assert not any(c.startswith("unnamed") for c in df.columns)


def test_elimina_status_marcador_mysql(resultado):
    assert 3 not in resultado[0].index


def test_elimina_cliente_error_excel(resultado):
    assert 6 not in resultado[0].index


def test_elimina_producto_de_prueba(resultado):
    assert 8 not in resultado[0].index


def test_conserva_producto_real_con_test_en_el_nombre(resultado):
    assert 10 in resultado[0].index


def test_bitacora_cuadra_con_filas(resultado):
    df, log = resultado
    filas_crudas = log[0]["filas_antes"]
    assert sum(p["filas_eliminadas"] for p in log) == filas_crudas - len(df)


# ---------------------------------------------------------------- texto y tipos
def test_quita_espacios(resultado):
    df, _ = resultado
    assert df.loc[2, "status"] == "canceled"
    assert df.loc[5, "sku"] == "D"


def test_payment_method_en_minusculas(resultado):
    assert resultado[0].loc[1, "payment_method"] == "cod"


def test_fechas_mes_dia(resultado):
    df, _ = resultado
    assert df.loc[2, "created_at"] == pd.Timestamp("2017-12-31")
    assert df.loc[2, "customer_since"] == pd.Timestamp("2017-12-01")


def test_columnas_y_tipos_finales(resultado):
    df, _ = resultado
    assert list(df.reset_index().columns) == lp.ORDEN_COLUMNAS
    assert str(df["customer_id"].dtype) == "Int64"
    assert df["es_compra_valida"].dtype == bool


# ---------------------------------------------------------------- nulos e imputación
def test_categoria_imputada_por_sku(resultado):
    # item 4 (sku A) no tiene categoría; el item 1 (mismo sku) es Books
    assert resultado[0].loc[4, "category_name_1"] == "Books"


def test_categoria_sin_referencia_es_desconocida(resultado):
    assert resultado[0].loc[2, "category_name_1"] == lp.CATEGORIA_DESCONOCIDA


def test_codigo_comision(resultado):
    df, _ = resultado
    assert df.loc[2, "uso_codigo_comision"]       # 'R-1'
    assert not df.loc[1, "uso_codigo_comision"]   # '\N'
    assert not df.loc[5, "uso_codigo_comision"]   # 'NA' → sin código


def test_sin_nulos(resultado):
    assert resultado[0].isna().sum().sum() == 0


# ---------------------------------------------------------------- valores inválidos
def test_descuento_negativo_a_cero(resultado):
    assert resultado[0].loc[2, "discount_amount"] == 0


def test_descuento_mayor_al_bruto(resultado):
    df, _ = resultado
    assert df.loc[4, "descuento_inconsistente"]
    assert df.loc[4, "monto_linea"] == 0          # recortado, nunca negativo


def test_montos(resultado):
    df, _ = resultado
    assert df.loc[1, "monto_bruto"] == 100
    assert df.loc[1, "monto_linea"] == 90
    assert (df["monto_linea"] >= 0).all()


def test_banderas_de_valores_atipicos(resultado):
    df, _ = resultado
    assert df.loc[4, "qty_atipica"] and df.loc[4, "grand_total_negativo"]
    assert df.loc[5, "precio_cero"]


# ---------------------------------------------------------------- compra válida y cuentas
def test_compra_valida(resultado):
    df, _ = resultado
    assert df.loc[1, "es_compra_valida"]          # complete, precio > 0
    assert not df.loc[2, "es_compra_valida"]      # canceled
    assert not df.loc[5, "es_compra_valida"]      # complete pero precio 0


def test_cuenta_interna(resultado):
    df, _ = resultado
    assert df.loc[9, "cuenta_interna_probable"]       # cliente 9: 1 de 2 compras era de prueba
    assert not df.loc[1, "cuenta_interna_probable"]   # cliente 1: ninguna


@pytest.mark.parametrize("sku, es_prueba", [
    ("test-product", True), ("test-product-00", True), ("test bundle product-test-product", True),
    ("Test Hazir Product-Karachi", True), ("test_tcsconnect", True),
    ("AhadTest Cnfg pricechange Discounted-MED", True), ("product_margin_test", True),
    ("SKMT_Blood Test", False), ("Aladdin_Test Star Cricket Ball - Red & White", False),
    ("sst_Vous Deteste-Regular fit-Medium", False), ("Apple iPhone 6S 64GB", False),
])
def test_patron_producto_prueba(sku, es_prueba):
    assert bool(pd.Series([sku]).str.contains(lp.PATRON_PRODUCTO_PRUEBA, regex=True)[0]) is es_prueba


# ---------------------------------------------------------------- dataset real
@pytest.mark.datos
@pytest.mark.skipif(not PARQUET.exists(), reason="Falta el parquet: ejecutar notebooks/01_ETL.ipynb")
def test_integridad_dataset_real():
    df = pd.read_parquet(PARQUET)
    assert list(df.columns) == lp.ORDEN_COLUMNAS
    assert df.isna().sum().sum() == 0
    assert df["item_id"].is_unique
    assert (df["monto_linea"] >= 0).all()
    assert not df["sku"].str.contains(lp.PATRON_PRODUCTO_PRUEBA, regex=True).any()
    assert not df.loc[df["es_compra_valida"], "precio_cero"].any()
    assert (df.groupby("increment_id")["customer_id"].nunique() == 1).all()
    assert df["created_at"].between("2016-07-01", "2018-08-31").all()
