"""Funciones de limpieza (ETL) del dataset de e-commerce de Pakistán.

Cada paso recibe un DataFrame y una bitácora (`log`), devuelve el DataFrame
transformado y registra en la bitácora cuántas filas/valores afectó y por qué.
Así el impacto de cada decisión queda cuantificado (lo pide la rúbrica).

Uso típico:
    from src.limpieza import pipeline_etl
    df, log = pipeline_etl("data/raw/Pakistan Largest Ecommerce Dataset.csv")
"""

from __future__ import annotations

import re

import pandas as pd

# --------------------------------------------------------------------------
# Constantes del negocio
# --------------------------------------------------------------------------

# Estados que cuentan como compra concretada (decisión del equipo).
# Se excluyen: canceled, order_refunded, refund, fraud y los pendientes
# (pending, processing, holded, payment_review, pending_paypal).
ESTADOS_VALIDOS = {"complete", "received", "closed", "paid", "cod", "exchange"}

# Columnas que se demuestran redundantes en el notebook antes de quitarlas.
COLUMNAS_REDUNDANTES = ["working_date", "year", "month", "m_y", "fy", "mv", "bi_status"]

# Columnas sin las cuales una transacción no se puede atribuir a nadie/nada.
COLUMNAS_OBLIGATORIAS = ["customer_id", "status", "sku"]

UMBRAL_QTY_ATIPICA = 100
CATEGORIA_DESCONOCIDA = "Desconocida"

# SKUs de prueba internos de la tienda (test-product, test bundle, Test Hazir,
# tcsconnect...). El patrón NO atrapa productos reales que contienen "test",
# como "SKMT_Blood Test", la pelota "Test Star" o la marca "Vous Deteste".
PATRON_PRODUCTO_PRUEBA = (r"(?i)(?:test[\s_-]*product|test[\s_-]*bundle|test[\s_-]*hazir"
                          r"|^test[_\s-]|tcsconnect|ahadtest|product_margin_test|^test$)")
# Clientes con al menos esta proporción de compras de prueba → probable cuenta interna.
UMBRAL_CUENTA_INTERNA = 0.30


# --------------------------------------------------------------------------
# Bitácora de impacto
# --------------------------------------------------------------------------

def registrar_paso(log: list, paso: str, filas_antes: int, filas_despues: int,
                   valores_afectados: int, motivo: str) -> None:
    """Agrega una entrada a la bitácora de impacto."""
    log.append({
        "paso": paso,
        "filas_antes": filas_antes,
        "filas_despues": filas_despues,
        "filas_eliminadas": filas_antes - filas_despues,
        "valores_afectados": valores_afectados,
        "motivo": motivo,
    })


def bitacora_a_df(log: list) -> pd.DataFrame:
    """Convierte la bitácora en una tabla para mostrar o exportar."""
    return pd.DataFrame(log)


def bitacora_a_markdown(log: list) -> str:
    """Tabla markdown de la bitácora (sin depender de `tabulate`)."""
    cols = ["paso", "filas_antes", "filas_despues", "filas_eliminadas",
            "valores_afectados", "motivo"]
    lineas = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for fila in log:
        celdas = [f"{fila[c]:,}".replace(",", ".") if isinstance(fila[c], int) else
                  str(fila[c]).replace("|", "/") for c in cols]
        lineas.append("| " + " | ".join(celdas) + " |")
    return "\n".join(lineas)


# --------------------------------------------------------------------------
# Pasos del ETL
# --------------------------------------------------------------------------

def cargar_crudo(ruta: str) -> pd.DataFrame:
    """Lee el CSV crudo tal como viene de Kaggle (sin transformar nada)."""
    return pd.read_csv(ruta, low_memory=False)


