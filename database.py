import configparser
import math
from pathlib import Path
import pyodbc

_config = configparser.ConfigParser()
_config.read(Path(__file__).parent / "config.ini")

BASE_QUERY = """
select
  o."Nr OS" as 'Orden de Reparacion',
    LTRIM(RTRIM(a."Chassi")) as 'Numero de Chasis',
    v."Nm Modelo" as 'Modelo',
    v."Versao" as 'Version',
    a."Quilometragem" as 'Kilometraje',
    o."Dt Fechamento" as 'Fecha Ultima Visita',
    a."Cliente Veiculo" as 'ND',
    e."Razao Social" as 'Nombre del Cliente',
    LTRIM(
        COALESCE(CAST(e."Nr DDD1" AS VARCHAR(20)), '') +
        COALESCE(CAST(e."Tel1" AS VARCHAR(20)), '')
    ) AS "Telefono",
    e."email" as 'Correo Flujo Informacion',
    v."Dt Venda",
    ap."Comentario" as 'Operacion'
From "OS" as o
inner join "Atendimento" as a on o."Nr Atendimento"=a."Nr Atendimento"
inner join "Veiculos" as v on a."Chassi"=v."Chassi"
inner join "Entidades" as e on a."Cliente Veiculo"=e."Cod Entidade"
left join "Atendimento Pacotes" as ap on o."Nr Atendimento"=ap."Nr Atendimento"
Where o.Situacao ='R'
"""

BASE_COUNT_QUERY = """
SELECT COUNT(*)
From "OS" as o
inner join "Atendimento" as a on o."Nr Atendimento"=a."Nr Atendimento"
inner join "Veiculos" as v on a."Chassi"=v."Chassi"
inner join "Entidades" as e on a."Cliente Veiculo"=e."Cod Entidade"
left join "Atendimento Pacotes" as ap on o."Nr Atendimento"=ap."Nr Atendimento"
Where o.Situacao ='R'
"""

BASE_TOP_QUERY = """
select TOP {fetch_count} o."Nr OS" as 'Orden de Reparacion',
  LTRIM(RTRIM(a."Chassi")) as 'Numero de Chasis',
  v."Nm Modelo" as 'Modelo',
  v."Versao" as 'Version',
  a."Quilometragem" as 'Kilometraje',
  o."Dt Fechamento" as 'Fecha Ultima Visita',
  a."Cliente Veiculo" as 'ND',
  e."Razao Social" as 'Nombre del Cliente',
  LTRIM(
      COALESCE(CAST(e."Nr DDD1" AS VARCHAR(20)), '') +
      COALESCE(CAST(e."Tel1" AS VARCHAR(20)), '')
  ) AS "Telefono",
  e."email" as 'Correo Flujo Informacion',
  v."Dt Venda",
  ap."Comentario" as 'Operacion'
From "OS" as o
inner join "Atendimento" as a on o."Nr Atendimento"=a."Nr Atendimento"
inner join "Veiculos" as v on a."Chassi"=v."Chassi"
inner join "Entidades" as e on a."Cliente Veiculo"=e."Cod Entidade"
left join "Atendimento Pacotes" as ap on o."Nr Atendimento"=ap."Nr Atendimento"
Where o.Situacao ='R'
"""


def _build_queries(fecha_desde: str | None, fecha_hasta: str | None) -> tuple[str, str]:
    filters = ""
    if fecha_desde:
        filters += f" AND o.\"Dt Fechamento\" >= '{fecha_desde}'"
    if fecha_hasta:
        filters += f" AND o.\"Dt Fechamento\" <= '{fecha_hasta}'"
    count_query = BASE_COUNT_QUERY.rstrip() + filters + "\n"
    top_query = BASE_TOP_QUERY.rstrip() + filters + "\n"
    return count_query, top_query


def get_ordenes(page: int, page_size: int, fecha_desde: str | None = None, fecha_hasta: str | None = None) -> dict:
    dsn = _config.get("database", "dsn")
    conn = pyodbc.connect(f"DSN={dsn}")
    cursor = None
    try:
        cursor = conn.cursor()

        count_query, top_query = _build_queries(fecha_desde, fecha_hasta)

        cursor.execute(count_query)
        total = cursor.fetchone()[0]

        offset = (page - 1) * page_size
        # Pervasive no soporta SKIP/OFFSET — usamos fetchmany para avanzar el cursor
        # sin cargar todas las filas en memoria
        cursor.execute(top_query.format(fetch_count=total))
        columns = [col[0] for col in cursor.description]
        if offset > 0:
            cursor.fetchmany(offset)  # avanza el cursor, descarta filas anteriores
        rows = [dict(zip(columns, row)) for row in cursor.fetchmany(page_size)]
    finally:
        if cursor:
            cursor.close()
        conn.close()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if page_size else 0,
        "data": rows,
    }
