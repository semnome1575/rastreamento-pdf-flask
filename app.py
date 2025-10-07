import os
import zipfile
import io
import pandas as pd
from flask import Flask, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename
from fpdf import FPDF
from PIL import Image
import qrcode

# Configurações iniciais
app = Flask(__name__)
# A URL base usada para rastreamento (o Render a define)
BASE_URL = 'https://pdf-rastreavel-app.onrender.com' 

# Variável de URL de Rastreamento (A SER USADA NO QR CODE)
BASE_URL_RASTREAMENTO = BASE_URL

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
            # Retorna o erro no AJAX do frontend
            return f'Erro ao ler arquivo Excel: {e}', 500
    elif filename.endswith('.csv'):
        # Tenta ler CSV com os delimitadores mais comuns e UTF-8
        for encoding in ['utf-8', 'latin-1']:
            for delimiter in [',', ';']: # Tenta vírgula e ponto-e-vírgula
                try:
                    file_stream.seek(0)
                    # CORREÇÃO AQUI: adicionando o separador 'sep'
                    df = pd.read_csv(file_stream, encoding=encoding, sep=delimiter)
                    
                    # Se a leitura for bem sucedida e tiver pelo menos 2 colunas, consideramos OK
                    if len(df.columns) > 1:
                        # Limpa espaços em branco nos nomes das colunas
                        df.columns = df.columns.str.strip()
                        # Sai do loop
                        break 
                    else:
                        continue # Tenta o próximo delimitador/encoding
                except Exception:
                    continue # Tenta o próximo delimitador/encoding
            if 'df' in locals() and len(df.columns) > 1:
                break
        
        if 'df' not in locals() or len(df.columns) <= 1:
            return 'Erro ao ler arquivo CSV. Verifique o delimitador (vírgula ou ponto-e-vírgula) e a codificação.', 500
    else:
        return 'Formato de arquivo não suportado. Use CSV ou Excel.', 400

    # Validação de colunas obrigatórias
    colunas_obrigatorias = ['ID_UNICO', 'NOME_CLIENTE', 'DATA_EMISSAO']
    # Garante que as colunas existem
    if not all(col in df.columns for col in colunas_obrigatorias):
        # Retorna as colunas encontradas para ajudar na depuração
        colunas_encontradas = ", ".join(df.columns.tolist())
        return f'Arquivo precisa das colunas: {", ".join(colunas_obrigatorias)}. Colunas encontradas: {colunas_encontradas}', 400

    # Criação do ZIP e buffer de memória para o ZIP
    zip_buffer = io.BytesIO()
    
    try:
        with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
            # Itera sobre cada linha da planilha
            for index, row in df.iterrows():
                unique_id = str(row['ID_UNICO'])
                
                # 1. Cria a URL de rastreamento para o QR Code
                rastreamento_url = f"{BASE_URL_RASTREAMENTO}{url_for('rastreamento', unique_id=unique_id)}"
                
                # 2. Gera o PDF em um buffer de memória
                pdf = FPDF('P', 'mm', 'A4')
                pdf.set_auto_page_break(auto=True, margin=15)
                
                gerar_pdf_com_qr(pdf, row.to_dict(), unique_id, rastreamento_url)
                
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
        return f'Erro de processamento no servidor (Backend): {e}', 500

# Rota de rastreamento (simulada)
@app.route('/rastreamento/<unique_id>')
def rastreamento(unique_id):
    # Esta rota é a que o QR Code aponta. 
    # Ela só precisa confirmar que o ID foi lido.
    return render_template(
        'rastreamento.html', 
        unique_id=unique_id, 
        base_url=BASE_URL_RASTREAMENTO
    )

# Criação de um template HTML simples para a página de rastreamento
@app.route('/rastreamento.html')
def rastreamento_html():
    return render_template('rastreamento.html')