def eliminar_filas_y_columnas_vacias(df: pd.DataFrame, log: list) -> pd.DataFrame:
    """Quita filas 100 % vacías (relleno del export de Excel) y columnas sin datos."""
    antes = len(df)
    cols_vacias = [c for c in df.columns if df[c].isna().all()]
    df = df.dropna(how="all").drop(columns=cols_vacias)
    registrar_paso(log, "Filas vacías", antes, len(df), antes - len(df),
                   "Filas sin ningún dato: relleno del export a Excel.")
    registrar_paso(log, "Columnas vacías", len(df), len(df), len(cols_vacias),
                   f"Columnas 100 % vacías: {', '.join(cols_vacias)}.")
    return df.reset_index(drop=True)


def a_snake_case(nombre: str) -> str:
    """'Customer ID' -> 'customer_id', ' MV ' -> 'mv', 'M-Y' -> 'm_y'."""
    nombre = nombre.strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", nombre).strip("_")


def normalizar_nombres(df: pd.DataFrame, log: list) -> pd.DataFrame:
    """Pasa los nombres de columnas a snake_case (quita espacios como en ' MV ')."""
    df = df.rename(columns=a_snake_case)
    registrar_paso(log, "Nombres de columnas", len(df), len(df), df.shape[1],
                   "Nombres en snake_case para evitar errores por espacios.")
    return df


def normalizar_texto(df: pd.DataFrame, log: list) -> pd.DataFrame:
    """Quita espacios, convierte el marcador '\\N' (nulo de MySQL) en NaN
    y unifica `payment_method` en minúsculas.

    Nota: `read_csv` ya trata como NaN los textos '#N/A' (error de Excel en 11
    `Customer ID`), 'NA' y 'None' (7 `sales_commission_code`), que también
    significan "sin dato"."""
    cols_texto = df.select_dtypes(include=["object", "string"]).columns
    marcadores = 0
    for c in cols_texto:
        df[c] = df[c].str.strip()
        es_marcador = df[c].eq("\\N")
        marcadores += int(es_marcador.sum())
        df[c] = df[c].mask(es_marcador)
    df["payment_method"] = df["payment_method"].str.lower()
    registrar_paso(log, "Texto y marcador \\N", len(df), len(df), marcadores,
                   "'\\N' es el nulo de MySQL: se trata como faltante. Strip de espacios.")
    return df


def convertir_tipos(df: pd.DataFrame, log: list) -> pd.DataFrame:
    """Fechas a datetime e identificadores a enteros (admiten nulos)."""
    df["created_at"] = pd.to_datetime(df["created_at"], format="%m/%d/%Y")
    df["customer_since"] = pd.to_datetime(df["customer_since"], format="%Y-%m")
    for c in ["item_id", "customer_id"]:
        df[c] = df[c].astype("Int64")
    df["qty_ordered"] = df["qty_ordered"].astype("Int64")
    registrar_paso(log, "Tipos de datos", len(df), len(df), 5,
                   "created_at y customer_since a fecha; item_id, customer_id y qty_ordered a entero.")
    return df


def eliminar_redundantes(df: pd.DataFrame, log: list) -> pd.DataFrame:
    """Quita columnas derivables de otras (la prueba está en el notebook) y
    convierte `sales_commission_code` en una bandera."""
    df["uso_codigo_comision"] = df["sales_commission_code"].notna()
    cols = COLUMNAS_REDUNDANTES + ["sales_commission_code"]
    df = df.drop(columns=cols)
    registrar_paso(log, "Columnas redundantes", len(df), len(df), len(cols),
                   "working_date = created_at; year/month/m_y/fy salen de la fecha; "
                   "mv = price×qty; bi_status depende solo de status. "
                   "sales_commission_code (81 % faltante) → bandera uso_codigo_comision.")
    return df


