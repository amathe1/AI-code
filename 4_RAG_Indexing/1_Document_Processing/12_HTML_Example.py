# Here is a **line‑by‑line explanation** of the HTML parsing code using `BeautifulSoup` and `pandas`, presented as bullet points.

# - `from bs4 import BeautifulSoup`
#   - Imports the `BeautifulSoup` class from the `bs4` library.
#   - BeautifulSoup is used for parsing HTML and XML documents, making it easy to navigate and search the parse tree.

# - `import pandas as pd`
#   - Imports the `pandas` library with the alias `pd`.
#   - Pandas is used here to create DataFrames from HTML tables and KPI cards.

# - `with open('C:\\Personal\\2024\\Learning\\Generative AI\\RAG\\27_Context_Engineering\\2_RAG\\1_Document_Processing\\Data\\company_report.html', 'r', encoding='utf-8') as f:`
#   - Opens the HTML file at the given path in read mode (`'r'`) with UTF‑8 encoding.
#   - The `with` statement ensures the file is automatically closed after the block.

# - `soup = BeautifulSoup(f, 'lxml')`
#   - Creates a BeautifulSoup object by parsing the file object `f` using the `lxml` parser (fast and lenient).
#   - The resulting `soup` object represents the entire HTML document as a navigable tree.

# - `# ── Method 1: Document metadata ───────────────────────────────────────────────`
#   - A comment indicating the start of the first method (extracting basic metadata).

# - `print("=" * 60)`
#   - Prints a line of 60 equals signs as a visual separator.

# - `print("METHOD 1: Document Metadata")`
#   - Prints a descriptive header for the first method.

# - `print("=" * 60)`
#   - Prints another separator line.

# - `print(f"Title   : {soup.title.text.strip()}")`
#   - Accesses the `<title>` tag via `soup.title`, extracts its text content with `.text`, and strips whitespace.
#   - Prints the page title.

# - `print(f"H1      : {soup.find('h1').text.strip()}")`
#   - Uses `soup.find('h1')` to locate the first `<h1>` tag, extracts its text, and strips whitespace.
#   - Prints the main heading.

# - `print(f"Sections: {len(soup.find_all('section'))}")`
#   - Finds all `<section>` tags in the document using `soup.find_all('section')` and counts them with `len()`.
#   - Prints the number of sections.

# - `print(f"Tables  : {len(soup.find_all('table'))}")`
#   - Counts all `<table>` tags and prints the number.

# - `print(f"Lists   : {len(soup.find_all(['ul', 'ol']))}")`
#   - Finds all `<ul>` (unordered list) and `<ol>` (ordered list) tags by passing a list of tag names to `find_all()`.
#   - Prints the total number of lists.

# - `# ── Method 2: All sections with headings + content ────────────────────────────`
#   - A comment indicating the second method (extracting sections, headings, paragraphs, quotes, lists).

# - `print("\n" + "=" * 60)`
#   - Prints a newline followed by a separator.

# - `print("METHOD 2: Sections with Headings & Paragraphs")`
#   - Prints the header for the second method.

# - `print("=" * 60)`
#   - Prints another separator.

# - `for section in soup.find_all('section'):`
#   - Iterates over every `<section>` element in the HTML.

# - `section_id = section.get('id', 'unknown')`
#   - Retrieves the value of the `id` attribute of the section. If the attribute does not exist, returns `'unknown'`.

# - `h2 = section.find('h2')`
#   - Finds the first `<h2>` tag inside the current section. Returns `None` if not found.

# - `heading = h2.text.strip() if h2 else 'No heading'`
#   - If an `<h2>` was found, extracts its stripped text; otherwise, sets `heading` to `'No heading'`.

# - `print(f"\n[Section: #{section_id}] {heading}")`
#   - Prints the section ID (prefixed with `#`) and its heading.

# - `print("-" * 50)`
#   - Prints a line of 50 hyphens.

# - `# Paragraphs`
#   - A comment indicating that the next block extracts paragraphs.

# - `for p in section.find_all('p'):`
#   - Iterates over all `<p>` tags inside the current section.

# - `text = p.get_text(strip=True)`
#   - Extracts all text inside the `<p>` tag, recursively, and strips whitespace (removes leading/trailing spaces and collapses internal whitespace).

# - `if text:`
#   - If the extracted text is not empty.

