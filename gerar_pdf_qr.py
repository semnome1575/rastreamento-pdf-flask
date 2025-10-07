# Importações para geração de PDF e QR Code
import io
import qrcode
import pandas as pd
from fpdf import FPDF 
from PIL import Image

# Configuração da URL base para o QR Code (Este valor será sobrescrito pelo app.py)
BASE_URL_RASTREAMENTO = "http://www.seu-dominio.com/rastrear/" 

def gerar_pdf_com_qr(dados_linha):
    """
    Gera um PDF contendo os dados de uma linha da planilha e um QR Code único.
    """
    # 1. Extração de Dados e Criação da URL Única
    documento_id = str(dados_linha.iloc[0]) 
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
    
    # --- Título ---
    pdf.set_font('Arial', 'B', 18)
    pdf.cell(0, 10, f'Documento: {documento_id}', 0, 1, 'C') 
    pdf.ln(10) 
    
    # --- Tabela de Dados ---
    pdf.set_font('Arial', 'B', 12)
    w_label = 75 
    w_value = 100
    
    for coluna, valor in zip(dados_linha.index, dados_linha.values):
        if coluna != dados_linha.index[0]:
            pdf.set_fill_color(240, 240, 240)
            pdf.cell(w_label, 8, f'{coluna}:', 1, 0, 'L', 1) 
            pdf.set_fill_color(255, 255, 255)
            pdf.set_font('Arial', '', 12)
            
            display_value = str(valor) if pd.notna(valor) else "N/A"
            pdf.cell(w_value, 8, display_value, 1, 1, 'L', 1)
            pdf.set_font('Arial', 'B', 12)
            
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