def tratar_nulos(df: pd.DataFrame, log: list) -> pd.DataFrame:
    """Elimina filas sin cliente, estado o sku; imputa la categoría faltante."""
    antes = len(df)
    df = df.dropna(subset=COLUMNAS_OBLIGATORIAS)
    registrar_paso(log, "Nulos en columnas clave", antes, len(df), antes - len(df),
                   "Sin customer_id, status o sku la transacción no se puede atribuir.")

    # Categoría: primero la más frecuente del mismo sku; si no hay, 'Desconocida'.
    faltante = df["category_name_1"].isna()
    categoria_por_sku = (df.loc[~faltante].groupby("sku")["category_name_1"]
                         .agg(lambda s: s.mode().iat[0]))
    imputada = df.loc[faltante, "sku"].map(categoria_por_sku)
    recuperadas = int(imputada.notna().sum())
    df.loc[faltante, "category_name_1"] = imputada.fillna(CATEGORIA_DESCONOCIDA)
    registrar_paso(log, "Categoría por sku", len(df), len(df), recuperadas,
                   "Categoría faltante imputada con la categoría más frecuente del mismo sku.")
    registrar_paso(log, "Categoría desconocida", len(df), len(df),
                   int(faltante.sum()) - recuperadas,
                   f"Sin referencia en otro registro del sku → '{CATEGORIA_DESCONOCIDA}'.")
    return df.reset_index(drop=True)


def tratar_duplicados(df: pd.DataFrame, log: list) -> pd.DataFrame:
    """Elimina duplicados exactos y verifica que item_id sea único.

    Las líneas idénticas salvo `item_id` NO se eliminan: el grand_total del
    pedido las incluye, así que son el mismo producto agregado dos veces.
    """
    antes = len(df)
    df = df.drop_duplicates()
    df = df.drop_duplicates(subset="item_id")
    casi = int(df.duplicated(subset=[c for c in df.columns if c != "item_id"]).sum())
    registrar_paso(log, "Duplicados exactos", antes, len(df), antes - len(df),
                   "Filas idénticas o item_id repetido.")
    registrar_paso(log, "Líneas repetidas (se conservan)", len(df), len(df), casi,
                   "Idénticas salvo item_id, pero el grand_total del pedido las suma: "
                   "son compras legítimas.")
    return df.reset_index(drop=True)


def tratar_productos_prueba(df: pd.DataFrame, log: list) -> pd.DataFrame:
    """Elimina las transacciones de productos de prueba y marca las cuentas que
    las usaban mucho (probable personal de la tienda)."""
    es_prueba = df["sku"].str.contains(PATRON_PRODUCTO_PRUEBA, regex=True)

    # La proporción se calcula ANTES de borrar las filas de prueba.
    prop_prueba = es_prueba.groupby(df["customer_id"]).mean()
    internas = prop_prueba[prop_prueba >= UMBRAL_CUENTA_INTERNA].index
    df["cuenta_interna_probable"] = df["customer_id"].isin(internas)

    antes = len(df)
    skus_prueba = df.loc[es_prueba, "sku"].nunique()
    df = df.loc[~es_prueba]
    registrar_paso(log, "Productos de prueba", antes, len(df), antes - len(df),
                   f"{skus_prueba} SKUs de prueba internos (test-product, test bundle, "
                   "Test Hazir, tcsconnect...): no son ventas reales.")
    restantes = df.loc[df["cuenta_interna_probable"], "customer_id"].nunique()
    registrar_paso(log, "Cuenta interna probable (marcada)", len(df), len(df),
                   int(df["cuenta_interna_probable"].sum()),
                   f"Filas de {restantes} clientes con ≥{UMBRAL_CUENTA_INTERNA:.0%} de compras "
                   "de prueba: se conservan y el EDA decide.")
    return df.reset_index(drop=True)


