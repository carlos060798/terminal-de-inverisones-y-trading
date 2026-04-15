"""
services/report_generator.py - Professional PDF Report Generation Service (ULTRA Edition)
Uses fpdf2 to create institutional-grade weekly performance reports.
"""
from fpdf import FPDF
from datetime import datetime
import io

class QuantumReport(FPDF):
    def header(self):
        # Logo placeholder or stylized text
        self.set_font('helvetica', 'B', 20)
        self.set_text_color(37, 99, 235) # Blue-600
        self.cell(0, 10, 'QUANTUM RETAIL TERMINAL - PRO', ln=True, align='L')
        
        self.set_font('helvetica', 'I', 10)
        self.set_text_color(100, 116, 139)
        self.cell(0, 10, f'Weekly Institutional Intelligence Report - {datetime.now().strftime("%d %b, %Y")}', ln=True, align='L')
        self.ln(5)
        
        # Border line
        self.set_draw_color(226, 232, 240)
        self.line(10, 32, 200, 32)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(148, 163, 184)
        self.cell(0, 10, f'Página {self.page_no()} | Quantum Terminal - Confidential Institutional Audit', align='C')

def generate_weekly_report(data):
    """
    Generates a PDF bytes object for the weekly report.
    data: dict containing totals, risk score, forensics, and stress tests.
    """
    pdf = QuantumReport()
    pdf.add_page()
    
    # --- SECTION 1: Executive Summary ---
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 10, '1. RESUMEN EJECUTIVO DE CARTERA', ln=True)
    pdf.ln(2)
    
    # Table-like summary
    pdf.set_font('helvetica', '', 11)
    pdf.set_fill_color(248, 250, 252)
    
    col_width = 90
    pdf.cell(col_width, 8, f' Valor Total AUM:', border=0, fill=True)
    pdf.set_font('helvetica', 'B', 11)
    pdf.cell(col_width, 8, f'${data["total_val"]:,.2f}', border=0, ln=True, fill=True)
    
    pdf.set_font('helvetica', '', 11)
    pdf.cell(col_width, 8, f' P&L Consolidado:', border=0)
    pdf.set_font('helvetica', 'B', 11)
    color = (16, 185, 129) if data["total_pnl"] >= 0 else (239, 68, 68)
    pdf.set_text_color(*color)
    pdf.cell(col_width, 8, f'${data["total_pnl"]:,.2f} ({data["pct_total"]:+.2f}%)', border=0, ln=True)
    
    pdf.set_text_color(30, 41, 59)
    pdf.set_font('helvetica', '', 11)
    pdf.cell(col_width, 8, f' Posiciones Activas:', border=0, fill=True)
    pdf.set_font('helvetica', 'B', 11)
    pdf.cell(col_width, 8, str(data["n_positions"]), border=0, ln=True, fill=True)
    
    pdf.ln(8)
    
    # --- SECTION 2: MACRO STRESS TEST (PHASE 11 INTEGRATION) ---
    pdf.set_font('helvetica', 'B', 14)
    pdf.cell(0, 10, '2. MACRO STRESS TEST (SHOCK SIMULATION)', ln=True)
    pdf.ln(3)
    
    stress = data.get("stress_results", {}).get("scenarios", {})
    if stress:
        pdf.set_font('helvetica', '', 10)
        for name, s_data in stress.items():
            pdf.set_text_color(71, 85, 105)
            pdf.cell(50, 8, f"{name}:", border=0)
            
            # Stylized label
            impact = s_data["impact_label"]
            pdf.set_font('helvetica', 'B', 10)
            label_color = (239, 68, 68) if impact == "CRÍTICO" else (16, 185, 129) if impact == "BAJO" else (245, 158, 11)
            pdf.set_text_color(*label_color)
            pdf.cell(40, 8, f"[{impact}]", ln=True)
            pdf.set_font('helvetica', '', 10)
    else:
        pdf.cell(0, 8, 'No se encontraron datos de simulación macro.', ln=True)
    
    pdf.ln(5)

    # --- SECTION 3: FORENSIC AUDIT SUMMARY (PHASE 10/12) ---
    pdf.set_text_color(30, 41, 59)
    pdf.set_font('helvetica', 'B', 14)
    pdf.cell(0, 10, '3. AUDITORIA FORENSE Y SALUD CORPORATIVA', ln=True)
    pdf.ln(3)
    
    forensics = data.get("forensics", [])
    if forensics:
        pdf.set_font('helvetica', 'B', 9)
        pdf.set_fill_color(30, 41, 59)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(20, 8, ' Ticker', border=1, fill=True)
        pdf.cell(30, 8, ' M-Score', border=1, fill=True)
        pdf.cell(30, 8, ' Sloan', border=1, fill=True)
        pdf.cell(40, 8, ' Merton PD', border=1, fill=True)
        pdf.cell(70, 8, ' Auditor Intelligence', border=1, fill=True, ln=True)
        
        pdf.set_text_color(30, 41, 59)
        pdf.set_font('helvetica', '', 8)
        for f in forensics[:10]:
            pdf.cell(20, 7, f' {f["Ticker"]}', border=1)
            pdf.cell(30, 7, f' {f["M-Score"]:.2f}', border=1)
            pdf.cell(30, 7, f' {f["Sloan"]:.1f}%', border=1)
            pdf.cell(40, 7, f' {f["Merton PD"]*100:.2f}%', border=1)
            pdf.cell(70, 7, f' {f["Status"]}', border=1, ln=True)
    else:
        pdf.cell(0, 8, 'Información forense no disponible.', ln=True)

    pdf.ln(8)
    
    # --- SECTION 4: POSITIONS DETAIL ---
    pdf.set_font('helvetica', 'B', 14)
    pdf.cell(0, 10, '4. COMPOSICIÓN DE ACTIVOS DETALLADA', ln=True)
    pdf.ln(3)
    
    pdf.set_font('helvetica', 'B', 9)
    pdf.set_fill_color(15, 23, 42)
    pdf.set_text_color(255, 255, 255)
    
    pdf.cell(20, 8, ' Ticker', border=1, fill=True)
    pdf.cell(45, 8, ' Sector', border=1, fill=True)
    pdf.cell(35, 8, ' Valor ($)', border=1, fill=True)
    pdf.cell(30, 8, ' P&L (%)', border=1, fill=True)
    pdf.cell(30, 8, ' Beta', border=1, fill=True)
    pdf.cell(30, 8, ' Peso (%)', border=1, fill=True, ln=True)
    
    pdf.set_font('helvetica', '', 8)
    pdf.set_text_color(30, 41, 59)
    for pos in data["positions"][:20]:
        pdf.cell(20, 7, f' {pos["Ticker"]}', border=1)
        pdf.cell(45, 7, f' {pos["Sector"][:22]}', border=1)
        pdf.cell(35, 7, f' ${pos["Value"]:,.2f}', border=1)
        
        pnl_val = pos.get("P&L %", 0)
        pnl_color = (16, 185, 129) if pnl_val >= 0 else (239, 68, 68)
        pdf.set_text_color(*pnl_color)
        pdf.cell(30, 7, f' {pnl_val:+.2f}%', border=1)
        
        pdf.set_text_color(30, 41, 59)
        pdf.cell(30, 7, f' {pos.get("Beta", 1.0):.2f}', border=1)
        pdf.cell(30, 7, f' {pos.get("Weight %", 0):.1f}%', border=1, ln=True)
        
    pdf.ln(10)
    pdf.set_font('helvetica', 'I', 8)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(0, 10, 'Confidencial - Quantum Terminal Institutional Edition. Prohibida su reproducción.', align='C')

    return pdf.output()
