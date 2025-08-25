import os
import logging
import time
import sqlite3
import pyodbc
import math
import pandas as pd
from flask import session


DB_PATH = os.environ.get('SQLITE_PATH', 'usuarios.db')


logging.basicConfig(level=logging.INFO)

# ---------- Conexão SQLite ----------
def connect_sqlite():
    try:
        return sqlite3.connect(DB_PATH)
    except sqlite3.Error as e:
        logging.error(f"[ERRO SQLITE] Conexão falhou: {e}")
        return None

def get_usuario_by_id(user_id):
    try:
        conn = connect_sqlite()
        if not conn:
            return None
        conn.row_factory = sqlite3.Row
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM usuarios WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logging.error(f"[ERRO SQLITE] get_usuario_by_id: {e}")
        return None

def create_usuario(user_id, upin, senha, nome):
    try:
        with connect_sqlite() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO usuarios (id, upin, senha, nome) VALUES (?, ?, ?, ?)",
                (user_id, upin, senha, nome)
            )
            conn.commit()
    except Exception as e:
        logging.error(f"[ERRO SQLITE] create_usuario: {e}")

def update_usuario_senha(user_id, nova_senha):
    try:
        with connect_sqlite() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE usuarios SET senha = ? WHERE id = ?", (nova_senha, user_id)
            )
            conn.commit()
    except Exception as e:
        logging.error(f"[ERRO SQLITE] update_usuario_senha: {e}")

# ---------- Conexão ODBC / AS400 ----------
def connect_odbc(uid, pwd):
    try:
        return pyodbc.connect(
            f'DRIVER={{iSeries Access ODBC Driver}};'
            f'SYSTEM=US400BR;'
            f'UID={uid};'
            f'PWD={pwd}'
        )
    except Exception as e:
        logging.error(f"[ERRO ODBC] Conexão ODBC falhou: {e}")
        raise

def fetch_data(item, lote, mov, quantidade, armazem):
    max_retries = 3
    usuario_id = session.get('usuario_id')

    if not usuario_id:
        logging.warning("[AUTH] Usuário não autenticado.")
        return None

    usuario = get_usuario_by_id(usuario_id)
    if not usuario:
        logging.warning(f"[AUTH] Usuário ID '{usuario_id}' não encontrado.")
        return None

    uid = usuario.get("upin")
    pwd = usuario.get("senha")

    for attempt in range(max_retries):
        try:
            with connect_odbc(uid, pwd) as con:
                query = """
                    SELECT W1TWHS Armazem, W1PROD Item, W1LOT Lote, W1PQTY Quantidade, W1MOVN Mov, SUBSTR(T2.TCLAS, 1, 1) AS Classe
                    FROM V60ARQ3M.IW1 T1
                    LEFT JOIN V60BPCSF.ITH T2 ON T1.W1MOVN = T2.TREF AND T1.W1DATE = T2.TTDTE
                    WHERE W1PROD = ? AND W1LOT = ? AND W1MOVN = ? AND W1PQTY = ? AND W1TWHS = ?
                    GROUP BY W1TWHS, W1PROD, W1LOT, W1PQTY, W1MOVN, SUBSTR(T2.TCLAS, 1, 1)
                """
                params = (
                    str(item).strip(),
                    str(lote).strip(),
                    str(mov).strip(),
                    f"{float(quantidade):.3f}",
                    str(armazem).strip()
                )
                df = pd.read_sql(query, con, params=params)
                return df if not df.empty else None

        except Exception as e:
            error_msg = str(e)
            logging.error(f"[ERRO DB] Tentativa {attempt+1} de {max_retries}: {error_msg}")

            if "CWBSY0002" in error_msg:
                raise ValueError("Senha do BPCS incorreta.")
            if "CWBSY0011" in error_msg:
                raise ValueError("Usuário BPCS bloqueado ou desativado.")

            time.sleep(2)  # Pequeno delay entre as tentativas

    return None


