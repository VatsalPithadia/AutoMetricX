import io
import os
import time
from typing import Dict, Any, List

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from PIL import Image as PILImage

class LMPCPdfReportGenerator:
    """
    ReportLab PDF Audit Certificate Generator for Legal Metrology AI Compliance.
    Includes embedded product label photo evidence and rule violation details.
    """

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._init_custom_styles()

    def _init_custom_styles(self):
        self.title_style = ParagraphStyle(
            'DocTitle',
            parent=self.styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=colors.HexColor('#0F172A'),
            alignment=TA_LEFT
        )
        self.subtitle_style = ParagraphStyle(
            'DocSubtitle',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#475569'),
            alignment=TA_LEFT
        )
        self.heading2_style = ParagraphStyle(
            'SectionHeading',
            parent=self.styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=12,
            leading=16,
            textColor=colors.HexColor('#0F172A'),
            spaceBefore=10,
            spaceAfter=6
        )
        self.body_style = ParagraphStyle(
            'CustomBody',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#334155')
        )
        self.table_header_style = ParagraphStyle(
            'TableHeader',
            parent=self.styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9,
            leading=11,
            textColor=colors.white,
            alignment=TA_LEFT
        )
        self.table_cell_style = ParagraphStyle(
            'TableCell',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor('#1E293B')
        )
        self.table_cell_bold = ParagraphStyle(
            'TableCellBold',
            parent=self.styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor('#0F172A')
        )

    def generate_pdf_bytes(self, scan_result: Dict[str, Any]) -> bytes:
        """
        Generates binary PDF report stream from API scan result payload with embedded label image.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        story: List[Any] = []

        filename = scan_result.get("filename", "label_photo.jpg")
        saved_file = scan_result.get("saved_file") or filename
        engine = scan_result.get("engine", "RapidOCR ONNX Engine")
        proc_time = scan_result.get("processing_time_seconds", 0.0)
        report = scan_result.get("compliance_report", {})
        overall_status = report.get("overall_status", "NON_COMPLIANT")
        score = report.get("compliance_score", 0.0)
        declarations = report.get("declarations", [])
        legibility = report.get("font_legibility_analysis", {})

        # Header Title Banner
        story.append(Paragraph("Auto MatriX Legal Metrology Inspection Certificate", self.title_style))
        story.append(Paragraph("Legal Metrology (Packaged Commodities) Rules Compliance Audit Report", self.subtitle_style))
        story.append(Spacer(1, 8))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0284C7'), spaceBefore=2, spaceAfter=8))

        # Embedded Product Label Evidence Photo
        img_path = None
        backend_dir = os.path.dirname(os.path.dirname(__file__))
        root_dir = os.path.dirname(backend_dir)
        uploads_dir = os.path.join(backend_dir, "uploads")
        test_images_dir = os.path.join(root_dir, "test_images")

        candidates = [
            saved_file if os.path.isabs(saved_file) else None,
            filename if os.path.isabs(filename) else None,
            os.path.join(uploads_dir, saved_file),
            os.path.join(uploads_dir, filename),
            os.path.join(test_images_dir, saved_file),
            os.path.join(test_images_dir, filename),
            os.path.join(root_dir, filename)
        ]

        for cand in candidates:
            if cand and os.path.exists(cand) and os.path.isfile(cand):
                img_path = cand
                break

        if img_path:
            try:
                with PILImage.open(img_path) as pimg:
                    pw, ph = pimg.size
                    max_w = 220.0  # max width ~3 inches
                    scale_ratio = max_w / float(pw)
                    rl_w = max_w
                    rl_h = ph * scale_ratio
                    if rl_h > 160.0:  # cap height
                        rl_h = 160.0
                        rl_w = pw * (160.0 / float(ph))
                    
                    rl_img = RLImage(img_path, width=rl_w, height=rl_h)
                    rl_img.hAlign = 'CENTER'
                    story.append(Paragraph("<b>Scanned Product Label Photo Evidence:</b>", self.body_style))
                    story.append(Spacer(1, 4))
                    story.append(rl_img)
                    story.append(Spacer(1, 8))
            except Exception as img_err:
                pass

        # Executive Summary Audit Card Table
        status_color_bg = colors.HexColor('#DCFCE7') if overall_status == 'COMPLIANT' else (
            colors.HexColor('#FEF3C7') if overall_status == 'PARTIALLY_COMPLIANT' else colors.HexColor('#FEE2E2')
        )
        status_color_fg = colors.HexColor('#15803D') if overall_status == 'COMPLIANT' else (
            colors.HexColor('#B45309') if overall_status == 'PARTIALLY_COMPLIANT' else colors.HexColor('#B91C1C')
        )

        summary_data = [
            [
                Paragraph("<b>Audit Package File:</b> " + filename, self.body_style),
                Paragraph("<b>Overall Status:</b>", self.body_style),
                Paragraph(f"<b>{overall_status}</b>", ParagraphStyle('StatusBadge', parent=self.body_style, fontName='Helvetica-Bold', textColor=status_color_fg, alignment=TA_CENTER))
            ],
            [
                Paragraph(f"<b>OCR Engine:</b> {engine}", self.body_style),
                Paragraph("<b>Audit Compliance Score:</b>", self.body_style),
                Paragraph(f"<b>{score}%</b>", ParagraphStyle('ScorePill', parent=self.body_style, fontName='Helvetica-Bold', fontSize=12, textColor=colors.HexColor('#0284C7'), alignment=TA_CENTER))
            ],
            [
                Paragraph(f"<b>Latency:</b> {proc_time}s &bull; <b>OCR Regions:</b> {scan_result.get('total_blocks', 0)}", self.body_style),
                Paragraph("<b>Rules Passed:</b>", self.body_style),
                Paragraph(f"<b>{report.get('passed_rules_count', 0)} / {report.get('total_rules_checked', 8)} Rules</b>", self.body_style)
            ]
        ]

        summary_table = Table(summary_data, colWidths=[240, 150, 150])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#E2E8F0')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('BACKGROUND', (2, 0), (2, 0), status_color_bg),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 10))

        # Section 1: Rule 6(1) Mandatory Declarations Table
        story.append(Paragraph("1. Mandatory Legal Metrology Rule 6(1) Declaration Audit", self.heading2_style))
        
        decl_headers = [
            Paragraph("<b>Clause</b>", self.table_header_style),
            Paragraph("<b>Declaration Name</b>", self.table_header_style),
            Paragraph("<b>Status</b>", self.table_header_style),
            Paragraph("<b>Detected Label Text</b>", self.table_header_style),
            Paragraph("<b>Legal Compliance Findings</b>", self.table_header_style)
        ]
        
        decl_rows = [decl_headers]
        for decl in declarations:
            st = decl.get("status", "FAIL")
            st_text = "PASS" if st == "PASS" else ("LOW CONF" if st == "LOW_CONFIDENCE" else "FAIL")
            st_fg = colors.HexColor('#166534') if st == 'PASS' else (colors.HexColor('#92400E') if st == 'LOW_CONFIDENCE' else colors.HexColor('#991B1B'))

            decl_rows.append([
                Paragraph(decl.get("clause", ""), self.table_cell_bold),
                Paragraph(decl.get("name", ""), self.table_cell_bold),
                Paragraph(f"<b>{st_text}</b>", ParagraphStyle('StCell', parent=self.table_cell_bold, textColor=st_fg, alignment=TA_CENTER)),
                Paragraph(decl.get("found_value") or "<i>Not Found</i>", self.table_cell_style),
                Paragraph(decl.get("explanation", ""), self.table_cell_style)
            ])

        decl_table = Table(decl_rows, colWidths=[65, 110, 60, 135, 170])
        decl_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('PADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(decl_table)
        story.append(Spacer(1, 10))

        # Section 2: Physical Font-Size & MRP Prominence Table
        if legibility:
            story.append(Paragraph("2. Physical Font-Size Calibration & Visual Prominence Analysis (Rule 7 & 9)", self.heading2_style))
            
            leg_meta = f"Calibration Scale: <b>{legibility.get('scale_px_mm', 16.0)} px/mm</b> ({legibility.get('scale_calibration_source', 'Default')}) &bull; Weight Tier: <b>{legibility.get('rule_7_3_tier', 'Tier <= 50g')}</b>"
            story.append(Paragraph(leg_meta, self.body_style))
            story.append(Spacer(1, 4))

            font_headers = [
                Paragraph("<b>Declaration Field</b>", self.table_header_style),
                Paragraph("<b>Measured Font (mm)</b>", self.table_header_style),
                Paragraph("<b>Required Min (mm)</b>", self.table_header_style),
                Paragraph("<b>Rule 7(3) Status</b>", self.table_header_style)
            ]
            font_rows = [font_headers]

            min_req = legibility.get("min_required_letter_height_mm", 1.0)
            field_evals = legibility.get("rule_7_3_field_evaluations", [])

            for fe in field_evals:
                st = fe.get("status", "PASS")
                st_fg = colors.HexColor('#166534') if st == 'PASS' else colors.HexColor('#92400E')
                font_rows.append([
                    Paragraph(fe.get("field", "").replace("_", " ").title(), self.table_cell_bold),
                    Paragraph(f"{fe.get('font_height_mm', 0)} mm", self.table_cell_style),
                    Paragraph(f"{min_req} mm", self.table_cell_style),
                    Paragraph(f"<b>{st}</b>", ParagraphStyle('FntSt', parent=self.table_cell_bold, textColor=st_fg, alignment=TA_CENTER))
                ])

            font_table = Table(font_rows, colWidths=[160, 130, 130, 120])
            font_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
                ('PADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(font_table)
            story.append(Spacer(1, 8))

            r9_1 = legibility.get("rule_9_1_mrp_prominence", {})
            r9_p_ratio = r9_1.get("prominence_ratio", 1.0)
            r9_expl = r9_1.get("explanation", "")
            story.append(Paragraph(f"<b>Rule 9(1) MRP Prominence Ratio:</b> {r9_p_ratio}x. {r9_expl}", self.body_style))
            story.append(Spacer(1, 10))

        # Section 3: Ingredient Safety & Hazard Verification
        ing_safety = scan_result.get("ingredient_safety")
        if ing_safety and ing_safety.get("has_ingredients"):
            story.append(Paragraph("3. Product Ingredient Safety & Hazard Verification", self.heading2_style))
            
            verdict = ing_safety.get("safety_verdict", "SAFE")
            score_val = ing_safety.get("safety_score", 100)
            summary_txt = ing_safety.get("summary", "")
            
            v_fg = colors.HexColor('#166534') if verdict == 'SAFE' else (colors.HexColor('#92400E') if verdict == 'CAUTION' else colors.HexColor('#991B1B'))
            v_bg = colors.HexColor('#DCFCE7') if verdict == 'SAFE' else (colors.HexColor('#FEF3C7') if verdict == 'CAUTION' else colors.HexColor('#FEE2E2'))

            ing_meta_data = [
                [
                    Paragraph(f"<b>Safety Verdict:</b> <font color='{v_fg.hexval()}'><b>{verdict}</b></font>", self.body_style),
                    Paragraph(f"<b>Health Safety Score:</b> <b>{score_val} / 100</b>", self.body_style),
                    Paragraph(f"<b>Total Ingredients:</b> {ing_safety.get('total_ingredients_count', 0)} ({ing_safety.get('harmful_count', 0)} Harmful, {ing_safety.get('caution_count', 0)} Caution)", self.body_style)
                ]
            ]
            ing_meta_table = Table(ing_meta_data, colWidths=[180, 160, 200])
            ing_meta_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), v_bg),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOX', (0, 0), (-1, -1), 1, v_fg),
                ('PADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(ing_meta_table)
            story.append(Spacer(1, 4))
            story.append(Paragraph(f"<b>Safety Summary:</b> {summary_txt}", self.body_style))
            story.append(Spacer(1, 6))

            flagged = ing_safety.get("flagged_ingredients", [])
            if flagged:
                ing_headers = [
                    Paragraph("<b>Harmful Ingredient</b>", self.table_header_style),
                    Paragraph("<b>Severity</b>", self.table_header_style),
                    Paragraph("<b>Hazard Classification</b>", self.table_header_style),
                    Paragraph("<b>Regulatory Status & Health Impact</b>", self.table_header_style)
                ]
                ing_rows = [ing_headers]
                for f in flagged:
                    sev = f.get("severity", "MODERATE")
                    s_color = colors.HexColor('#991B1B') if sev == 'HIGH' else colors.HexColor('#92400E')
                    ing_rows.append([
                        Paragraph(f"<b>{f.get('name', '')}</b><br/><font size=7 color='#64748B'>{f.get('ins_code', '')}</font>", self.table_cell_bold),
                        Paragraph(f"<b>{sev}</b>", ParagraphStyle('SevCell', parent=self.table_cell_bold, textColor=s_color, alignment=TA_CENTER)),
                        Paragraph(f.get("hazard_type", ""), self.table_cell_style),
                        Paragraph(f"<b>{f.get('regulatory_status', '')}:</b> {f.get('risk_explanation', '')}", self.table_cell_style)
                    ])
                ing_table = Table(ing_rows, colWidths=[130, 60, 140, 210])
                ing_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#334155')),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
                    ('PADDING', (0, 0), (-1, -1), 3),
                ]))
                story.append(ing_table)
                story.append(Spacer(1, 8))

        # Section 4: Actionable Remediation Guidance & Inspector Signature Box
        story.append(Paragraph("4. Remediation & Officer Certification", self.heading2_style))
        remediation_items = []
        for decl in declarations:
            if decl.get("status") != "PASS":
                remediation_items.append(f"• <b>{decl.get('name')}:</b> {decl.get('explanation')}")

        if not remediation_items:
            remediation_text = "<b>COMPLIANCE VERIFIED:</b> All mandatory Legal Metrology (Packaged Commodities) Rules, 2011 declarations are present and compliant."
        else:
            remediation_text = "<br/>".join(remediation_items)

        story.append(Paragraph(remediation_text, self.body_style))
        story.append(Spacer(1, 14))

        sig_data = [
            [
                Paragraph("<b>Inspecting Legal Metrology Officer:</b> _____________________", self.body_style),
                Paragraph(f"<b>Audit Date:</b> {time.strftime('%Y-%m-%d %H:%M:%S')}", self.body_style),
                Paragraph("<b>Official Stamp:</b> [ METROLENS CERTIFIED ]", ParagraphStyle('StampText', parent=self.body_style, fontName='Helvetica-Bold', textColor=colors.HexColor('#0284C7'), alignment=TA_RIGHT))
            ]
        ]
        sig_table = Table(sig_data, colWidths=[220, 160, 160])
        sig_table.setStyle(TableStyle([
            ('LINEABOVE', (0, 0), (-1, 0), 1, colors.HexColor('#94A3B8')),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(KeepTogether([sig_table]))

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
