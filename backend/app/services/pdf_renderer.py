"""
PDF Renderer Engine for ResumeIQ

Provides a modular, extensible PDF template rendering framework using ReportLab.
Renders native vector text in a single-column, highly machine-readable ATS format.
"""

import io
import html
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    HRFlowable,
    KeepTogether,
)


class ResumeViewModel(BaseModel):
    """Normalized View Model representation of targeted candidate evidence for rendering."""
    full_name: str = ""
    headline: str = ""
    contact_line: str = ""
    summary: str = ""
    experience: List[Dict[str, Any]] = Field(default_factory=list)
    projects: List[Dict[str, Any]] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    education: List[Dict[str, Any]] = Field(default_factory=list)
    certifications: List[Dict[str, Any]] = Field(default_factory=list)
    achievements: List[Dict[str, Any]] = Field(default_factory=list)
    target_role: str = ""
    target_company: str = ""

    model_config = ConfigDict(populate_by_name=True)


class BasePdfRenderer(ABC):
    """Abstract Base Class for ResumeIQ PDF template renderers."""

    @abstractmethod
    def render(self, vm: ResumeViewModel) -> bytes:
        """Renders the ResumeViewModel into native PDF binary bytes."""
        pass


def _clean_pdf_text(val: Optional[str]) -> str:
    """Escapes special characters for ReportLab XML/Paragraph markup safely."""
    if not val:
        return ""
    # Sanitize HTML tags and XML entities
    text = str(val).strip()
    return html.escape(text, quote=True)


