import os
import secrets
import logging
from functools import wraps
from flask import Flask, render_template, request, send_file, session, redirect, url_for, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from database import fetch_data, get_usuario_by_id, create_usuario, update_usuario_senha, fetch_data_locação, get_item_cubagem, salvar_ou_atualizar_item_cubagem
from etiquetaszpl import imprimir_etiqueta
from tabulate import tabulate
from waitress import serve



load_dotenv()

# Configurações iniciais
app = Flask(__name__)
CORS(app)

# Segurança da sessão
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=os.environ.get('FLASK_ENV') == 'production', 
    SESSION_PERMANENT=True
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(level=logging.INFO)




# Decorador de login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    success = None

    if request.method == 'POST' and 'usuario_id' not in session:
        error = "Sessão expirada. Faça login novamente."
        macro_count = len(session.get('macro_buffer', []))
        return render_template('index.html', error=error, macro_count=macro_count)

    if 'macro_buffer' not in session:
        session['macro_buffer'] = []

    if request.method == 'POST':
        action = request.form.get('action')
        item = request.form['item']
        lote = request.form['lote']
        Mov = request.form['Mov'].strip().upper()
        Armazem = request.form['Armazem']
        Volume = request.form['Volume']
        QUD = request.form['QUD']
        

        if Mov.startswith('W'):
            Mov = Mov[1:]
        Mov = Mov[-6:]

        
        action = request.form.get("action")
        if action == "consultar":
            # Validação de cubagem
            info_cubagem = get_item_cubagem(item)
            campos_obrigatorios = ["Comprimento", "Largura", "Altura", "Cubagem", "Cx_Lastro"]

            if not info_cubagem or any(info_cubagem.get(c) in (None, '', 0) for c in campos_obrigatorios):
                error = "O item não possui todas as informações de cubagem preenchidas. Complete antes de continuar."
                macro_count = len(session.get('macro_buffer', []))
                return render_template('index.html', error=error, macro_count=macro_count)
            try:
                Quantidade = float(QUD) * float(Volume)
            except ValueError:
                error = "Erro ao calcular a quantidade. Verifique os valores de QUD e Volume."
                macro_count = len(session.get('macro_buffer', []))
                return render_template('index.html', error=error, macro_count=macro_count)

            try:
                data = fetch_data(item, lote, Mov, Quantidade, Armazem )

                if data is not None:
                    print("[DEBUG] Resultado da consulta ao BPCS:")
                    print(tabulate(data, headers='keys', tablefmt='fancy_grid'))
                else:
                    print("[DEBUG] Nenhum dado retornado pelo fetch_data.")

                if data is not None:
                    if 'locacoes_usadas' not in session:
                        session['locacoes_usadas'] = []

                    locacao_resultado, zona_utilizada = buscar_locacao_com_fallback(
                    armazem=Armazem,
                    locacoes_usadas=session['locacoes_usadas'],
                    item=item,
                    volume=Volume
                )

                    if locacao_resultado and zona_utilizada:
                        session['locacoes_usadas'].append(locacao_resultado)

                        # Imprimir etiqueta com base na zona usada

                        upin = session.get("upin", "")
                        impressora = request.form.get("Impressora")
                        logging.info(f"[DEBUG] Impressora selecionada: >>{impressora}<<")

                        try:
                            imprimir_etiqueta([locacao_resultado], zona=zona_utilizada, movimentacao=Mov, upin=upin, impressora=impressora)
                        except ValueError as e:
                            error = str(e)
                        except ConnectionError as ce:
                            error = str(ce)
                            macro_count = len(session.get('macro_buffer', []))
                            return render_template('index.html', error=error, macro_count=macro_count)
                        logging.debug(f"[FORM DATA] {request.form}")
                        # Monta a macro corretamente e adiciona ao buffer
                        data.columns = [col.strip().lower() for col in data.columns]

                        
                        # Acesso com nome normalizado
                        classe = str(data.iloc[0]["classe"]).strip()
                        if classe in ("1", "7"):
                            tipo_item_deducido = "STD"
                        elif classe == "2":
                            tipo_item_deducido = "NSTD"
                        else:
                            tipo_item_deducido = "STD"  # valor padrão seguro

                        macro = (
                            f"{Armazem}[tab]W{Mov}[tab][enter]{locacao_resultado}[enter][pf6]"
                            if tipo_item_deducido == "STD"
                            else f"{Armazem}[tab]W{Mov}[tab][enter]{locacao_resultado}{Volume}[enter][pf6]"
                        )
                        macro_buffer = session.get('macro_buffer', [])
                        macro_buffer.append(macro)
                        session['macro_buffer'] = macro_buffer

                        success = "Consulta adicionada com sucesso."
                    else:
                        error = "Nenhuma locação disponível."
                else:
                    error = "Dados informados não coincidem com o BPCS. Verifique e tente novamente."
                

            except ValueError as ve:
                error = str(ve)
            except ValueError as ve:
                error = str(ve)
            except ConnectionError as ce:
                error = str(ce)  
            except Exception as e:
                logging.error(f"Erro inesperado durante consulta: {e}")
                error = "Erro inesperado durante a consulta ao sistema BPCS."
                 

        elif action == "gravar":
            macro_buffer = session.get('macro_buffer', [])
            if not macro_buffer:
                error = "Nenhuma macro em buffer para gravar."
            else:
                full_macro = (
                    '<HAScript name="Macro">'
                    '<screen name="MainScreen" entryscreen="true">'
                    '<description></description>'
                    '<actions><input value="' + "".join(macro_buffer) + '"/></actions>'
                    '<nextscreens timeout="0" ><nextscreen name="EndScreen" /></nextscreens>'
                    '</screen>'
                    '<screen name="EndScreen" exitscreen="true">'
                    '<description></description><actions></actions>'
                    '<nextscreens timeout="0" ></nextscreens>'
                    '</screen>'
                    '</HAScript>'
                )

                try:
                    network_path = os.environ.get(
                        'MACRO_PATH',
                        r"C:\Users\a9ww9zz\Desktop\Recebimento 2.0\output"
                    )
                    os.makedirs(network_path, exist_ok=True)
                    filename = "macro_final.mac"
                    full_path = os.path.join(network_path, filename)

                    with open(full_path, 'w') as f:
                        f.write(full_macro)

                    session['file_path'] = full_path
                    session['macro_buffer'] = []
                    session['locacoes_usadas'] = []

                    return redirect(url_for('index', download=filename))
                except Exception as e:
                    error = f"Erro ao salvar a macro: {str(e)}"
                    logging.error(error)

    macro_count = len(session.get('macro_buffer', []))
    return render_template('index.html', error=error, success=success, macro_count=macro_count)

