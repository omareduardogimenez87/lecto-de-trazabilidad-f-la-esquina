# Lector de medicamentos con trazabilidad

App para la farmacia que lee los códigos de trazabilidad de los medicamentos a partir de una foto y los guarda en un archivo, con la fecha de la foto y los datos de quien la envió.

## Qué hace (dos funciones)

### 1. Leer los códigos desde una foto
El usuario saca o sube una foto del envase. La app detecta el código DataMatrix (el cuadradito impreso) y, si no puede, lee el texto impreso al lado. De cada envase obtiene:

| Dato | En el envase | Ejemplo |
|---|---|---|
| GTIN (código del producto) | `(01)` | 07796285298739 |
| Número de serie | `(21)` | 6717047054 |
| Lote | `LOT:` o `L` | 4975D |
| Vencimiento | `VEN:` o `V` | 30/06/2028 |

### 2. Transcribir y guardar el registro
Cada lectura se agrega como una fila en un archivo (CSV o Excel) con:

- Los datos del medicamento (GTIN, serie, lote, vencimiento).
- La **fecha y hora de la foto** (tomada de los datos internos de la imagen; si no los tiene, la fecha de envío).
- Los **datos del usuario** que la envió (nombre y sucursal).
- El nombre del archivo de la foto, para poder revisarla después.

## Estado
Proyecto recién iniciado. Próximos pasos:
1. Prototipo que lea las fotos de ejemplo y genere el CSV.
2. Definir cómo envía las fotos el usuario (web, celular, etc.).
3. Probar con fotos reales del mostrador.

## Privacidad
Las fotos y registros pueden tener datos sensibles. Este repositorio es **privado** y no debe subirse ninguna foto con datos de pacientes.

## Cierre del proyecto
Al terminar la app se agrega un `RESUMEN.md` con lo que se hizo, las decisiones tomadas y lo aprendido, para usarlo como contexto en la próxima app.
