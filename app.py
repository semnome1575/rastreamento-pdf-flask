import os
import io
import pandas as pd
import tempfile
import shutil
import zipfile
import logging # Para debug no Render

# Importações do Flask
from flask import Flask, request, send_file, render_template, abort

# Importação da nossa lógica de geração de PDF
from gerar_pdf_qr import gerar_pdf_com_qr

# --- Configuração do App ---

# 1. Inicializa o Flask
app = Flask(__name__, template_folder='templates')

# 2. Configurações de upload (O Render usa /tmp para arquivos temporários)
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir() # Usa o diretório temporário padrão do OS

# 3. Configuração da URL de Rastreamento
# Tenta obter a variável de ambiente BASE_URL_RASTREAMENTO (definida no Render)
# O valor padrão é um URL de exemplo para caso a variável não esteja definida localmente.
# Nota: A variável é configurada no Render com o valor: https://pdf-rastreavel-app-1.onrender.com/documento/
BASE_URL = os.environ.get('BASE_URL_RASTREAMENTO', 'http://rastreio.exemplo.com.br/documento/')
app.logger.info(f"URL de Rastreamento Base configurada para: {BASE_URL}")

# Garante que o módulo de geração de PDF use a URL configurada
from gerar_pdf_qr import BASE_URL_RASTREAMENTO
gerar_pdf_qr.BASE_URL_RASTREAMENTO = BASE_URL

# --- Rotas do Aplicativo ---

@app.route('/', methods=['GET'])
def index():
    """Rota principal que renderiza a interface de upload."""
    try:
        # Tenta renderizar o templates/index.html
        return render_template('index.html')
    except Exception as e:
        app.logger.error(f"Erro ao renderizar index.html: {e}")
        return "Erro interno do servidor ao carregar a página inicial.", 500


@app.route('/upload', methods=['POST'])
def upload_file():
    """
    Rota para receber a planilha, processar os dados e gerar um arquivo ZIP
    contendo todos os PDFs rastreáveis.
    """
    app.logger.info("Tentativa de upload de arquivo iniciada.")
    
    # 1. Validação e Leitura do Arquivo
    if 'file' not in request.files:
        return "Nenhum arquivo enviado.", 400
    
    file = request.files['file']
    if file.filename == '':
        return "Nenhum arquivo selecionado.", 400

    filename = file.filename
    app.logger.info(f"Arquivo recebido: {filename}")
    
    # Leitura do arquivo (usando io.BytesIO para evitar salvar no disco)
    try:
        file_stream = io.BytesIO(file.read())
        
        if filename.endswith('.csv'):
            df = pd.read_csv(file_stream)
        elif filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file_stream)
        else:
            return "Formato de arquivo não suportado. Use CSV ou XLSX.", 400
        
    except Exception as e:
        app.logger.error(f"Erro na leitura/parsing do arquivo: {e}")
        return f"Erro ao processar a planilha: {e}", 500

    if df.empty:
        return "A planilha está vazia.", 400
    
    # 2. Geração dos PDFs
    
    # Cria um buffer de memória para armazenar o arquivo ZIP final
    zip_buffer = io.BytesIO()
    
    # Cria o arquivo ZIP
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        
        # Itera sobre cada linha da planilha
        for index, row in df.iterrows():
            try:
                # Gera o PDF usando a lógica do nosso módulo
                pdf_buffer = gerar_pdf_com_qr(row)
                
                # Usa o ID da primeira coluna para nomear o arquivo
                documento_id = str(row.iloc[0]) 
                pdf_filename = f"Documento_{documento_id}.pdf"
                
                # Adiciona o PDF ao arquivo ZIP
                zf.writestr(pdf_filename, pdf_buffer.getvalue())
                
            except Exception as e:
                app.logger.error(f"Erro ao gerar PDF para linha {index}: {e}")
                # Continua para a próxima linha se houver erro
                
    # 3. Finalização e Resposta
    
    # Reposiciona o ponteiro para o início do buffer antes de enviar
    zip_buffer.seek(0)
    
    app.logger.info(f"Processamento concluído. {len(df)} documentos gerados (ou tentados).")
    
    # Retorna o arquivo ZIP
    return send_file(
        zip_buffer,
        as_attachment=True,
        download_name='documentos_rastreaveis.zip',
        mimetype='application/zip'
    )

@app.route('/documento/<string:documento_id>', methods=['GET'])
def rastrear_documento(documento_id):
    """
    Rota de placeholder para simular o rastreamento. 
    Esta rota é acessada pelo QR Code.
    """
    app.logger.info(f"Tentativa de rastreamento para ID: {documento_id}")
    
    # Retorna uma página simples de sucesso/rastreamento
    return f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Rastreio Concluído</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>body {{ font-family: 'Inter', sans-serif; background-color: #f7f9fb; }}</style>
    </head>
    <body class="min-h-screen flex items-center justify-center p-4">
        <div class="max-w-md w-full p-8 space-y-4 bg-white shadow-xl rounded-xl text-center">
            <svg xmlns="http://www.w3.org/2000/svg" class="mx-auto h-16 w-16 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h1 class="text-2xl font-bold text-gray-800">Rastreamento do Documento</h1>
            <p class="text-lg text-green-600 font-semibold">STATUS: Recebido e Confirmado!</p>
            <p class="text-gray-600">O QR Code para o documento <code class="bg-gray-100 p-1 rounded font-mono">{documento_id}</code> foi lido com sucesso.</p>
            <p class="text-sm text-gray-500 pt-4">Em um sistema real, aqui você veria detalhes de data, hora e localização do rastreamento.</p>
        </div>
    </body>
    </html>
    """, 200

# Esta parte é importante para que o Flask não rode em modo debug no Render
if __name__ == '__main__':
    # Esta linha não será executada pelo Gunicorn, mas é útil para testes locais
    app.run(debug=True, port=os.environ.get("PORT", 5000))