# - `print(f"  Para : {text[:100]}{'...' if len(text) > 100 else ''}")`
#   - Prints the first 100 characters of the paragraph. If the text is longer than 100 characters, appends `...` to indicate truncation.

# - `# Blockquotes`
#   - A comment indicating extraction of blockquotes.

# - `for bq in section.find_all('blockquote'):`
#   - Iterates over all `<blockquote>` tags inside the section.

# - `quote = bq.get_text(separator=' ', strip=True)`
#   - Extracts text from the blockquote, using a space as separator between different elements (instead of the default newline), and strips whitespace.

# - `print(f"  Quote: {quote[:100]}...")`
#   - Prints the first 100 characters of the quote followed by `...` (assumes all quotes are longer than 100 characters for brevity).

# - `# List items`
#   - A comment indicating extraction of lists.

# - `for ul in section.find_all(['ul', 'ol']):`
#   - Iterates over all unordered (`<ul>`) and ordered (`<ol>`) lists inside the section.

# - `list_id = ul.get('id', 'list')`
#   - Retrieves the `id` attribute of the list, defaulting to `'list'` if absent.

# - `items = [li.get_text(strip=True) for li in ul.find_all('li')]`
#   - Creates a list comprehension: for each `<li>` inside the list, extracts its stripped text and collects it.

# - `print(f"  List [{list_id}]: {len(items)} items")`
#   - Prints the list ID and the number of items.

# - `for item in items:`
#   - Iterates over each list item.

# - `print(f"    • {item}")`
#   - Prints a bullet symbol (`•`) followed by the item text, indented further.

# - `# ── Method 3: KPI cards as structured data ────────────────────────────────────`
#   - A comment indicating the third method (extracting KPI cards as structured data).

# - `print("\n" + "=" * 60)`
#   - Prints a newline and a separator.

# - `print("METHOD 3: KPI Cards → Structured Data")`
#   - Prints the header for the third method.

# - `print("=" * 60)`
#   - Prints another separator.

# - `kpis = []`
#   - Initialises an empty list that will hold dictionaries, each representing one KPI card.

# - `for card in soup.find_all('div', class_='kpi-card'):`
#   - Finds all `<div>` elements with the CSS class `'kpi-card'` and iterates over them.

# - `kpis.append({`
#   - Appends a new dictionary to the `kpis` list.

# - `'metric'  : card.get('data-metric', 'N/A'),`
#   - Retrieves the `data-metric` attribute from the card. If not present, defaults to `'N/A'`.

# - `'label'   : card.find(class_='kpi-label').text.strip(),`
#   - Finds an element with class `'kpi-label'` inside the card, extracts its text, and strips whitespace. Assumes it exists.

# - `'value'   : card.find(class_='kpi-value').text.strip(),`
#   - Finds an element with class `'kpi-value'` and extracts its stripped text.

# - `'change'  : card.find(class_='kpi-change').text.strip(),`
#   - Finds an element with class `'kpi-change'` and extracts its stripped text.

# - `'trend'   : 'up' if 'up' in card.find(class_='kpi-change').get('class', []) else 'down'`
#   - Looks at the CSS classes of the `kpi-change` element. If the list of classes contains `'up'`, sets trend to `'up'`; otherwise `'down'`.

# - `})`
#   - Closes the dictionary and the `append` call.

# - `df_kpi = pd.DataFrame(kpis)`
#   - Creates a pandas DataFrame from the list of dictionaries `kpis`. Each dictionary becomes a row.

# - `print(df_kpi.to_string(index=False))`
#   - Prints the DataFrame as a string, omitting the row index numbers.

# - `# ── Method 4: HTML table → DataFrame ─────────────────────────────────────────`
#   - A comment indicating the fourth method (converting an HTML table to a DataFrame).

# - `print("\n" + "=" * 60)`
#   - Prints a newline and a separator.

# - `print("METHOD 4: Product Table → Pandas DataFrame")`
#   - Prints the header for the fourth method.

# - `print("=" * 60)`
#   - Prints another separator.

# - `table = soup.find('table', id='product-table')`
#   - Finds the `<table>` element with the attribute `id='product-table'`. Assumes it exists.

# - `# Extract headers`
#   - A comment indicating extraction of column headers.

# - `headers = [th.text.strip() for th in table.select('thead th')]`
#   - Uses a CSS selector `'thead th'` to find all `<th>` cells inside the `<thead>` of the table.
#   - Creates a list of stripped header texts.

