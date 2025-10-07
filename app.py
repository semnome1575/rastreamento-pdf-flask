import os
import io
import zipfile
import pandas as pd
from flask import Flask, render_template, request, send_file, redirect, url_for
from werkzeug.utils import secure_filename
# Importação CORRIGIDA: Importamos o módulo inteiro (gerar_pdf_qr)
import gerar_pdf_qr # Apenas o nome do arquivo, sem o .py

app = Flask(__name__)
# Configurações de upload do Flask
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limite de 16MB
# Lista de extensões permitidas
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}

# Obter a URL base do ambiente (necessário para o QR Code funcionar no Render)
# Se estiver rodando localmente, ele usará 'http://127.0.0.1:5000'
BASE_URL = os.environ.get('BASE_URL', 'http://127.0.0.1:5000')

# 1. ATUALIZAÇÃO CRÍTICA: Passa a URL base para o módulo de geração de PDF
# O módulo inteiro 'gerar_pdf_qr' foi importado, permitindo a modificação de sua variável global.
gerar_pdf_qr.BASE_URL_RASTREAMENTO = BASE_URL

def allowed_file(filename):
    """Verifica se a extensão do arquivo é permitida."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Rota para carregar a página inicial com o formulário de upload."""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Rota para processar o upload do arquivo e gerar os PDFs."""
    if 'file' not in request.files:
        return "Nenhum arquivo enviado.", 400
    
    file = request.files['file']
    
    if file.filename == '':
        return "Nome de arquivo inválido.", 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        
        # Leitura do arquivo (usando BytesIO para evitar salvar no disco)
        file_bytes = file.read()
        file_like_object = io.BytesIO(file_bytes)
        
        try:
            # 2. Leitura da Planilha
            if filename.endswith('.csv'):
                # Tenta ler CSV com diferentes codificações comuns
                try:
                    df = pd.read_csv(file_like_object, encoding='utf-8')
                except UnicodeDecodeError:
                    file_like_object.seek(0) # Volta ao início
                    df = pd.read_csv(file_like_object, encoding='latin-1')
            else:
                # Arquivos Excel (xlsx, xls)
                df = pd.read_excel(file_like_object, engine='openpyxl')

            if df.empty:
                 return "A planilha está vazia.", 400

            # 3. Geração dos PDFs
            # df.to_dict('records') converte cada linha em um dicionário
            data_records = df.to_dict('records')
            
            # Usamos o io.BytesIO para criar um arquivo ZIP na memória
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
                for record in data_records:
                    # Garantimos que a chave 'ID_UNICO' exista e não seja nula
                    if 'ID_UNICO' in record and pd.notna(record['ID_UNICO']):
                        # O nome do arquivo será o ID_UNICO para fácil rastreamento
                        document_name = f"documento_{record['ID_UNICO']}"
                        
                        # Chama a função de geração de PDF do módulo importado
                        pdf_bytes = gerar_pdf_qr.gerar_pdf_com_qr(record)
                        
                        # Adiciona o PDF gerado ao arquivo ZIP
                        zip_file.writestr(f"{document_name}.pdf", pdf_bytes.getvalue())
            
            zip_buffer.seek(0)
            
            # 4. Envia o arquivo ZIP para download
            return send_file(
                zip_buffer,
                mimetype='application/zip',
                as_attachment=True,
                download_name='documentos_rastreaveis.zip'
            )

        except Exception as e:
            # Captura qualquer outro erro durante o processamento (ex: problemas com colunas)
            print(f"Erro de processamento: {e}")
            return f"Erro no processamento da planilha: {e}", 500

    return "Tipo de arquivo não permitido. Use .csv ou .xlsx.", 400

# Rota para rastreamento - Esta rota seria usada pelo QR Code
@app.route('/rastrear/<id_unico>')
def rastrear_documento(id_unico):
    """
    Simula a página de rastreamento acessada pelo QR Code.
    Aqui você faria a consulta ao banco de dados usando o id_unico.
    """
    # Você pode expandir esta página para consultar o Firestore ou outro DB.
    return render_template(
        'rastreamento.html',
        id_unico=id_unico,
        status="Documento VÁLIDO e em Processamento" # Exemplo de status
    )


if __name__ == '__main__':
    # Roda a aplicação localmente no modo debug
    app.run(debug=True)
