import os
import zipfile
import io
import pandas as pd
from flask import Flask, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename
from fpdf import FPDF
from PIL import Image
import qrcode
import gerar_pdf_qr

# Configurações iniciais
app = Flask(__name__)
# O Render usa a porta 10000. No entanto, o Gunicorn lida com isso.
# A URL base será o domínio do Render.
BASE_URL = 'https://pdf-rastreavel-app.onrender.com' 

# Configurar a URL de rastreamento no módulo gerador
# Importamos o módulo inteiro para poder acessar a variável global BASE_URL_RASTREAMENTO
gerar_pdf_qr.BASE_URL_RASTREAMENTO = BASE_URL


# Função auxiliar para configurar o PDF e a célula do texto
def set_pdf_style(pdf):
    """Configura o estilo padrão do PDF."""
    pdf.set_font("Arial", size=12)
    pdf.set_margins(10, 10, 10)
    pdf.add_page()

# FUNÇÃO PRINCIPAL: Gera o PDF a partir dos dados de uma linha
def gerar_pdf_com_qr(pdf, row_data, unique_id, rastreamento_url):
    """
    Gera o conteúdo de um único PDF (uma página) com os dados da linha 
    e um QR Code rastreável.
    """
    pdf.add_page()

    # Título
    pdf.set_font("Arial", 'B', 18)
    pdf.cell(0, 15, 'Documento Rastreável', 0, 1, 'C')

    # Dados
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 8, f"ID Único: {unique_id}", 0, 1)
    pdf.cell(0, 8, f"Nome do Cliente: {row_data.get('NOME_CLIENTE', 'N/A')}", 0, 1)
    pdf.cell(0, 8, f"Data de Emissão: {row_data.get('DATA_EMISSAO', 'N/A')}", 0, 1)
    pdf.ln(10)

    # Informação de Rastreamento
    pdf.set_font("Arial", 'I', 10)
    pdf.multi_cell(0, 5, 
        f"Este documento pode ser verificado em: {rastreamento_url}", 0, 'C'
    )
    pdf.ln(10)

    # Geração do QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(rastreamento_url)
    qr.make(fit=True)

    # Cria uma imagem PIL
    img_pil = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    
    # Salva a imagem em um buffer de memória (IO)
    img_buffer = io.BytesIO()
    # Usamos o formato 'PNG' para não perder a qualidade e ser compatível com FPDF
    img_pil.save(img_buffer, format="PNG")
    img_buffer.seek(0)

    # Adiciona a imagem ao PDF (colocada no centro da largura da página)
    page_width = pdf.w - 2 * pdf.l_margin
    img_size = 50  # Tamanho fixo do QR code
    x_pos = (pdf.w - img_size) / 2
    
    pdf.image(img_buffer, x=x_pos, y=pdf.get_y(), w=img_size, h=img_size, type='PNG')
    pdf.ln(img_size + 10) # Avança para depois do QR code
    
    # Campo de Rastreio Simulado (Rodapé)
    pdf.set_y(pdf.h - 20)
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(0, 5, f"CHAVE DE RASTREIO INTERNO: {unique_id}", 0, 0, 'C')

# Rota principal para carregar o HTML
@app.route('/')
def index():
    return render_template('index.html')