# - `# Extract rows preserving badge text`
#   - A comment indicating row extraction.

# - `rows = []`
#   - Initialises an empty list to hold the rows of data.

# - `for tr in table.select('tbody tr'):`
#   - Uses the CSS selector `'tbody tr'` to find all `<tr>` rows inside the `<tbody>` of the table.

# - `cells = [td.get_text(strip=True) for td in tr.find_all('td')]`
#   - For each row, finds all `<td>` cells, extracts their stripped text, and collects them into a list.

# - `rows.append(cells)`
#   - Appends the list of cell texts to the `rows` list.

# - `df_products = pd.DataFrame(rows, columns=headers)`
#   - Creates a pandas DataFrame from the `rows` list, using the extracted `headers` as column names.

# - `print(df_products.to_string(index=False))`
#   - Prints the entire DataFrame without row indices.

# - `# Extra: filter only Active products`
#   - A comment indicating a simple filter operation.

# - `print("\n  Active products only:")`
#   - Prints a newline and a sub‑header.

# - `active = df_products[df_products['Status'] == 'Active']`
#   - Filters the DataFrame to keep only rows where the `'Status'` column equals `'Active'`.

# - `print(active[['Product Name', 'Q1 Revenue', 'Growth']].to_string(index=False))`
#   - Prints only the selected columns (`'Product Name'`, `'Q1 Revenue'`, `'Growth'`) of the filtered DataFrame, without row indices.

# - `# ── Method 5: Full document structure as dict ─────────────────────────────────`
#   - A comment indicating the fifth method (building a summary dictionary).

# - `print("\n" + "=" * 60)`
#   - Prints a newline and a separator.

# - `print("METHOD 5: Full Structure Summary")`
#   - Prints the header for the fifth method.

# - `print("=" * 60)`
#   - Prints another separator.

# - `structure = {`
#   - Initialises a dictionary named `structure`.

# - `'title'    : soup.title.text.strip(),`
#   - Stores the stripped page title under the key `'title'`.

# - `'sections' : [],`
#   - Initialises an empty list under the key `'sections'` to hold data about each section.

# - `}`
#   - Closes the dictionary.

# - `for section in soup.find_all('section'):`
#   - Iterates over all `<section>` elements again.

# - `h2      = section.find('h2')`
#   - Finds the first `<h2>` inside the section.

# - `lists   = section.find_all(['ul', 'ol'])`
#   - Finds all `<ul>` and `<ol>` lists inside the section.

# - `tables  = section.find_all('table')`
#   - Finds all `<table>` tags inside the section.

# - `paras   = section.find_all('p')`
#   - Finds all `<p>` tags inside the section.

# - `structure['sections'].append({`
#   - Appends a new dictionary to the `'sections'` list.

# - `'id'      : section.get('id'),`
#   - Stores the section’s `id` attribute (or `None` if not present).

# - `'heading' : h2.text.strip() if h2 else None,`
#   - Stores the heading text if an `<h2>` exists, otherwise `None`.

# - `'paragraphs' : len(paras),`
#   - Stores the number of paragraphs.

# - `'lists'   : [`
#   - Begins a list that will hold dictionaries for each list.

# - `{'id': l.get('id'), 'items': [li.get_text(strip=True) for li in l.find_all('li')]}`
#   - For each list `l`, creates a dictionary with its `id` and a list of item texts.

# - `for l in lists`
#   - Iterates over the `lists` found earlier (comprehension inside the list building).

# - `],`
#   - Closes the list.

# - `'tables'  : len(tables),`
#   - Stores the number of tables.

# - `})`
#   - Closes the section dictionary and the `append` call.

# - `for s in structure['sections']:`
#   - Iterates over each section in the `'sections'` list.

# - `print(f"\n  [{s['id']}] {s['heading']}")`
#   - Prints the section ID and heading, indented.

# - `print(f"    Paragraphs : {s['paragraphs']}")`
#   - Prints the number of paragraphs.

# - `print(f"    Tables     : {s['tables']}")`
#   - Prints the number of tables.

# - `for lst in s['lists']:`
#   - Iterates over the lists in the current section.

# - `print(f"    List [{lst['id']}]: {len(lst['items'])} items → {lst['items'][:2]}...")`
#   - Prints the list ID, the number of items, and the first two items (truncated with `...`).

from bs4 import BeautifulSoup
import pandas as pd

