import os
import io
import re
import zipfile
import pandas as pd
import qrcode
from fpdf import FPDF
from PIL import Image
from flask import Flask, render_template, request, send_file, redirect, url_for, abort

# Configurações de Segurança
# Permitir apenas estas extensões de arquivo
ALLOWED_EXTENSIONS = {'csv', 'xls', 'xlsx'} 
MAX_CONTENT_LENGTH = 16 * 1024 * 1024 # Limite de 16MB para o upload

# O nome da URL de rastreamento deve ser definido APÓS a publicação na nuvem.
# Exemplo: Se o Render te der a URL 'https://meuapp.onrender.com', você deve mudar para:
# BASE_URL_RASTREAMENTO = "https://meuapp.onrender.com/documento/"
BASE_URL_RASTREAMENTO = "http://rastreio.exemplo.com.br/documento/" 


app = Flask(__name__, template_folder='templates')
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH


# --- Funções de Segurança ---

def allowed_file(filename):
    """Verifica se a extensão do arquivo é permitida."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Funções de Geração de PDF (Movidas de gerar_pdf_qr.py) ---

def gerar_pdf_com_qr(dados_linha):
    """
    Gera um PDF contendo os dados de uma linha da planilha e um QR Code único.

    Args:
        dados_linha (pandas.Series): Uma linha de dados da planilha.
        
    Returns:
        io.BytesIO: Um buffer de memória contendo o PDF gerado.
    """
    # 1. Extração de Dados e Criação da URL Única
    documento_id = str(dados_linha.iloc[0]) 
    
    # Gera a URL de rastreamento única
    url_rastreamento = f"{BASE_URL_RASTREAMENTO}{documento_id}"
    dados_secundarios = dados_linha.iloc[1:]
    
    
    # 2. Criação do QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url_rastreamento)
    qr.make(fit=True)
    
    img_qr = qr.make_image(fill_color="black", back_color="white")
    
    qr_buffer = io.BytesIO()
    img_qr.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)
    
    
    # 3. Criação do PDF
    pdf = FPDF('P', 'mm', 'A4')
    pdf.add_page()
    
    # --- Estilização do Título ---
    pdf.set_font('Arial', 'B', 18)
    pdf.cell(0, 10, f'Documento: {documento_id}', 0, 1, 'C') 
    pdf.ln(10) 
    
    # --- Tabela de Dados Secundários ---
    pdf.set_font('Arial', 'B', 12)
    w_label = 75 
    w_value = 100
    
    for coluna, valor in zip(dados_linha.index, dados_linha.values):
        if coluna != dados_linha.index[0]:
            pdf.set_fill_color(240, 240, 240) # Cinza claro para o fundo
            
            pdf.cell(w_label, 8, f'{coluna}:', 1, 0, 'L', 1) 
            
            pdf.set_fill_color(255, 255, 255) # Fundo branco
            pdf.set_font('Arial', '', 12) # Volta para fonte normal
            
            # Garante que o valor não é NaN e converte para string
            display_value = str(valor) if pd.notna(valor) else "N/A"
            pdf.cell(w_value, 8, display_value, 1, 1, 'L', 1)
            pdf.set_font('Arial', 'B', 12) # Volta para negrito
            
    pdf.ln(15) 
    
    # --- Inserção do QR Code ---
    qr_code_size_mm = 40
    x_pos = (210 - qr_code_size_mm) / 2 
    
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 5, "Use a câmera do seu celular para rastrear:", 0, 1, 'C')
    pdf.ln(2)
    
    pdf.image(qr_buffer, x=x_pos, y=pdf.get_y(), w=qr_code_size_mm, h=qr_code_size_mm, type='PNG')
    pdf.ln(qr_code_size_mm + 5) 

    # --- Nota de Rodapé ---
    pdf.set_font('Arial', 'I', 8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, f'URL Única: {url_rastreamento}', 0, 1, 'C')

    # 4. Finalização
    pdf_buffer = io.BytesIO()
    pdf.output(pdf_buffer, 'S') 
    pdf_buffer.seek(0)
    
    return pdf_buffer

# --- Rotas do Aplicativo ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    # 1. SEGURANÇA: Verifica se o arquivo foi enviado corretamente
    if 'file' not in request.files:
        abort(400, description="Nenhum arquivo enviado.")
    
    file = request.files['file']
    
    if file.filename == '':
        abort(400, description="Arquivo não selecionado.")

    # 2. SEGURANÇA: Verifica o nome e extensão do arquivo
    if not file or not allowed_file(file.filename):
        abort(400, description="Tipo de arquivo não permitido. Apenas CSV, XLS ou XLSX.")

    try:
        # Lê o arquivo para um DataFrame do Pandas
        filename_ext = file.filename.rsplit('.', 1)[1].lower()
        if filename_ext == 'csv':
            df = pd.read_csv(file)
        else: # xls ou xlsx
            df = pd.read_excel(file)
            
    except Exception as e:
        # Erro ao ler o arquivo (formato inválido, etc.)
        abort(500, description=f"Erro ao processar a planilha: {e}")

    # Cria o buffer ZIP na memória
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        
        # Itera sobre cada linha do DataFrame para gerar um PDF
        for index, row in df.iterrows():
            pdf_buffer = gerar_pdf_com_qr(row)
            
            # O nome do arquivo PDF será o ID Único da primeira coluna
            documento_id = str(row.iloc[0])
            pdf_filename = f'documento_{documento_id}.pdf'
            
            # Adiciona o PDF ao arquivo ZIP
            zip_file.writestr(pdf_filename, pdf_buffer.getvalue())

    # Prepara o buffer para download
    zip_buffer.seek(0)
    
    # Retorna o arquivo ZIP para o usuário
    return send_file(zip_buffer,
                     mimetype='application/zip',
                     as_attachment=True,
                     download_name='documentos_rastreaveis.zip')

@app.route('/documento/<unique_id>')
def rastrear_documento(unique_id):
    """
    SEGURANÇA: Esta rota simula a página de rastreamento.
    Ela deve ser o ÚNICO ponto de exposição na internet.
    """
    
    # 1. SEGURANÇA CRÍTICA: Validação do ID (Proteção contra Injeção de Código)
    # Apenas permite letras, números e hífens.
    if not re.match(r'^[a-zA-Z0-9-]+$', unique_id):
        abort(400, description="ID de documento inválido ou formato incorreto.")

    # 2. Aqui você faria a consulta real a um banco de dados
    # para buscar informações sobre o 'unique_id'.
    
    # 3. SIMULAÇÃO: Retorna uma página HTML com a informação
    html_content = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Rastreamento de Documento</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="min-h-screen flex items-center justify-center p-4 bg-gray-100">
        <div class="max-w-md w-full bg-white p-6 rounded-lg shadow-xl text-center">
            <h1 class="text-3xl font-bold text-indigo-700 mb-4">Rastreamento de Documento</h1>
            <p class="text-lg text-gray-700 mb-2">ID Verificado:</p>
            <p class="text-2xl font-mono text-gray-900 bg-gray-200 p-2 rounded-md mb-6">{unique_id}</p>
            
            <div class="p-4 bg-green-100 border-l-4 border-green-500 text-green-700">
                <p class="font-semibold text-left">STATUS ATUAL: Cópia VÁLIDA e RASTREÁVEL</p>
                <ul class="list-disc list-inside text-left mt-2 text-sm">
                    <li>Destinatário (Simulação): João da Silva</li>
                    <li>Status de Uso: Entregue em 10/06/2025.</li>
                    <li><strong class="text-red-600">Alerta:</strong> Esta cópia é única e qualquer vazamento será atribuído a quem a recebeu.</li>
                </ul>
            </div>
            
            <p class="text-xs text-gray-500 mt-6">Sistema de validação e rastreamento V1.0</p>
        </div>
    </body>
    </html>
    """
    return html_content, 200 # Retorna o HTML com status OK


if __name__ == '__main__':
    # ATENÇÃO: Nunca use debug=True em produção (na nuvem)!
    # Para rodar localmente no seu PC:
    app.run(host='0.0.0.0', port=5000)