# Rota de upload de arquivo
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return 'Nenhum arquivo enviado', 400
    
    file = request.files['file']
    if file.filename == '':
        return 'Nenhum arquivo selecionado', 400
    
    filename = secure_filename(file.filename)
    # Salva o arquivo em memória para processamento (não precisamos salvar no disco)
    file_stream = io.BytesIO(file.read())
    
    # Detecta o tipo de arquivo
    if filename.endswith(('.xls', '.xlsx')):
        try:
            # Para arquivos Excel
            df = pd.read_excel(file_stream)
        except Exception as e:
            return f'Erro ao ler arquivo Excel: {e}', 500
    elif filename.endswith('.csv'):
        try:
            # TENTA LER CSV com UTF-8 (Correção da Codificação)
            df = pd.read_csv(file_stream, encoding='utf-8')
        except UnicodeDecodeError:
            # Se a leitura falhar, tenta com codificação 'latin-1' (comum em PT-BR)
            file_stream.seek(0) # Volta ao início do arquivo
            try:
                df = pd.read_csv(file_stream, encoding='latin-1')
            except Exception as e:
                return f'Erro ao ler arquivo CSV (codificação): {e}', 500
        except Exception as e:
            return f'Erro ao ler arquivo CSV: {e}', 500
    else:
        return 'Formato de arquivo não suportado. Use CSV ou Excel.', 400

    # Validação de colunas obrigatórias
    colunas_obrigatorias = ['ID_UNICO', 'NOME_CLIENTE', 'DATA_EMISSAO']
    if not all(col in df.columns for col in colunas_obrigatorias):
        return f'Arquivo precisa das colunas: {", ".join(colunas_obrigatorias)}', 400

    # Criação do ZIP e buffer de memória para o ZIP
    zip_buffer = io.BytesIO()
    
    try:
        with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
            # Itera sobre cada linha da planilha
            for index, row in df.iterrows():
                unique_id = str(row['ID_UNICO'])
                
                # 1. Cria a URL de rastreamento para o QR Code
                # Usamos url_for para criar um link dinâmico, simulando o endpoint de rastreamento
                rastreamento_url = f"{BASE_URL}{url_for('rastreamento', unique_id=unique_id)}"
                
                # 2. Gera o PDF em um buffer de memória
                pdf = FPDF('P', 'mm', 'A4')
                pdf.set_auto_page_break(auto=True, margin=15)
                
                gerar_pdf_qr.gerar_pdf_com_qr(pdf, row.to_dict(), unique_id, rastreamento_url)
                
                pdf_output = pdf.output(dest='S').encode('latin-1')
                
                # 3. Adiciona o PDF ao ZIP
                pdf_filename = f"documento_{unique_id}.pdf"
                zip_file.writestr(pdf_filename, pdf_output)

        zip_buffer.seek(0)
        
        # 4. Envia o arquivo ZIP
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name='documentos_rastreaveis.zip'
        )

    except Exception as e:
        # Erro genérico de processamento
        return f'Erro de processamento no servidor: {e}', 500

# Rota de rastreamento (simulada)
@app.route('/rastreamento/<unique_id>')
def rastreamento(unique_id):
    # Esta rota é a que o QR Code aponta. 
    # Ela só precisa confirmar que o ID foi lido.
    return render_template(
        'rastreamento.html', 
        unique_id=unique_id, 
        base_url=BASE_URL
    )

# Criação de um template HTML simples para a página de rastreamento
@app.route('/rastreamento.html')
def rastreamento_html():
    return '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Status do Documento</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen flex items-center justify-center p-4 bg-gray-50">
    <div class="max-w-md w-full bg-white p-8 rounded-xl shadow-xl text-center">
        <h1 class="text-3xl font-bold text-green-600 mb-4">VERIFICAÇÃO DE DOCUMENTO</h1>
        <svg xmlns="http://www.w3.org/2000/svg" class="h-16 w-16 text-green-500 mx-auto mb-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p class="text-gray-700 text-lg mb-2">Documento Validado com Sucesso!</p>
        <p class="text-gray-500 text-sm">O ID de rastreamento 
            <span class="font-mono text-indigo-600">{{ unique_id }}</span> 
            foi encontrado. Este é o documento original.</p>
        <div class="mt-8">
            <a href="/" class="bg-indigo-600 text-white py-2 px-4 rounded-lg hover:bg-indigo-700 transition duration-300 font-semibold">Voltar para o Upload</a>
        </div>
    </div>
</body>
</html>
'''

# Se você estiver rodando localmente (o Render ignora esta parte)
if __name__ == '__main__':
    # Usado apenas para fins de debug local, a porta Render é 10000
    app.run(debug=True)
