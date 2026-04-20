# import pdfplumber
# import pandas as pd

# tables = []

# with pdfplumber.open('C:\\Personal\\2024\\Learning\\Generative AI\\RAG\\27_Context_Engineering\\2_RAG\\1_Document_Processing\\Data\\BioGenX_text.pdf') as pdf:
#     for page_num, page in enumerate(pdf.pages, start=1):  # Fix 1: use enumerate
#         tables_on_page = page.extract_tables({
#             "vertical_strategy": "text",
#             "horizontal_strategy": "text",
#             "intersection_x_tolerance": 10,
#             "intersection_y_tolerance": 10
#         })
        
#         if tables_on_page:
#             for table in tables_on_page:
#                 if table:
#                     tables.append({
#                         'page': page_num,  # Fix 1: use enumerated page number
#                         'data': table
#                     })

# for table in tables:
#     print(f"\nTable from page {table['page']}:")
#     print(pd.DataFrame(table['data']))
#     print("-" * 50)

# Using pypdf
# import pypdf

# def extract_text_from_pdf(pdf_path):
#     text = ""

#     with open(pdf_path, 'rb') as file:
#         pdf_reader = pypdf.PdfReader(file)
#         num_pages = len(pdf_reader.pages)

#         for page_num in range(num_pages):
#             page = pdf_reader.pages[page_num]
#             page_text = page.extract_text()
#             text += page_text + "\n\n"

#     return text

# # Run it
# text = extract_text_from_pdf('C:\\Personal\\2024\\Learning\\Generative AI\\RAG\\27_Context_Engineering\\2_RAG\\1_Document_Processing\\Data\\BioGenX_text.pdf')
# print(text)

# Using tabula
from tabula.io import read_pdf
import pandas as pd

pdf_path = r'D:\GenAI Content\AI code\4_RAG_Indexing\1_Document_Processing\Data\Safari_text.pdf'

# Try lattice mode first (for tables with visible borders)
tables = read_pdf(
    pdf_path,
    pages='all',
    multiple_tables=True,
    lattice=True,
    guess=False,
    pandas_options={'header': None},
)

# Fallback to stream mode if no tables found
if not tables:
    tables = read_pdf(
        pdf_path,
        pages='all',
        multiple_tables=True,
        stream=True,
        guess=False,
        pandas_options={'header': None},
    )

for i, table in enumerate(tables, 1):
    print(f"\nTable {i}:")
    print(table)
    print("-" * 50)


# import pdfplumber
# import pandas as pd

# pdf_path = r'C:\Personal\2024\Learning\Generative AI\RAG\27_Context_Engineering\2_RAG\1_Document_Processing\Data\BioGenX_text.pdf'

# with pdfplumber.open(pdf_path) as pdf:
#     for page_num, page in enumerate(pdf.pages, start=1):
#         print(f"\n{'='*50}")
#         print(f"PAGE {page_num} - Full Text:")
#         print('='*50)
#         print(page.extract_text())

#         print(f"\nPAGE {page_num} - Tables:")
#         print('-'*50)
#         tables = page.extract_tables()

#         if tables:
#             for i, table in enumerate(tables, 1):
#                 print(f"\nTable {i}:")
#                 df = pd.DataFrame(table)
#                 print(df.to_string(index=False))
#         else:
#             # No formal tables detected — extract words by position
#             print("No bordered tables found. Extracting by word positions...\n")
#             words = page.extract_words()
#             # Group words by their vertical position (same line = same row)
#             from itertools import groupby
#             lines = {}
#             for word in words:
#                 row_key = round(word['top'] / 5) * 5  # bucket by 5pt bands
#                 lines.setdefault(row_key, []).append(word['text'])

#             for _, line_words in sorted(lines.items()):
#                 print('  '.join(line_words))