with open('D:\\GenAI Content\\AI code\\4_RAG_Indexing\\1_Document_Processing\\Data\\company_report.html', 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f, 'lxml')

# ── Method 1: Document metadata ───────────────────────────────────────────────
print("=" * 60)
print("METHOD 1: Document Metadata")
print("=" * 60)

print(f"Title   : {soup.title.text.strip()}")
print(f"H1      : {soup.find('h1').text.strip()}")
print(f"Sections: {len(soup.find_all('section'))}")
print(f"Tables  : {len(soup.find_all('table'))}")
print(f"Lists   : {len(soup.find_all(['ul', 'ol']))}")

# ── Method 2: All sections with headings + content ────────────────────────────
print("\n" + "=" * 60)
print("METHOD 2: Sections with Headings & Paragraphs")
print("=" * 60)

for section in soup.find_all('section'):
    section_id = section.get('id', 'unknown')
    h2 = section.find('h2')
    heading = h2.text.strip() if h2 else 'No heading'
    print(f"\n[Section: #{section_id}] {heading}")
    print("-" * 50)

    # Paragraphs
    for p in section.find_all('p'):
        text = p.get_text(strip=True)
        if text:
            print(f"  Para : {text[:100]}{'...' if len(text) > 100 else ''}")

    # Blockquotes
    for bq in section.find_all('blockquote'):
        quote = bq.get_text(separator=' ', strip=True)
        print(f"  Quote: {quote[:100]}...")

    # List items
    for ul in section.find_all(['ul', 'ol']):
        list_id = ul.get('id', 'list')
        items = [li.get_text(strip=True) for li in ul.find_all('li')]
        print(f"  List [{list_id}]: {len(items)} items")
        for item in items:
            print(f"    • {item}")

# ── Method 3: KPI cards as structured data ────────────────────────────────────
print("\n" + "=" * 60)
print("METHOD 3: KPI Cards → Structured Data")
print("=" * 60)

kpis = []
for card in soup.find_all('div', class_='kpi-card'):
    kpis.append({
        'metric'  : card.get('data-metric', 'N/A'),
        'label'   : card.find(class_='kpi-label').text.strip(),
        'value'   : card.find(class_='kpi-value').text.strip(),
        'change'  : card.find(class_='kpi-change').text.strip(),
        'trend'   : 'up' if 'up' in card.find(class_='kpi-change').get('class', []) else 'down'
    })

df_kpi = pd.DataFrame(kpis)
print(df_kpi.to_string(index=False))

# ── Method 4: HTML table → DataFrame ─────────────────────────────────────────
print("\n" + "=" * 60)
print("METHOD 4: Product Table → Pandas DataFrame")
print("=" * 60)

table = soup.find('table', id='product-table')

# Extract headers
headers = [th.text.strip() for th in table.select('thead th')]

# Extract rows preserving badge text
rows = []
for tr in table.select('tbody tr'):
    cells = [td.get_text(strip=True) for td in tr.find_all('td')]
    rows.append(cells)

df_products = pd.DataFrame(rows, columns=headers)
print(df_products.to_string(index=False))

# Extra: filter only Active products
print("\n  Active products only:")
active = df_products[df_products['Status'] == 'Active']
print(active[['Product Name', 'Q1 Revenue', 'Growth']].to_string(index=False))

# ── Method 5: Full document structure as dict ─────────────────────────────────
print("\n" + "=" * 60)
print("METHOD 5: Full Structure Summary")
print("=" * 60)

structure = {
    'title'    : soup.title.text.strip(),
    'sections' : [],
}

for section in soup.find_all('section'):
    h2      = section.find('h2')
    lists   = section.find_all(['ul', 'ol'])
    tables  = section.find_all('table')
    paras   = section.find_all('p')

    structure['sections'].append({
        'id'      : section.get('id'),
        'heading' : h2.text.strip() if h2 else None,
        'paragraphs' : len(paras),
        'lists'   : [
            {'id': l.get('id'), 'items': [li.get_text(strip=True) for li in l.find_all('li')]}
            for l in lists
        ],
        'tables'  : len(tables),
    })

for s in structure['sections']:
    print(f"\n  [{s['id']}] {s['heading']}")
    print(f"    Paragraphs : {s['paragraphs']}")
    print(f"    Tables     : {s['tables']}")
    for lst in s['lists']:
        print(f"    List [{lst['id']}]: {len(lst['items'])} items → {lst['items'][:2]}...")