def tratar_invalidos(df: pd.DataFrame, log: list) -> pd.DataFrame:
    """Corrige o marca valores imposibles sin borrar información."""
    desc_neg = df["discount_amount"] < 0
    df.loc[desc_neg, "discount_amount"] = 0.0
    registrar_paso(log, "Descuento negativo", len(df), len(df), int(desc_neg.sum()),
                   "Un descuento no puede ser negativo → 0.")

    # El descuento del crudo se reparte de forma irregular entre las líneas de un
    # pedido: a veces supera el valor bruto de la línea (o del pedido entero).
    bruto = df["price"] * df["qty_ordered"].astype(float)
    df["descuento_inconsistente"] = df["discount_amount"] > bruto
    registrar_paso(log, "Descuento > bruto (marcado)", len(df), len(df),
                   int(df["descuento_inconsistente"].sum()),
                   "El descuento supera price×qty: dato poco confiable a nivel línea. "
                   "monto_linea se recorta a 0.")

    df["grand_total_negativo"] = df["grand_total"] < 0
    registrar_paso(log, "grand_total negativo (marcado)", len(df), len(df),
                   int(df["grand_total_negativo"].sum()),
                   "Total de pedido < 0 (descuento mayor al precio): se marca, no se borra.")

    df["precio_cero"] = df["price"] == 0
    registrar_paso(log, "Precio cero (marcado)", len(df), len(df),
                   int(df["precio_cero"].sum()),
                   "Regalos o errores de carga: no cuentan como compra válida.")

    df["qty_atipica"] = (df["qty_ordered"] > UMBRAL_QTY_ATIPICA).astype(bool)
    registrar_paso(log, "Cantidad atípica (marcada)", len(df), len(df),
                   int(df["qty_atipica"].sum()),
                   f"qty_ordered > {UMBRAL_QTY_ATIPICA}: posibles compras mayoristas; decide el EDA.")
    return df


def crear_variables(df: pd.DataFrame, log: list) -> pd.DataFrame:
    """Variables básicas para el EDA y el modelado."""
    # grand_total es a nivel pedido, por eso el monto por ítem se calcula aparte.
    df["monto_bruto"] = df["price"] * df["qty_ordered"].astype(float)
    # Recorte a 0: con descuento_inconsistente la resta daría montos negativos.
    df["monto_linea"] = (df["monto_bruto"] - df["discount_amount"]).clip(lower=0)
    df["anio_mes"] = df["created_at"].dt.to_period("M").astype(str)
    registrar_paso(log, "Variables nuevas", len(df), len(df), 3,
                   "monto_bruto = price×qty; monto_linea = max(bruto − descuento, 0) "
                   "(grand_total es por pedido); anio_mes.")
    return df


def marcar_compra_valida(df: pd.DataFrame, log: list) -> pd.DataFrame:
    """Bandera de compra concretada: estado válido y precio mayor a cero."""
    df["es_compra_valida"] = df["status"].isin(ESTADOS_VALIDOS) & ~df["precio_cero"]
    registrar_paso(log, "Compra válida (bandera)", len(df), len(df),
                   int(df["es_compra_valida"].sum()),
                   f"status ∈ {sorted(ESTADOS_VALIDOS)} y price > 0.")
    return df


ORDEN_COLUMNAS = [
    "item_id", "increment_id", "customer_id", "customer_since", "created_at", "anio_mes",
    "status", "es_compra_valida", "sku", "category_name_1", "price", "qty_ordered",
    "discount_amount", "monto_bruto", "monto_linea", "grand_total", "payment_method",
    "uso_codigo_comision", "precio_cero", "descuento_inconsistente",
    "grand_total_negativo", "qty_atipica", "cuenta_interna_probable",
]


def pipeline_etl(ruta_cruda: str) -> tuple[pd.DataFrame, list]:
    """Ejecuta todos los pasos en orden y devuelve (df_limpio, bitácora)."""
    log: list = []
    df = cargar_crudo(ruta_cruda)
    registrar_paso(log, "Carga", len(df), len(df), 0, "CSV crudo de Kaggle.")
    for paso in (eliminar_filas_y_columnas_vacias, normalizar_nombres, normalizar_texto,
                 convertir_tipos, eliminar_redundantes, tratar_nulos, tratar_duplicados,
                 tratar_productos_prueba, tratar_invalidos, crear_variables,
                 marcar_compra_valida):
        df = paso(df, log)
    return df[ORDEN_COLUMNAS], log