@app.route('/static_download/<filename>')
def static_download(filename):
    path = os.path.join(BASE_DIR, 'output', filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return redirect(url_for('index'))

@app.route('/verificar_usuario', methods=['POST'])
def verificar_usuario():
    user_id = request.json.get('id')
    logging.info(f"Verificando usuário com ID: {user_id}")
    usuario = get_usuario_by_id(user_id)
    return jsonify(usuario if usuario else {})

@app.route('/salvar_usuario', methods=['POST'])
def salvar_usuario():
    data = request.json
    user_id = data['id']
    upin = data['upin']
    senha = data['senha']
    nome = data['nome']

    usuario_existente = get_usuario_by_id(user_id)

    if usuario_existente:
        update_usuario_senha(user_id, senha)
        return jsonify({"status": "atualizado"})
    else:
        create_usuario(user_id, upin, senha, nome)
        return jsonify({"status": "criado"})

@app.route('/logout', methods=['POST'])
def logout():
    try:
        session.clear()
        return jsonify({'success': True}), 200
    except Exception as e:
        logging.error(f"Erro durante logout: {e}")
        return jsonify({'success': False, 'message': 'Erro ao encerrar a sessão.'}), 500

@app.route('/verificar_status_login')
def verificar_status_login():
    return jsonify({'logged_in': ('usuario_id' in session)})

@app.route('/login', methods=['POST'])
def login():
    user_id = request.json.get('id')
    usuario = get_usuario_by_id(user_id)

    if usuario:
        session['usuario_id'] = usuario['id']
        session['upin'] = usuario['upin']
        session['senha'] = usuario['senha']
        return jsonify({'success': True})
    else:
        return jsonify({'success': False}), 401

@app.route("/fetch_locacao", methods=["POST"])
def fetch_locacao():
    data = request.get_json()
    zona = data.get("tipo")
    armazem = data.get("armazem")

    if not zona or not armazem:
        return jsonify({"success": False, "mensagem": "Zona ou armazém não informado."}), 400

    endereco = fetch_data_locação(zona, armazem)
    if endereco:
        return jsonify({"success": True, "endereco": endereco})
    else:
        return jsonify({"success": False, "mensagem": "Nenhum endereço disponível para essa combinação."})


def zonas_por_altura(altura_necessaria):
    """
    Retorna a lista de zonas prioritárias baseadas na altura necessária.
    """
    if altura_necessaria <= 1.0:
        return ["PEQ", "MED", "RUA"]
    elif altura_necessaria <= 1.35:
        return ["MED", "GRA", "RUA"]
    elif altura_necessaria <= 2:
        return ["GRA", "RUA"]
    else:
        return ["RUA"]

def buscar_locacao_com_fallback(armazem, locacoes_usadas, item, volume):
    info = get_item_cubagem(item)
    if not info:
        logging.warning("Item não encontrado na cubagem.")
        return None

    try:
        volume = float(volume)
        cx_lastro = float(info['Cx_Lastro'])
        altura_item = float(info['Altura'])

        ALTURA_PALLET = 0.15
        altura_necessaria = ((volume / cx_lastro) * altura_item) + ALTURA_PALLET
        altura_necessaria = round(altura_necessaria, 2)
    except Exception as e:
        logging.warning(f"[ERRO ALTURA] Erro ao calcular altura necessária: {e}")
        return None

    zonas_tentativas = zonas_por_altura(altura_necessaria)

    logging.info(f"[FALLBACK] Altura necessária: {altura_necessaria} → zonas tentativas: {zonas_tentativas}")

    for zona in zonas_tentativas:
        endereco = fetch_data_locação(
            zona=zona,
            armazem=armazem,
            excluir_locs=locacoes_usadas,
            volume=volume,
            item=item
        )
        if endereco:
            return endereco, zona

    logging.warning("[FALLBACK] Nenhuma locação encontrada em nenhuma zona.")
    return None, None

@app.route('/verificar_item_cubagem', methods=['POST'])
def verificar_item_cubagem():
    item = request.json.get('item')
    info = get_item_cubagem(item)

    campos_esperados = ["Comprimento", "Largura", "Altura", "Cubagem", "Cx_Lastro"]

    # Se item não existir, cria com campos nulos
    if not info:
        novo_item = {campo: None for campo in campos_esperados}
        novo_item["Item"] = item
        salvar_ou_atualizar_item_cubagem(novo_item)
        return jsonify({"necessitaPreenchimento": True, "dados": novo_item})

    # Se algum campo estiver vazio ou nulo, precisa preenchimento
    if any(info.get(campo) in (None, '', 0) for campo in campos_esperados):
        return jsonify({"necessitaPreenchimento": True, "dados": info})

    return jsonify({"necessitaPreenchimento": False, "dados": info})

@app.route('/salvar_item_cubagem', methods=['POST'])
def salvar_item_cubagem():
    dados = request.json
    sucesso = salvar_ou_atualizar_item_cubagem(dados)
    if sucesso:
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Erro ao salvar no banco de dados."})

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500 

@app.errorhandler(Exception)
def handle_exception(e):
    logging.error(f"Erro inesperado: {e}")
    return render_template("500.html"), 500  



# Rodar com Waitress para produção (use Gunicorn no Linux)
if __name__ == '__main__':
    logging.info("Servidor iniciado em modo desenvolvimento.")
    app.run(host='0.0.0.0', port=5000)


