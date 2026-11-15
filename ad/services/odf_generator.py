from odf.opendocument import OpenDocumentText
from odf.style import (Style, TableProperties, TableColumnProperties,
                       TableCellProperties, TextProperties,
                       ParagraphProperties)
from odf.table import Table, TableColumn, TableRow, TableCell
from odf.text import P


class ODTBuilder:
    """Construit un document ODT avec des tableaux stylés (style AIP)."""

    def __init__(self):
        self.doc = OpenDocumentText()
        self._setup_styles()
        self._col_widths_cache = {}

    # ------------------------------------------------------------------ styles
    def _setup_styles(self):
        # Standard paragraph
        text_style = Style(name="Standard", family="paragraph")
        text_style.addElement(TextProperties(fontsize="8pt", fontfamily="Arial"))
        text_style.addElement(ParagraphProperties(marginbottom="0.05cm",
                                                  margintop="0cm"))
        self.doc.styles.addElement(text_style)

        # Section heading
        h_style = Style(name="SectionHeading", family="paragraph")
        h_style.addElement(TextProperties(fontsize="9pt", fontfamily="Arial",
                                          fontweight="bold"))
        h_style.addElement(ParagraphProperties(margintop="0.3cm",
                                               marginbottom="0.1cm",
                                               textalign="center"))
        self.doc.styles.addElement(h_style)

        # Sub-heading (AD 2.10)
        sub_style = Style(name="SubHeading", family="paragraph")
        sub_style.addElement(TextProperties(fontsize="8pt", fontfamily="Arial",
                                            fontweight="bold", fontstyle="italic"))
        sub_style.addElement(ParagraphProperties(margintop="0.15cm",
                                                 marginbottom="0.05cm"))
        self.doc.styles.addElement(sub_style)

        # Bold text (table headers, titles)
        bold_style = Style(name="BoldCell", family="paragraph")
        bold_style.addElement(TextProperties(fontsize="8pt", fontfamily="Arial",
                                             fontweight="bold"))
        bold_style.addElement(ParagraphProperties(marginbottom="0cm",
                                                  margintop="0cm"))
        self.doc.styles.addElement(bold_style)

        # Centered bold (AD 2.1 box)
        center_bold = Style(name="CenterBold", family="paragraph")
        center_bold.addElement(TextProperties(fontsize="9pt", fontfamily="Arial",
                                              fontweight="bold"))
        center_bold.addElement(ParagraphProperties(textalign="center",
                                                   marginbottom="0cm",
                                                   margintop="0cm"))
        self.doc.styles.addElement(center_bold)

        # Table
        table_style = Style(name="TableGrid", family="table")
        table_style.addElement(TableProperties(align="margins", width="100%"))
        self.doc.automaticstyles.addElement(table_style)

        # Cell with border
        cell_style = Style(name="CellBorder", family="table-cell")
        cell_style.addElement(TableCellProperties(
            border="0.5pt solid #000000",
            padding="0.05cm",
            verticalalign="top"
        ))
        self.doc.automaticstyles.addElement(cell_style)

    def _get_column_style(self, width):
        width = str(width)
        if width in self._col_widths_cache:
            return self._col_widths_cache[width]
        style_name = f"Col_{width.replace('.', '_').replace('cm', '')}"
        col_style = Style(name=style_name, family="table-column")
        col_style.addElement(TableColumnProperties(columnwidth=width))
        self.doc.automaticstyles.addElement(col_style)
        self._col_widths_cache[width] = style_name
        return style_name

    # ------------------------------------------------------------------ blocks
    def add_heading(self, text):
        p = P(stylename="SectionHeading")
        p.addText(text.upper())
        self.doc.text.addElement(p)

    def add_subheading(self, text):
        p = P(stylename="SubHeading")
        p.addText(text)
        self.doc.text.addElement(p)

    def add_text_block(self, title, content):
        p = P(stylename="SectionHeading")
        p.addText(title.upper())
        self.doc.text.addElement(p)
        body = P(stylename="Standard")
        body.addText(content or "NIL")
        self.doc.text.addElement(body)

    def add_title_box(self, text):
        """Boîte simple 1 cellule avec texte centré gras (AD 2.1)."""
        table = Table(name="TitleBox", stylename="TableGrid")
        table.addElement(TableColumn(stylename=self._get_column_style("21cm")))
        tr = TableRow()
        cell = TableCell(stylename="CellBorder", valuetype="string")
        cell.addElement(P(text=text, stylename="CenterBold"))
        tr.addElement(cell)
        table.addElement(tr)
        self.doc.text.addElement(table)

    # ------------------------------------------------------------------ tables
    def _build_table(self, title_or_none, widths, headers_or_none, rows):
        """Constructeur générique de tableau."""
        if title_or_none:
            self.add_heading(title_or_none)

        table = Table(name="T", stylename="TableGrid")

        for w in widths:
            col_style = self._get_column_style(w)
            table.addElement(TableColumn(stylename=col_style))

        # En-tête
        if headers_or_none:
            tr = TableRow()
            for h in headers_or_none:
                cell = TableCell(stylename="CellBorder", valuetype="string")
                cell.addElement(P(text=h, stylename="BoldCell"))
                tr.addElement(cell)
            table.addElement(tr)

        # Données
        for row_data in rows:
            tr = TableRow()
            for val in row_data:
                cell = TableCell(stylename="CellBorder", valuetype="string")
                text = str(val) if val not in (None, "") else ""
                # Split sur les retours à la ligne → plusieurs paragraphes
                lines = text.split("\n") if text else [""]
                for line in lines:
                    cell.addElement(P(text=line, stylename="Standard"))
                tr.addElement(cell)
            table.addElement(tr)

        self.doc.text.addElement(table)

    def add_key_value_table(self, title, rows):
        """Tableau 3 colonnes : num, label, value."""
        data = [[r.get("num", ""), r.get("label", ""), r.get("value", "")]
                for r in rows]
        self._build_table(title, ["0.8cm", "5cm", "11.2cm"], None, data)

    def add_multi_column_table(self, title, headers, rows):
        """Tableau multi-colonnes avec en-tête."""
        n = len(headers)
        col_w = f"{21.0 / n:.2f}cm"
        self._build_table(title, [col_w] * n, headers, rows)

    # ------------------------------------------------------------------ output
    def save(self, output_stream):
        self.doc.save(output_stream)