class AtsTemplateRenderer(BasePdfRenderer):
    """
    Standard ATS-optimized single-column PDF renderer.
    Renders native vector text layer, 0.5" margins, clean hierarchy,
    standard Helvetica typography, and zero graphic elements that obstruct ATS parsing.
    """

    def render(self, vm: ResumeViewModel) -> bytes:
        buffer = io.BytesIO()

        # Page setup: Letter size with 0.5" margins (36 points)
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()

        # Custom ATS Typography Styles (Helvetica / Helvetica-Bold)
        name_style = ParagraphStyle(
            "AtsName",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#111827"),
            alignment=0,
        )

        headline_style = ParagraphStyle(
            "AtsHeadline",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#374151"),
            alignment=0,
        )

        contact_style = ParagraphStyle(
            "AtsContact",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#4B5563"),
            alignment=0,
        )

        section_heading_style = ParagraphStyle(
            "AtsSectionHeading",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#111827"),
            spaceBefore=8,
            spaceAfter=4,
        )

        item_title_style = ParagraphStyle(
            "AtsItemTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#1F2937"),
        )

        item_subtitle_style = ParagraphStyle(
            "AtsItemSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#4B5563"),
        )

        body_style = ParagraphStyle(
            "AtsBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#1F2937"),
        )

        bullet_style = ParagraphStyle(
            "AtsBullet",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#1F2937"),
            leftIndent=14,
            firstLineIndent=-10,
            spaceAfter=2,
        )

        story = []

        # 1. Header (Name, Headline, Contact Info)
        candidate_name = _clean_pdf_text(vm.full_name) or "Candidate Name"
        story.append(Paragraph(candidate_name, name_style))

        if vm.headline or vm.target_role:
            role_line = _clean_pdf_text(vm.headline or vm.target_role)
            if vm.target_company:
                role_line += f" &mdash; {_clean_pdf_text(vm.target_company)}"
            story.append(Spacer(1, 2))
            story.append(Paragraph(role_line, headline_style))

        if vm.contact_line:
            story.append(Spacer(1, 3))
            story.append(Paragraph(_clean_pdf_text(vm.contact_line), contact_style))

        story.append(Spacer(1, 6))
        story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#D1D5DB"), spaceBefore=2, spaceAfter=8))

        # 2. Professional Summary
        if vm.summary:
            story.append(Paragraph("PROFESSIONAL SUMMARY", section_heading_style))
            story.append(Paragraph(_clean_pdf_text(vm.summary), body_style))
            story.append(Spacer(1, 8))

        # 3. Professional Experience
        if vm.experience:
            story.append(Paragraph("PROFESSIONAL EXPERIENCE", section_heading_style))
            for exp in vm.experience:
                exp_elements = []
                role_company = f"<b>{_clean_pdf_text(exp.get('role', ''))}</b> &mdash; {_clean_pdf_text(exp.get('company', ''))}"
                date_str = _clean_pdf_text(exp.get("date_range", ""))
                if date_str:
                    role_company += f" <font color='#6B7280'>({date_str})</font>"

                exp_elements.append(Paragraph(role_company, item_title_style))

                if exp.get("location"):
                    exp_elements.append(Paragraph(_clean_pdf_text(exp["location"]), item_subtitle_style))

                for bullet in exp.get("bullets", []):
                    clean_b = _clean_pdf_text(bullet)
                    if clean_b:
                        exp_elements.append(Paragraph(f"&bull; {clean_b}", bullet_style))

                exp_elements.append(Spacer(1, 6))
                story.append(KeepTogether(exp_elements))

            story.append(Spacer(1, 4))

        # 4. Key Projects
        if vm.projects:
            story.append(Paragraph("KEY PROJECTS", section_heading_style))
            for proj in vm.projects:
                proj_elements = []
                title_line = f"<b>{_clean_pdf_text(proj.get('title', ''))}</b>"
                if proj.get("role"):
                    title_line += f" <font color='#6B7280'>({_clean_pdf_text(proj['role'])})</font>"
                proj_elements.append(Paragraph(title_line, item_title_style))

                if proj.get("description"):
                    proj_elements.append(Paragraph(_clean_pdf_text(proj["description"]), body_style))

                for hl in proj.get("highlights", []):
                    clean_hl = _clean_pdf_text(hl)
                    if clean_hl:
                        proj_elements.append(Paragraph(f"&bull; {clean_hl}", bullet_style))

                proj_elements.append(Spacer(1, 5))
                story.append(KeepTogether(proj_elements))

            story.append(Spacer(1, 4))

        # 5. Technical Skills
        if vm.skills:
            story.append(Paragraph("TECHNICAL SKILLS", section_heading_style))
            skills_str = ", ".join([_clean_pdf_text(s) for s in vm.skills if s])
            story.append(Paragraph(skills_str, body_style))
            story.append(Spacer(1, 8))

        # 6. Education
        if vm.education:
            story.append(Paragraph("EDUCATION", section_heading_style))
            for edu in vm.education:
                degree_inst = f"<b>{_clean_pdf_text(edu.get('degree', ''))}</b> &mdash; {_clean_pdf_text(edu.get('institution', ''))}"
                if edu.get("fieldOfStudy"):
                    degree_inst += f" ({_clean_pdf_text(edu['fieldOfStudy'])})"
                story.append(Paragraph(degree_inst, body_style))
                story.append(Spacer(1, 3))

            story.append(Spacer(1, 5))

        # 7. Certifications
        if vm.certifications:
            story.append(Paragraph("CERTIFICATIONS", section_heading_style))
            for cert in vm.certifications:
                cert_line = f"<b>{_clean_pdf_text(cert.get('title', ''))}</b>"
                if cert.get("issuer"):
                    cert_line += f" &mdash; {_clean_pdf_text(cert['issuer'])}"
                story.append(Paragraph(cert_line, body_style))
                story.append(Spacer(1, 3))
            story.append(Spacer(1, 5))

        # 8. Honors & Achievements
        if vm.achievements:
            story.append(Paragraph("HONORS & ACHIEVEMENTS", section_heading_style))
            for ach in vm.achievements:
                ach_elements = []
                ach_title = f"<b>{_clean_pdf_text(ach.get('title', ''))}</b>"
                if ach.get("issuer"):
                    ach_title += f" &mdash; {_clean_pdf_text(ach['issuer'])}"
                if ach.get("date"):
                    ach_title += f" <font color='#6B7280'>({_clean_pdf_text(ach['date'])})</font>"
                ach_elements.append(Paragraph(ach_title, item_title_style))

                if ach.get("description"):
                    ach_elements.append(Paragraph(_clean_pdf_text(ach["description"]), body_style))

                ach_elements.append(Spacer(1, 4))
                story.append(KeepTogether(ach_elements))

        # Build document
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
