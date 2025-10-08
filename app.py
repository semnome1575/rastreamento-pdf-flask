import os
import zipfile
import io
import pandas as pd
from flask import Flask, render_template, request, url_for, Response, make_response
from werkzeug.utils import secure_filename
from fpdf2 import FPDF # <--- CORRIGIDO: Usando a biblioteca fpdf2
from PIL import Image
import qrcode
import numpy as np # Importado para ajudar a tratar valores NaN (Not a Number)
import traceback # Importado para capturar a pilha de erros (traceback)

# Configurações iniciais
app = Flask(__name__)
# A URL base usada para rastreamento (o Render a define)
BASE_URL = 'https://pdf-rastreavel-app.onrender.com' 

# Variável de URL de Rastreamento (A SER USADA NO QR CODE)
BASE_URL_RASTREAMENTO = BASE_URL

# FUNÇÃO AUXILIAR CRÍTICA: Sanitiza o texto para FPDF
def sanitize_text(text):
    """
    Garantes que o texto é seguro para FPDF, removendo ou ignorando 
    caracteres que não são ASCII (como acentos e cedilha).
    """
    if pd.isna(text) or text is None:
        return 'N/A'
    
    # Converte para string, depois força codificação latin-1 (padrão FPDF)
    # usando 'ignore' para remover caracteres não suportados, e decodifica de volta.
    return str(text).encode('latin-1', 'ignore').decode('latin-1').strip()

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
    nome_cliente = sanitize_text(row_data.get('NOME_CLIENTE', 'N/A'))
    data_emissao = sanitize_text(row_data.get('DATA_EMISSAO', 'N/A'))
    
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
    img_size = 50 
    x_pos = (pdf.w - img_size) / 2
    
    # Com fpdf2, esta sintaxe é a correta para passar um buffer de imagem
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
    # NOVO: Bloco de exceção principal para capturar e registrar qualquer erro fatal
    try:
        if 'file' not in request.files:
            return 'Nenhum arquivo enviado', 400
        
        file = request.files['file']
        if file.filename == '':
            return 'Nenhum arquivo selecionado', 400
        
        filename = secure_filename(file.filename)
        
        # Lê o arquivo COMPLETO em memória
        file_bytes = file.read()
        
        # Detecção e leitura do arquivo
        df = None # Inicializa df
        if filename.endswith(('.xls', '.xlsx')):
            file_stream = io.BytesIO(file_bytes)
            
            # TENTATIVA 1: Ler como XLSX (OpenPyXL)
            try:
                print(f"DEBUG: Tentando ler Excel como XLSX (OpenPyXL): {filename}")
                df = pd.read_excel(file_stream, engine='openpyxl') 
                print(f"DEBUG: Excel lido com SUCESSO via OpenPyXL. {len(df)} linhas.")
            except Exception as e_openpyxl:
                file_stream.seek(0) # Volta o ponteiro para o início para tentar de novo
                
                # TENTATIVA 2: Ler como XLS (xlrd)
                try:
                    print(f"DEBUG: Falha em OpenPyXL. Tentando como XLS (xlrd): {filename}")
                    # Este bloco irá falhar no Render pois 'xlrd' não está instalado.
                    df = pd.read_excel(file_stream, engine='xlrd') 
                    print(f"DEBUG: Excel lido com SUCESSO via xlrd. {len(df)} linhas.")
                except Exception as e_xlrd:
                    error_traceback = traceback.format_exc()
                    print(f"ERRO FATAL LEITURA EXCEL (Final): {error_traceback}")
                    return f'Erro ao ler arquivo Excel. Tentativas com openpyxl (xlsx) e xlrd (xls) falharam. Por favor, use um arquivo CSV.', 500
                
        elif filename.endswith('.csv'):
            # Abordagem mais robusta para leitura de CSV usando BytesIO
            file_stream_bytes = io.BytesIO(file_bytes)
            
            # Tentativa 1: Delimitador Vírgula (encoding latin-1)
            try:
                file_stream_bytes.seek(0)
                # O Pandas lida melhor com quebras de linha quando recebe o BytesIO diretamente
                df = pd.read_csv(file_stream_bytes, sep=',', encoding='latin-1')
                df.columns = df.columns.str.strip()
                print(f"DEBUG: CSV lido com SUCESSO (Vírgula) - {len(df)} linhas. Colunas encontradas: {df.columns.tolist()}")
            except Exception as e:
                # Tentativa 2: Tenta Ponto-e-vírgula (encoding latin-1)
                try:
                    file_stream_bytes.seek(0)
                    df = pd.read_csv(file_stream_bytes, sep=';', encoding='latin-1')
                    df.columns = df.columns.str.strip()
                    print(f"DEBUG: CSV lido com SUCESSO (Ponto-e-vírgula) - {len(df)} linhas. Colunas encontradas: {df.columns.tolist()}")
                except Exception as e2:
                    return f'Erro fatal ao ler o arquivo CSV. Tente salvar o arquivo como "CSV (Delimitado por vírgulas)" e verifique a codificação. Detalhe da falha: {e2}', 500
                
            # Verificação de leitura bem-sucedida, especialmente se tiver poucas colunas
            if df is None or len(df.columns) <= 1:
                return 'Erro ao ler arquivo CSV. O delimitador não foi reconhecido corretamente. Verifique se o arquivo está formatado como CSV.', 500
                
        else:
            return 'Formato de arquivo não suportado. Use CSV ou Excel.', 400

        # Validação de colunas obrigatórias
        colunas_obrigatorias = ['ID_UNICO', 'NOME_CLIENTE', 'DATA_EMISSAO']
        
        # AQUI O ERRO 400 OCORREU
        if len(df) == 0:
            return 'O arquivo CSV/Excel foi lido, mas não contém nenhuma linha de dados válida.', 400

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
                        error_traceback = traceback.format_exc()
                        print(f"ERRO FATAL GERAÇÃO PDF NA LINHA {index + 1}: {error_traceback}")
                        error_message = f"Erro fatal ao gerar o PDF na linha {index + 1} (ID: {row.get('ID_UNICO', 'N/A')}). Detalhe: {row_e}"
                        return error_message, 500

            # Envia o ZIP usando a função de streaming
            return send_file_streamed(zip_buffer)

        except Exception as e:
            error_traceback = traceback.format_exc()
            print(f"ERRO DE PROCESSAMENTO NO SERVIDOR (FORA DO LOOP): {error_traceback}")
            return f'Erro de processamento no servidor (Backend): {e}', 500
    
    except Exception as e_final:
        # Última chance de logar se o erro for ainda mais alto na pilha
        error_traceback = traceback.format_exc()
        print(f"ERRO DE CONEXÃO/IO: {error_traceback}")
        return f'Erro de conexão/IO. Detalhe: {e_final}', 500


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

# Criação de um template HTML simples para a página de rastreamento (Rota de teste)
@app.route('/rastreamento.html')
def rastreamento_html():
    return render_template('rastreamento.html')