def fetch_data_locação(zona=None, armazem=None, excluir_locs=None, volume=None, item=None):
    try:
        if not zona or not armazem or volume is None or not item:
            logging.warning("Zona, armazém, item ou volume não informados em fetch_data_locação.")
            return None

        usuario_id = session.get('usuario_id')
        usuario = get_usuario_by_id(usuario_id)
        if not usuario:
            return None

        uid = usuario.get("upin")
        pwd = usuario.get("senha")

        excluir_locs = excluir_locs or []

        # Buscar dados do item
        info = get_item_cubagem(item)
        if not info:
            logging.warning("Item não encontrado na tabela de cubagem.")
            return None

        try:
            volume = float(volume)
            cx_lastro = float(info['Cx_Lastro'])
            altura_item = float(info['Altura'])
        except (ValueError, TypeError):
            logging.warning("Erro ao converter volume ou dados de cubagem.")
            return None

        ALTURA_PALLET = 0.15
        altura_necessaria = (math.ceil(volume / cx_lastro) * altura_item) + ALTURA_PALLET
        altura_necessaria = round(altura_necessaria, 2)
        logging.info(f"[LOCACAO] Buscando locação para zona '{zona.upper()}' com altura necessária mínima de {altura_necessaria:.2f}m")

        with connect_odbc(uid, pwd) as con:
            query = """
                SELECT ILE.LELOC, ILE.LEHGHT
                FROM V60BPCSF.ILE ILE
                WHERE 
                    ILE.LEWHS = ?
                    AND ILE.LEID = 'LE' 
                    AND ILE.LELOCT = '0'
                    AND ILE.LELCDE = 'E'
                    AND CAST(ILE.LEHGHT AS DECIMAL(5,2)) >= ?
                    AND NOT EXISTS (
                        SELECT 1 
                        FROM V60ARQ3M.IULM IULM
                        WHERE IULM.ULWHSE = ILE.LEWHS AND IULM.ULLOCA = ILE.LELOC
                    )
                    AND UPPER(ILE.LEZONE) = ?
            """

            if excluir_locs:
                placeholders = ','.join(['?'] * len(excluir_locs))
                query += f" AND ILE.LELOC NOT IN ({placeholders})"

            query += """
                ORDER BY 
                CASE 
                    WHEN UPPER(ILE.LEZONE) = 'RUA' THEN 2
                    ELSE 1
                END,
                CAST(ILE.LEHGHT AS DECIMAL(5,2)) ASC,
                ILE.LELOC
                FETCH FIRST 1 ROWS ONLY
                """

            params = [armazem, altura_necessaria, zona.upper()] + excluir_locs

            cursor = con.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            if row:
                endereco, height = row[0], row[1]
                logging.info(f"[LOCACAO] Endereço escolhido: {endereco} com LEHGHT={height}")
                return endereco
            return None

    except Exception as e:
        logging.error(f"[ERRO] fetch_data_locação: {e}")
        return None

ITENS_DB_PATH = os.environ.get('ITENS_DB_PATH', 'Itens.db')

def connect_itens_db():
    try:
        return sqlite3.connect(ITENS_DB_PATH)
    except sqlite3.Error as e:
        logging.error(f"[ERRO SQLITE] Conexão com Itens.db falhou: {e}")
        return None

def get_item_cubagem(item):
    try:
        conn = connect_itens_db()
        conn.row_factory = sqlite3.Row
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM Itens_cubagem WHERE Item = ?", (item,))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logging.error(f"[ERRO] get_item_cubagem: {e}")
        return None

def salvar_ou_atualizar_item_cubagem(dados):
    try:
        cubagem_formatada = (
            round(float(dados['Cubagem']), 4)
            if dados.get('Cubagem') not in (None, '')
            else None
        )

        with connect_itens_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO Itens_cubagem (Item, Comprimento, Largura, Altura, Cubagem, Cx_Lastro)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(Item) DO UPDATE SET
                    Comprimento=excluded.Comprimento,
                    Largura=excluded.Largura,
                    Altura=excluded.Altura,
                    Cubagem=excluded.Cubagem,
                    Cx_Lastro=excluded.Cx_Lastro
            """, (
                dados['Item'],
                dados['Comprimento'],
                dados['Largura'],
                dados['Altura'],
                cubagem_formatada,
                dados['Cx_Lastro']
            ))
            conn.commit()
            return True
    except Exception as e:
        logging.error(f"[ERRO] salvar_ou_atualizar_item_cubagem: {e}")
        return False