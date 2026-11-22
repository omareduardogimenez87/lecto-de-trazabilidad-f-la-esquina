"""Procesar todas las fotos de una carpeta, sin abrir la app.

Uso (desde la carpeta del proyecto):
    python procesar_carpeta.py CARPETA_CON_FOTOS --usuario Omar

Muestra lo que leyó de cada foto. Con --guardar, además lo agrega al registro.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from lector import registro
from lector.imagen import abrir, analizar, fecha_de_la_foto

EXTENSIONES = {".jpg", ".jpeg", ".png", ".webp"}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("carpeta", type=Path)
    p.add_argument("--usuario", required=True, help="Nombre tal como figura en usuarios.json")
    p.add_argument("--guardar", action="store_true", help="Agregar las lecturas al registro")
    args = p.parse_args()

    config = json.loads((Path(__file__).parent / "usuarios.json").read_text(encoding="utf-8"))
    usuarios = {u["nombre"].lower(): u for u in config["usuarios"]}
    usuario = usuarios.get(args.usuario.lower())
    if not usuario:
        raise SystemExit(f"Usuario desconocido. Opciones: {', '.join(u['nombre'] for u in config['usuarios'])}")

    filas = []
    for foto in sorted(f for f in args.carpeta.iterdir() if f.suffix.lower() in EXTENSIONES):
        img = abrir(foto)
        fecha, origen = fecha_de_la_foto(img, foto.name)
        if fecha is None:
            fecha, origen = datetime.fromtimestamp(foto.stat().st_mtime), "fecha del archivo"
        for lec in analizar(img):
            fila = lec.como_dict()
            fila.update(
                fecha_foto=fecha.strftime(registro.FORMATO_FECHA), origen_fecha_foto=origen,
                usuario=usuario["nombre"], rol=usuario["rol"], sucursal=config.get("sucursal", ""),
                archivo_foto=foto.name,
            )
            filas.append(fila)
            marca = "OK " if lec.fuente == "DataMatrix" and lec.gtin_valido else "REV"
            print(f"[{marca}] {foto.name}: GTIN={lec.gtin or '-'} serie={lec.serie or '-'} "
                  f"lote={lec.lote or '-'} vto={lec.vencimiento or '-'} ({lec.fuente})")

    if args.guardar:
        nuevas = [f for f in filas if not registro.ya_registrado(f["gtin"], f["serie"])]
        registro.guardar(nuevas)
        print(f"\nGuardadas {len(nuevas)} fila(s) en {registro.ARCHIVO} ({len(filas) - len(nuevas)} duplicadas)")


if __name__ == "__main__":
    main()
