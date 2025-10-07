import os
import zipfile
import io
import pandas as pd
from flask import Flask, render_template, request, url_for, Response, make_response
from werkzeug.utils import secure_filename
from fpdf import FPDF
from PIL import Image
import qrcode
import numpy as np # Importado para ajudar a tratar valores NaN (Not a Number)

# Configurações iniciais
app = Flask(__name__)
# A URL base usada para rastreamento (o Render a define)
BASE_URL = 'https://pdf-rastreavel-app.onrender.com' 

# Variável de URL de Rastreamento (A SER USADA NO QR CODE)
BASE_URL_RASTREAMENTO = BASE_URL

# FUNÇÃO AUXILIAR CRÍTICA: Sanitiza o texto para FPDF
def sanitize_text(text):
    """
    Garante que o texto é seguro para FPDF, removendo ou ignorando 
    caracteres que não são ASCII (como acentos e cedilha).
    """
    if pd.isna(text) or text is None:
        return 'N/A'
    
    # Converte para string, depois força codificação latin-1 (padrão FPDF)
    # usando 'ignore' para remover caracteres não suportados, e decodifica de volta.
    return str(text).encode('latin-1', 'ignore').decode('latin-1').strip()

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
    e um QR Code rastreável, com sanitizacao de dados.
    """
    pdf.add_page()

    # Título (sem acentos para segurança máxima no FPDF)
    pdf.set_font("Arial", 'B', 18)
    pdf.cell(0, 15, 'Documento Rastreavel', 0, 1, 'C')

    # Dados
    pdf.set_font("Arial", '', 12)
    
    # 1. Sanitiza os dados da planilha antes de usar
    nome_cliente = sanitize_text(row_data.get('NOME_CLIENTE'))
    data_emissao = sanitize_text(row_data.get('DATA_EMISSAO'))
    
    # 2. Usa os dados sanitizados e strings fixas sem acento
    pdf.cell(0, 8, f"ID Unico: {unique_id}", 0, 1)
    pdf.cell(0, 8, f"Nome do Cliente: {nome_cliente}", 0, 1)
    pdf.cell(0, 8, f"Data de Emissao: {data_emissao}", 0, 1)
    pdf.ln(10)

    # Informacao de Rastreamento (sem acento)
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
    img_pil.save(img_buffer, format="PNG")
    img_buffer.seek(0)

    # Adiciona a imagem ao PDF
    page_width = pdf.w - 2 * pdf.l_margin
    img_size = 50 
    x_pos = (pdf.w - img_size) / 2
    
    pdf.image(img_buffer, x=x_pos, y=pdf.get_y(), w=img_size, h=img_size, type='PNG')
    pdf.ln(img_size + 10) 
    
    # Campo de Rastreio Simulado (Rodapé - sem acento)
    pdf.set_y(pdf.h - 20)
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(0, 5, f"CHAVE DE RASTREIO INTERNO: {unique_id}", 0, 0, 'C')

# Função para enviar o ZIP por streaming
def send_file_streamed(zip_buffer, filename='documentos_rastreaveis.zip'):
    """Envia o conteúdo do buffer em streaming para evitar timeouts."""
    zip_buffer.seek(0)
    
    # Cria uma função geradora para ler o buffer em pedaços (chunks)
    def generate():
        chunk_size = 8192 # 8KB chunks
        while True:
            chunk = zip_buffer.read(chunk_size)
            if not chunk:
                break
            yield chunk

    # Cria a resposta do Flask usando o gerador
    response = Response(generate(), mimetype='application/zip')
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    response.headers['Content-Length'] = str(zip_buffer.getbuffer().nbytes)
    return response

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
    file_stream = io.BytesIO(file.read())
    
    # Detecção e leitura do arquivo
    df = None # Inicializa df
    if filename.endswith(('.xls', '.xlsx')):
        try:
            df = pd.read_excel(file_stream)
        except Exception as e:
            return f'Erro ao ler arquivo Excel: {e}', 500
            
    elif filename.endswith('.csv'):
        # Tentativa 1: Delimitador Vírgula (padrão US/Internacional) com Latin-1
        try:
            file_stream.seek(0)
            df = pd.read_csv(file_stream, encoding='latin-1', sep=',')
            df.columns = df.columns.str.strip()
            print(f"DEBUG: CSV lido com SUCESSO (Vírgula, Latin-1) - {len(df)} linhas.")
            
        except Exception as e:
            # Tentativa 2: Falhou na vírgula, tenta Ponto-e-vírgula (padrão BR) com Latin-1
            try:
                file_stream.seek(0)
                df = pd.read_csv(file_stream, encoding='latin-1', sep=';')
                df.columns = df.columns.str.strip()
                print(f"DEBUG: CSV lido com SUCESSO (Ponto-e-vírgula, Latin-1) - {len(df)} linhas.")
            except Exception as e2:
                # Falha total: retorna erro detalhado
                return f'Erro fatal ao ler o arquivo CSV. Tente salvar o arquivo como "CSV (Delimitado por vírgulas)" e verifique a codificação. Detalhe da falha: {e2}', 500
            
        if df is None or len(df.columns) <= 1:
            return 'Erro ao ler arquivo CSV. O delimitador não foi reconhecido corretamente. Verifique se o arquivo está formatado como CSV.', 500
            
    else:
        return 'Formato de arquivo não suportado. Use CSV ou Excel.', 400

    # Validação de colunas obrigatórias
    colunas_obrigatorias = ['ID_UNICO', 'NOME_CLIENTE', 'DATA_EMISSAO']
    if not all(col in df.columns for col in colunas_obrigatorias):
        colunas_encontradas = ", ".join(df.columns.tolist())
        return f'Arquivo precisa das colunas: {", ".join(colunas_obrigatorias)}. Colunas encontradas: {colunas_encontradas}', 400

    # Criação do ZIP e buffer de memória para o ZIP
    zip_buffer = io.BytesIO()
    
    try:
        with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
            for index, row in df.iterrows():
                try:
                    # Trata valores nulos ou NaN no ID_UNICO
                    unique_id_raw = row.get('ID_UNICO')
                    # Usamos np.isnan para verificar NaN de forma segura
                    if pd.isna(unique_id_raw) or (isinstance(unique_id_raw, float) and np.isnan(unique_id_raw)):
                        unique_id = f"ERRO-LINHA-{index + 1}"
                    else:
                        unique_id = str(unique_id_raw).strip()
                        if not unique_id:
                            unique_id = f"ERRO-LINHA-{index + 1}"
                    
                    # 1. Cria a URL de rastreamento para o QR Code
                    rastreamento_url = f"{BASE_URL_RASTREAMENTO}{url_for('rastreamento', unique_id=unique_id)}"
                    
                    # 2. Gera o PDF em um buffer de memória
                    pdf = FPDF('P', 'mm', 'A4')
                    pdf.set_auto_page_break(auto=True, margin=15)
                    
                    gerar_pdf_com_qr(pdf, row.to_dict(), unique_id, rastreamento_url)
                    
                    # Obtém os bytes diretamente no buffer
                    pdf_output_buffer = io.BytesIO()
                    pdf.output(dest='B', out=pdf_output_buffer)
                    pdf_output = pdf_output_buffer.getvalue()
                    
                    # 3. Adiciona o PDF ao ZIP
                    pdf_filename = f"documento_{unique_id}.pdf"
                    zip_file.writestr(pdf_filename, pdf_output)
                
                except Exception as row_e:
                    # Captura o erro específico da linha e retorna imediatamente
                    error_message = f"Erro fatal ao gerar o PDF na linha {index + 1} (ID: {row.get('ID_UNICO', 'N/A')}). Detalhe: {row_e}"
                    return error_message, 500

        # Agora, envia o ZIP usando a função de streaming
        return send_file_streamed(zip_buffer)

    except Exception as e:
        # Erro genérico de processamento (fora do loop)
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
