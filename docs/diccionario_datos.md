# Diccionario de datos

El dataset de Kaggle no trae diccionario. Las descripciones se infirieron del análisis de `notebooks/01_ETL.ipynb`.

**Archivo:** `data/processed/transacciones_limpias.parquet` · 582.701 filas × 23 columnas · una fila = una línea (ítem) de un pedido.
**Período:** 2016-07-01 a 2018-08-28.

## Columnas del dataset limpio

| Columna | Tipo | Origen | Descripción |
|---|---|---|---|
| `item_id` | Int64 | `item_id` | Identificador único de la línea del pedido. |
| `increment_id` | str | `increment_id` | Número de pedido. Un pedido puede tener varias líneas. 9 líneas terminan en `-1` (pedido re-emitido; el pedido base también existe). |
| `customer_id` | Int64 | `Customer ID` | Identificador del cliente. |
| `customer_since` | datetime | `Customer Since` | Mes de alta del cliente (día 1 del mes). |
| `created_at` | datetime | `created_at` | Fecha de la transacción (sin hora). |
| `anio_mes` | str | derivada | Año-mes de `created_at` (`"2017-11"`). |
| `status` | str | `status` | Estado de la transacción (complete, canceled, received, order_refunded, refund, cod, paid, closed, pending, …). |
| `es_compra_valida` | bool | derivada | `True` si `status` ∈ {complete, received, closed, paid, cod, exchange} y `price` > 0. **Filtro para el modelado.** |
| `sku` | str | `sku` | Código del producto (a veces incluye el nombre). |
| `category_name_1` | str | `category_name_1` | Categoría del producto (15 categorías + `"Desconocida"`). |
| `price` | float | `price` | Precio unitario en PKR. |
| `qty_ordered` | Int64 | `qty_ordered` | Unidades pedidas. |
| `discount_amount` | float | `discount_amount` | Descuento asignado a la línea (PKR). El descuento del pedido se reparte de forma irregular entre las líneas. |
| `monto_bruto` | float | derivada | `price × qty_ordered`: valor bruto de la línea. Confiable (coincide con el `MV` original). **Recomendado para el volumen de compra.** |
| `monto_linea` | float | derivada | `max(monto_bruto − discount_amount, 0)`: monto neto, recortado a 0. Poco confiable donde `descuento_inconsistente` es True. |
| `grand_total` | float | `grand_total` | **Total del pedido** (se repite en todas sus líneas). No se suma por ítem. |
| `payment_method` | str | `payment_method` | Medio de pago (cod = contra entrega, easypay, jazzwallet, …), en minúsculas. |
| `uso_codigo_comision` | bool | `sales_commission_code` | La línea tiene un código de comisión o de vendedor. |
| `precio_cero` | bool | derivada | `price == 0` (regalo o error de carga). |
| `descuento_inconsistente` | bool | derivada | `discount_amount > price × qty_ordered` (9.711 filas). |
| `grand_total_negativo` | bool | derivada | `grand_total < 0`. |
| `qty_atipica` | bool | derivada | `qty_ordered > 100` (posible compra mayorista). |
| `cuenta_interna_probable` | bool | derivada | El cliente tenía ≥ 30 % de compras de productos de prueba (probable personal de la tienda; 53 clientes). |

## Columnas eliminadas del crudo

| Columna | Motivo |
|---|---|
| `Unnamed: 21`–`Unnamed: 25` | 100 % vacías. |
| `Working Date` | Idéntica a `created_at` en el 100 % de las filas. |
| `Year`, `Month`, `M-Y`, `FY` | Derivables de `created_at` (FY = año fiscal julio–junio). |
| ` MV ` | Valor bruto `price × qty` guardado como texto (coincide en el 99,6 %; el resto es price = 0). |
| `BI Status` | Función de `status`: Gross = cancelada o pendiente, Net = completa o cerrada, Valid = recibida, pagada o reembolsada. |
| `sales_commission_code` | 81 % faltante; se reemplaza por `uso_codigo_comision`. |
