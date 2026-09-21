import os
import logging
import docx
import pymupdf as fitz
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

logger = logging.getLogger(__name__)


class ResumeGenerator:
    """
    Generates structured ATS-friendly DOCX and PDF resumes for tailored job applications.
    """
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_docx(self, candidate_name: str, contact_info: dict, summary: str, skills: list, experience: list, education: list) -> str:
        doc = docx.Document()

        # Set normal margins
        sections = doc.sections
        for section in sections:
            section.top_margin = Inches(0.6)
            section.bottom_margin = Inches(0.6)
            section.left_margin = Inches(0.6)
            section.right_margin = Inches(0.6)

        # Header Name
        title_p = doc.add_paragraph()
        title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = title_p.add_run(candidate_name)
        run.bold = True
        run.font.size = Pt(20)
        run.font.name = "Arial"
        run.font.color.rgb = RGBColor(0x11, 0x18, 0x27)

        # Contact line
        contact_p = doc.add_paragraph()
        contact_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        contact_str = f"{contact_info.get('email', '')} | {contact_info.get('phone', '')} | {contact_info.get('location', 'Hyderabad, India')}"
        c_run = contact_p.add_run(contact_str)
        c_run.font.size = Pt(9.5)
        c_run.font.name = "Arial"
        c_run.font.color.rgb = RGBColor(0x4B, 0x55, 0x63)

        # Helper for Heading
        def add_heading(text: str):
            h_p = doc.add_paragraph()
            h_p.paragraph_format.space_before = Pt(12)
            h_p.paragraph_format.space_after = Pt(4)
            h_run = h_p.add_run(text.upper())
            h_run.bold = True
            h_run.font.size = Pt(11)
            h_run.font.name = "Arial"
            h_run.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)

        # Professional Summary
        add_heading("Professional Summary")
        sum_p = doc.add_paragraph()
        s_run = sum_p.add_run(summary)
        s_run.font.size = Pt(10)
        s_run.font.name = "Arial"

        # Core Technical Skills
        add_heading("Core Technical Skills")
        skills_p = doc.add_paragraph()
        sk_run = skills_p.add_run(" • ".join(skills))
        sk_run.font.size = Pt(10)
        sk_run.font.name = "Arial"
        sk_run.bold = True

        # Professional Experience / Projects
        add_heading("Professional Experience & Projects")
        for exp in experience:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(2)
            title_run = p.add_run(f"{exp.get('title', 'QA Engineer')} — {exp.get('company', 'NurseIO / Healthcare Project')}")
            title_run.bold = True
            title_run.font.size = Pt(10.5)
            title_run.font.name = "Arial"

            for detail in exp.get("details", []):
                bp = doc.add_paragraph(style="List Bullet")
                bp.paragraph_format.space_after = Pt(2)
                b_run = bp.add_run(detail)
                b_run.font.size = Pt(9.5)
                b_run.font.name = "Arial"

        # Education
        add_heading("Education")
        for edu in education:
            ep = doc.add_paragraph()
            if isinstance(edu, dict):
                edu_text = f"{edu.get('degree', 'Bachelor Degree')} — {edu.get('field', 'Computer Science / Engineering')}"
            else:
                edu_text = str(edu)
            e_run = ep.add_run(edu_text)
            e_run.font.size = Pt(10)
            e_run.font.name = "Arial"

        docx_path = os.path.join(self.output_dir, "resume.docx")
        doc.save(docx_path)
        logger.info(f"Generated DOCX resume: {docx_path}")
        return docx_path

    def generate_pdf_from_docx(self, docx_path: str) -> str:
        pdf_path = os.path.join(self.output_dir, "resume.pdf")
        # Try docx2pdf if available on Windows, else fallback to copy/convert placeholder
        try:
            from docx2pdf import convert
            convert(docx_path, pdf_path)
            logger.info(f"Converted DOCX to PDF via docx2pdf: {pdf_path}")
        except Exception:
            # Simple text rendering fallback using PyMuPDF if docx2pdf fails
            doc = docx.Document(docx_path)
            text_lines = [p.text for p in doc.paragraphs if p.text]

            fitz_doc = fitz.open()
            page = fitz_doc.new_page()
            y_pos = 50
            for line in text_lines:
                page.insert_text((40, y_pos), line[:100], fontsize=10)
                y_pos += 15
                if y_pos > 750:
                    page = fitz_doc.new_page()
                    y_pos = 50
            fitz_doc.save(pdf_path)
            fitz_doc.close()
            logger.info(f"Generated PDF resume fallback: {pdf_path}")

        return pdf_path
