# 📦 Sistema de Recebimento e Geração de Macro – US400/AS400

Este projeto é uma aplicação web desenvolvida com **Flask**, voltada ao controle de **endereçamento logístico, validação de itens com base em cubagem, consulta ao sistema BPCS**, e **geração de macros** automatizadas para uso no terminal de recebimento de mercadorias. Além disso, o sistema realiza **impressão de etiquetas ZPL** diretamente em impressoras Zebra de rede.

---

## 🚀 Funcionalidades Principais

- 🔐 Login com autenticação baseada em credenciais do BPCS.
- 📦 Consulta de movimentações no BPCS via ODBC.
- 📏 Verificação e cadastro de dados de cubagem de itens.
- 📍 Alocação automática de endereços baseada em zona e altura.
- 🖨 Impressão de etiquetas ZPL em impressoras Zebra.
- 📄 Geração de arquivos .mac com macros para o sistema terminal.
- 👥 Gerenciamento de usuários com persistência via SQLite.



## 🧱 Estrutura do Projeto

.
- ├── app.py                   # Aplicação principal Flask
- ├── database.py              # Acesso ao SQLite e BPCS via ODBC
- ├── etiquetaszpl.py          # Impressão ZPL em impressoras Zebra
- ├── templates/
- │   └── index.html           # Interface principal do sistema
- ├── static/
- │   └── style.css            # Estilos personalizados
- ├── Itens.db                 # Banco com dados de cubagem
- ├── usuarios.db              # Banco com dados de usuários
- ├── .env                     # Variáveis de ambiente (configuração)
- └── README.md                # Documentação do projeto


## ⚙️ Pré-requisitos

- Python 3.10+
- Driver ODBC da IBM iSeries Access for Windows instalado
- Acesso ao sistema US400 / AS400
- Impressora Zebra conectada via rede
- Permissão de leitura/gravação no caminho de rede onde os arquivos .mac serão salvos
- Variáveis de ambiente .env configuradas (veja abaixo)

## 🔐 Variáveis de Ambiente (.env)

- SECRET_KEY=uma_chave_segura_aleatoria
- FLASK_ENV=development
- SQLITE_PATH=usuarios.db
- ITENS_DB_PATH=Itens.db
- MACRO_PATH=C:\caminho\para\salvar\macros


## ▶️ Como Rodar Localmente

### 1. Clone o repositório
git clone https://github.com/Msandrade2/Sistema_Recebimento_Macros-US400.git

cd recebimento-macros

### 2. Crie o ambiente virtual
python -m venv venv
source venv/bin/activate     # Linux/macOS
venv\Scripts\activate        # Windows

### 3. Instale as dependências
pip install -r requirements.txt



## 🖥️ Execução

### Ativar o ambiente virtual (se ainda não ativado)
.venv\Scripts\activate

### Rodar a aplicação
python app.py

A aplicação estará disponível em:
📍 http://localhost:8000

## 🖨️ Impressoras Compatíveis

O sistema está configurado para funcionar com as impressoras Zebra abaixo:
- BRTEMAN01
- BRTEMAN02
Você pode editar o arquivo etiquetaszpl.py para adicionar ou modificar as configurações de IP, margens, e layout da etiqueta.


## 💾 Banco de Dados

O sistema utiliza dois arquivos .db:

usuarios.db – Armazena usuários e credenciais de acesso ao BPCS.

Itens.db – Armazena dados de cubagem dos itens para cálculos logísticos.

Esses arquivos são criados automaticamente caso não existam, e devem estar acessíveis na raiz do projeto.


## 🔄 Fluxo de Uso

- 1-Acesse a página principal e faça login com um ID válido (armazenado via SQLite)
- 2-Insira os dados da movimentação: Item, Lote, Armazém, Quantidade, etc.
- 3-Clique em "Consultar" para validar os dados no AS400 via ODBC
- 4-Se os dados forem encontrados, será gerada uma macro para terminal 5250
- 5-Clique em "Gravar" para salvar o arquivo .mac no caminho configurado
- 6-Faça o download e execute no seu emulador US400



## 🔒 Segurança
 
- Todas as sessões são protegidas via cookie seguro (SESSION_COOKIE_SECURE)
- As sessões são protegidas com SECRET_KEY.
- As credenciais de BPCS são armazenadas localmente via SQLite.
- Sessões expiram após logout manual.
- Evite expor esta aplicação fora de rede interna sem autenticação forte
- Acesso às rotas principais é controlado via @login_required.

## 📁 Dependências

Veja em requirements.txt:

- Flask
- flask-cors
- python-dotenv
- waitress
- pyodbc
- pandas

## 🛠️ Tecnologias

- Python 3.10+
- Flask
- Flask-CORS
- Waitress (servidor de produção)
- ODBC / pyodbc (para conexão com AS400/BPCS)
- SQLite3
- HTML + CSS (básico)
- Pandas
- ZPL (Zebra Programming Language)

## 🤝 Contribuições
Contribuições são bem-vindas! Para sugestões, melhorias ou correções, abra um issue ou envie um pull request.

## 🧾 Licença
Este projeto é privado/proprietário. Consulte o responsável pelo projeto para mais informações sobre uso e redistribuição.

## 📞 Suporte
Em caso de problemas, entre em contato com o desenvolvedor Msandrade.
Email: m.sergio157@gmail.com