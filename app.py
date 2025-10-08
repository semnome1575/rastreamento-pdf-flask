import os
import io
import zipfile
import traceback
import pandas as pd
import qrcode
from PIL import Image
from fpdf2 import FPDF # <--- Importação correta forçada
from flask import Flask, render_template, request, send_file, url_for, abort

# Configurações do Flask
app = Flask(__name__)
# URL DE RASTREAMENTO: ATUALIZE SE O SEU DOMÍNIO MUDAR NO RENDER
BASE_URL_RASTREAMENTO = "https://pdf-rastreavel-app-1.onrender.com/rastrear/" 

# --- Função de Geração de PDF com QR Code ---

def gerar_pdf_com_qr(pdf, row_data, unique_id, rastreamento_url):
    """
    Gera o conteúdo de um PDF para uma linha de dados.
    Usa o objeto FPDF2 e dados já processados.
    """
    try:
        # 1. Criação do QR Code
        full_url = f"{rastreamento_url}{unique_id}"

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(full_url)
        qr.make(fit=True)
        
        # Cria a imagem do QR Code
        img_qr = qr.make_image(fill_color="black", back_color="white")
        
        # Salva a imagem em um buffer de memória (BytesIO)
        img_buffer = io.BytesIO()
        img_qr.save(img_buffer, format='PNG')
        img_buffer.seek(0)

        # 2. Configurações e Título do PDF
        pdf.add_page()
        pdf.set_font('Arial', 'B', 18)
        pdf.cell(0, 10, f'Documento Rastreável: {unique_id}', 0, 1, 'C') 
        pdf.ln(10) 
        
        # 3. Tabela de Dados (Campos da Planilha)
        pdf.set_font('Arial', 'B', 12)
        w_label = 75 
        w_value = 100
        
        # Acesso aos dados do dicionário (da linha do pandas)
        for key, value in row_data.items():
            # Exibe todos os dados, exceto a chave única
            if key.upper() != 'ID_UNICO':
                pdf.set_fill_color(240, 240, 240)
                pdf.cell(w_label, 8, f'{key.replace("_", " ").title()}:', 1, 0, 'L', True) 
                
                pdf.set_font('Arial', '', 12)
                pdf.set_fill_color(255, 255, 255)
                
                display_value = str(value) if pd.notna(value) else "N/A"
                pdf.cell(w_value, 8, display_value, 1, 1, 'L', True)
                pdf.set_font('Arial', 'B', 12)
                
        pdf.ln(15) 
        
        # 4. Inserção do QR Code
        qr_code_size_mm = 40
        x_pos = (pdf.w - qr_code_size_mm) / 2 # Centraliza o QR Code
        
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 5, "Use a câmera do seu celular para rastrear:", 0, 1, 'C')
        pdf.ln(2)
        
        pdf.image(img_buffer, x=x_pos, y=pdf.get_y(), w=qr_code_size_mm, h=qr_code_size_mm, type='PNG')
        pdf.ln(qr_code_size_mm + 5) 

        # 5. Nota de Rodapé
        pdf.set_font('Arial', 'I', 8)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 5, f'URL Única: {full_url}', 0, 1, 'C')
        pdf.set_text_color(0, 0, 0) # Volta ao preto

    except Exception as e:
        app.logger.error(f"Erro ao gerar PDF para ID {unique_id}: {e}")
        raise

# --- Rotas do Flask ---

@app.route('/')
def index():
    """Renderiza a página inicial com o formulário de upload."""
    return render_template('index.html')

@app.route('/rastrear/<unique_id>')
def rastrear_documento(unique_id):
    """Rota para simular o rastreamento (o QR Code aponta para aqui)."""
    return render_template('rastreamento.html', unique_id=unique_id)

@app.route('/upload', methods=['POST'])
def upload_file():
    """Processa o arquivo CSV/XLSX, gera PDFs e retorna um ZIP."""
    if 'file' not in request.files:
        return "Nenhum arquivo enviado.", 400

    file = request.files['file']

    if file.filename == '':
        return "Nenhum arquivo selecionado.", 400
    
    # Adicionando .xls para maior compatibilidade
    if not (file.filename.endswith('.csv') or file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        return "Formato de arquivo inválido. Use .csv ou .xlsx.", 400

    try:
        file_bytes = file.read()
        file_buffer = io.BytesIO(file_bytes)

        if file.filename.endswith('.csv'):
            try:
                # Tenta ler CSV com vírgula (sep=',')
                df = pd.read_csv(file_buffer, encoding='utf-8', sep=',')
            except Exception:
                # Tenta ler CSV com ponto e vírgula (sep=';') como fallback
                file_buffer.seek(0)
                df = pd.read_csv(file_buffer, encoding='utf-8', sep=';')
        
        elif file.filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file_buffer)

        if 'ID_UNICO' not in df.columns:
            return "A planilha deve conter uma coluna chamada 'ID_UNICO'.", 400

        df = df.dropna(subset=['ID_UNICO'])

        if len(df) == 0:
            return "Nenhuma linha válida encontrada para processamento após limpeza.", 400

        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for index, row in df.iterrows():
                unique_id = str(row['ID_UNICO']).strip()
                pdf = FPDF('P', 'mm', 'A4')
                
                try:
                    gerar_pdf_com_qr(pdf, row.to_dict(), unique_id, BASE_URL_RASTREAMENTO)
                    
                    pdf_buffer = io.BytesIO()
                    pdf.output(pdf_buffer)
                    pdf_buffer.seek(0)
                    
                    pdf_filename = f'{unique_id}.pdf'
                    zip_file.writestr(pdf_filename, pdf_buffer.read())

                except Exception as e:
                    error_msg = f"ERRO FATAL GERAÇÃO PDF NA LINHA {index + 1} (ID: {unique_id}): {traceback.format_exc()}"
                    app.logger.error(error_msg)
                    return f"Erro ao gerar PDF para a linha {index + 1} (ID: {unique_id}): {str(e)}", 500

        zip_buffer.seek(0)

        return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name='documentos_rastreaveis.zip')

    except Exception as e:
        app.logger.error(f"Erro inesperado no processamento: {traceback.format_exc()}")
        return f"Erro inesperado no servidor: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)
