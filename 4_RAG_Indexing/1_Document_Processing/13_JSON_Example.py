# Here is a **line‑by‑line explanation** of the JSON parsing code using `json` and `pandas`, presented as bullet points.

# - `import json`
#   - Imports Python’s built‑in `json` module, used to parse JSON strings and files into Python data structures (dicts, lists, strings, numbers, etc.).

# - `import pandas as pd`
#   - Imports the `pandas` library with the alias `pd`. Used here to create DataFrames from JSON data for analysis and filtering.

# - `from datetime import datetime`
#   - Imports the `datetime` class from the `datetime` module. (Although not used in this code, it is available for date parsing if needed.)

# - `with open('C:\\Personal\\2024\\Learning\\Generative AI\\RAG\\27_Context_Engineering\\2_RAG\\1_Document_Processing\\Data\\company_data.json', 'r', encoding='utf-8') as f:`
#   - Opens the JSON file at the given path in read mode (`'r'`) with UTF‑8 encoding.
#   - The `with` statement ensures the file is properly closed after the block.

# - `data = json.load(f)`
#   - Uses `json.load()` to read the file object `f` and parse its contents into a Python dictionary (or list). The resulting object is stored in the variable `data`.

# - `# ── Method 1: Top-level metadata ──────────────────────────────────────────────`
#   - A comment indicating the first method: extracting company‑level metadata.

# - `print("=" * 60)`
#   - Prints a line of 60 equals signs as a visual separator.

# - `print("METHOD 1: Company Info & Metadata")`
#   - Prints a descriptive header for the first method.

# - `print("=" * 60)`
#   - Prints another separator line.

# - `company = data['company']`
#   - Accesses the dictionary under the key `'company'` (top‑level in the JSON) and assigns it to the variable `company`.

# - `print(f"  Company   : {company['name']}")`
#   - Prints the company name, indented by two spaces.

# - `print(f"  Founded   : {company['founded']}")`
#   - Prints the founding year (or date) from the `company` dictionary.

# - `print(f"  HQ        : {company['headquarters']}")`
#   - Prints the headquarters location.

# - `print(f"  Industry  : {company['industry']}")`
#   - Prints the industry field.

# - `print(f"  Employees : {company['total_employees']}")`
#   - Prints the total number of employees (a top‑level aggregated value).

# - `meta = data['metadata']`
#   - Accesses the dictionary under the key `'metadata'` and assigns it to `meta`.

# - `print(f"\n  Version   : {meta['version']}")`
#   - Prints the version number of the data (e.g., `'1.0'`), preceded by a newline.

# - `print(f"  Created   : {meta['created_at']}")`
#   - Prints the creation timestamp of the data.

# - `print(f"  Class.    : {meta['classification']}")`
#   - Prints the classification (e.g., `'internal'`, `'confidential'`).

# - `# ── Method 2: Nested structure — departments + employees ─────────────────────`
#   - A comment indicating the second method: traversing nested departments and employees.

# - `print("\n" + "=" * 60)`
#   - Prints a newline followed by a separator.

# - `print("METHOD 2: Departments with Nested Employees")`
#   - Prints the header for the second method.

# - `print("=" * 60)`
#   - Prints another separator.

# - `for dept in data['departments']:`
#   - Iterates over each department dictionary in the list stored under the key `'departments'`.

# - `print(f"\n  [{dept['dept_id']}] {dept['name']}  |  Head: {dept['head']}  |  Budget: ${dept['budget_usd']:,}")`
#   - Prints the department ID, name, head (manager name), and budget formatted with commas as thousands separators.

# - `print(f"  {'-' * 52}")`
#   - Prints a line of 52 hyphens for visual separation.

# - `for emp in dept['employees']:`
#   - Iterates over the list of employees within the current department.

# - `print(f"    {emp['emp_id']} — {emp['name']:20s} | {emp['role']:25s} | {emp['status']}")`
#   - Prints employee ID, name (right‑padded to 20 characters), role (padded to 25), and status (e.g., `'Active'`).

# - `print(f"    {'':10s} Skills : {', '.join(emp['skills'])}")`
#   - Prints 10 spaces, then `Skills :`, followed by the list of skills joined with commas.

# - `print(f"    {'':10s} Salary : ${emp['salary_usd']:,}  |  Joined: {emp['joined']}")`
#   - Prints salary with commas and the join date.

# - `print(f"    {'':10s} Q1 Score: {emp['performance']['q1_2026']}")`
#   - Prints the Q1 performance score from the nested `performance` dictionary.

# - `print(f"    {'':10s} City   : {emp['address']['city']}, {emp['address']['state']}")`
#   - Prints the city and state from the nested `address` dictionary.

# - `print()`
#   - Prints an empty line to separate employees.

# - `# ── Method 3: Flatten employees into a DataFrame ──────────────────────────────`
#   - A comment indicating the third method: flattening nested employee data into a table.

# - `print("=" * 60)`
#   - Prints a separator.

# - `print("METHOD 3: All Employees → Flat DataFrame")`
#   - Prints the header for the third method.

# - `print("=" * 60)`
#   - Prints another separator.

# - `rows = []`
#   - Initialises an empty list that will hold dictionaries (each representing one employee row).

# - `for dept in data['departments']:`
#   - Iterates over each department again.

# - `for emp in dept['employees']:`
#   - Iterates over each employee in the department.

# - `rows.append({`
#   - Appends a new dictionary to the `rows` list.

# - `'emp_id'      : emp['emp_id'],`
#   - Stores employee ID.

# - `'name'        : emp['name'],`
#   - Stores employee name.

# - `'department'  : dept['name'],`
#   - Stores the department name (from the parent department).

# - `'role'        : emp['role'],`
#   - Stores the role.

# - `'salary_usd'  : emp['salary_usd'],`
#   - Stores salary.

# - `'status'      : emp['status'],`
#   - Stores status.

# - `'joined'      : emp['joined'],`
#   - Stores join date.

# - `'q1_score'    : emp['performance']['q1_2026'],`
#   - Stores the Q1 performance score from the nested `performance` dictionary.

# - `'city'        : emp['address']['city'],`
#   - Stores the city from the nested `address` dictionary.

# - `'skills_count': len(emp['skills']),`
#   - Stores the number of skills (length of the `skills` list).

# - `})`
#   - Closes the dictionary and the `append` call.

# - `df_emp = pd.DataFrame(rows)`
#   - Creates a pandas DataFrame from the list of dictionaries `rows`. Each dictionary becomes a row.

# - `print(df_emp.to_string(index=False))`
#   - Prints the entire DataFrame as a string, omitting the row index numbers.

# - `# Aggregation — avg salary by department`
#   - A comment indicating that the next block computes average salary per department.

# - `print("\n  Average Salary by Department:")`
#   - Prints a newline and a sub‑header.

# - `print(df_emp.groupby('department')['salary_usd']`
#   - Groups the DataFrame by the `'department'` column and selects the `'salary_usd'` column.

# - `.mean().apply(lambda x: f"${x:,.0f}").to_string())`
#   - Computes the mean salary for each department, applies a lambda that formats each value as currency with commas and no decimal places, then converts to a string for printing.

# - `# ── Method 4: Products list → DataFrame with filtering ───────────────────────`
#   - A comment indicating the fourth method: converting the products list to a DataFrame and filtering.

# - `print("\n" + "=" * 60)`
#   - Prints a newline and a separator.

# - `print("METHOD 4: Products → DataFrame with Filtering")`
#   - Prints the header for the fourth method.

# - `print("=" * 60)`
#   - Prints another separator.

# - `df_prod = pd.DataFrame(data['products'])`
#   - Creates a DataFrame directly from the list of product dictionaries stored under the key `'products'`.

# - `print(df_prod.to_string(index=False))`
#   - Prints the entire products DataFrame without row indices.

# - `print("\n  Active products only:")`
#   - Prints a newline and a sub‑header.

# - `active = df_prod[df_prod['status'] == 'Active']`
#   - Filters the products DataFrame to keep only rows where the `'status'` column equals `'Active'`. The result is stored in `active`.

# - `print(active[['name', 'category', 'price_usd', 'q1_revenue']].to_string(index=False))`
#   - Prints only the selected columns (`'name'`, `'category'`, `'price_usd'`, `'q1_revenue'`) of the filtered DataFrame, without row indices.

# - `print(f"\n  Total Q1 Revenue (Active): ${active['q1_revenue'].sum():,}")`
#   - Computes the sum of the `'q1_revenue'` column for active products, formats it as currency with commas, and prints the total.

# - `# ── Method 5: Deeply nested access — financials comparison ───────────────────`
#   - A comment indicating the fifth method: iterating over quarterly financial data.

# - `print("\n" + "=" * 60)`
#   - Prints a newline and a separator.

# - `print("METHOD 5: Financials — Quarter-over-Quarter")`
#   - Prints the header for the fifth method.

# - `print("=" * 60)`
#   - Prints another separator.

# - `financials = data['financials']`
#   - Accesses the dictionary under the key `'financials'` and assigns it to `financials`.

# - `for quarter, stats in financials.items():`
#   - Iterates over each key‑value pair in the `financials` dictionary. `quarter` is the key (e.g., `'q1_2026'`), `stats` is the nested dictionary of financial numbers.

# - `print(f"\n  {quarter.upper()}")`
#   - Prints the quarter name in uppercase, preceded by a newline.

# - `print(f"    Revenue  : ${stats['total_revenue_usd']:,}")`
#   - Prints total revenue with commas.

# - `print(f"    Expenses : ${stats['total_expenses_usd']:,}")`
#   - Prints total expenses with commas.

# - `print(f"    Profit   : ${stats['net_profit_usd']:,}")`
#   - Prints net profit with commas.

# - `growth_key = [k for k in stats if 'growth' in k][0]`
#   - Creates a list of keys in the `stats` dictionary that contain the substring `'growth'`, then takes the first such key (e.g., `'revenue_growth'`). Assumes at least one exists.

# - `print(f"    Growth   : {stats[growth_key]}%")`
#   - Prints the growth percentage using the found key, appending a `%` sign.

# - `# ── Method 6: Search & filter across nested structure ─────────────────────────`
#   - A comment indicating the sixth method: searching for specific skills or performance criteria.

# - `print("\n" + "=" * 60)`
#   - Prints a newline and a separator.

# - `print("METHOD 6: Search Across Nested Data")`
#   - Prints the header for the sixth method.

# - `print("=" * 60)`
#   - Prints another separator.

# - `# Find all employees with a specific skill`
#   - A comment describing the search.

# - `search_skill = "Python"`
#   - Defines a variable with the skill to search for.

# - `print(f"\n  Employees with skill '{search_skill}':")`
#   - Prints a sub‑header showing the skill being searched.

# - `for dept in data['departments']:`
#   - Iterates over each department.

# - `for emp in dept['employees']:`
#   - Iterates over each employee in the department.

# - `if search_skill in emp['skills']:`
#   - Checks if the `search_skill` string is present in the employee’s `skills` list.

# - `print(f"    → {emp['name']} ({dept['name']})")`
#   - Prints the employee’s name and department, preceded by an arrow.

# - `# Find all Active employees with Q1 score > 4.5`
#   - A comment describing the second search.

# - `print(f"\n  High performers (Q1 score > 4.5 & Active):")`
#   - Prints a sub‑header.

# - `for dept in data['departments']:`
#   - Iterates over departments again.

# - `for emp in dept['employees']:`
#   - Iterates over employees again.

# - `if emp['status'] == 'Active' and emp['performance']['q1_2026'] > 4.5:`
#   - Checks both conditions: status is `'Active'` and the Q1 score is greater than 4.5.

# - `print(f"    → {emp['name']:20s} | Score: {emp['performance']['q1_2026']} | {dept['name']}")`
#   - Prints the employee name (padded to 20 characters), the score, and the department name.

# - `# ── Method 7: Full structure summary ─────────────────────────────────────────`
#   - A comment indicating the seventh method: summarizing the entire JSON structure.

# - `print("\n" + "=" * 60)`
#   - Prints a newline and a separator.

# - `print("METHOD 7: Document Structure Summary")`
#   - Prints the header for the seventh method.

# - `print("=" * 60)`
#   - Prints another separator.

# - `print(f"  Top-level keys : {list(data.keys())}")`
#   - Prints the list of top‑level keys in the loaded JSON dictionary.

# - `print(f"  Departments    : {len(data['departments'])}")`
#   - Prints the number of departments (length of the `'departments'` list).

# - `print(f"  Total Employees: {sum(len(d['employees']) for d in data['departments'])}")`
#   - Sums the lengths of the `'employees'` lists across all departments to get the total employee count.

# - `print(f"  Products       : {len(data['products'])}")`
#   - Prints the number of products.

# - `print(f"  Financial Qtrs : {len(data['financials'])}")`
#   - Prints the number of financial quarters (keys in the `'financials'` dictionary).

# - `print(f"  Unique Skills  : {len(set(s for d in data['departments'] for e in d['employees'] for s in e['skills']))}")`
#   - Uses a nested generator expression: for each department, for each employee, for each skill in the employee’s skills list, collects the skill. Then creates a `set` to keep unique skills, and finally prints the count of unique skills across all employees.

import json
import pandas as pd
from datetime import datetime

with open('D:\\GenAI Content\AI code\\4_RAG_Indexing\\1_Document_Processing\\Data\\company_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# ── Method 1: Top-level metadata ──────────────────────────────────────────────
print("=" * 60)
print("METHOD 1: Company Info & Metadata")
print("=" * 60)

company = data['company']
print(f"  Company   : {company['name']}")
print(f"  Founded   : {company['founded']}")
print(f"  HQ        : {company['headquarters']}")
print(f"  Industry  : {company['industry']}")
print(f"  Employees : {company['total_employees']}")

meta = data['metadata']
print(f"\n  Version   : {meta['version']}")
print(f"  Created   : {meta['created_at']}")
print(f"  Class.    : {meta['classification']}")

# ── Method 2: Nested structure — departments + employees ─────────────────────
print("\n" + "=" * 60)
print("METHOD 2: Departments with Nested Employees")
print("=" * 60)

for dept in data['departments']:
    print(f"\n  [{dept['dept_id']}] {dept['name']}  |  Head: {dept['head']}  |  Budget: ${dept['budget_usd']:,}")
    print(f"  {'-' * 52}")
    for emp in dept['employees']:
        print(f"    {emp['emp_id']} — {emp['name']:20s} | {emp['role']:25s} | {emp['status']}")
        print(f"    {'':10s} Skills : {', '.join(emp['skills'])}")
        print(f"    {'':10s} Salary : ${emp['salary_usd']:,}  |  Joined: {emp['joined']}")
        print(f"    {'':10s} Q1 Score: {emp['performance']['q1_2026']}")
        print(f"    {'':10s} City   : {emp['address']['city']}, {emp['address']['state']}")
        print()

# ── Method 3: Flatten employees into a DataFrame ──────────────────────────────
print("=" * 60)
print("METHOD 3: All Employees → Flat DataFrame")
print("=" * 60)

rows = []
for dept in data['departments']:
    for emp in dept['employees']:
        rows.append({
            'emp_id'      : emp['emp_id'],
            'name'        : emp['name'],
            'department'  : dept['name'],
            'role'        : emp['role'],
            'salary_usd'  : emp['salary_usd'],
            'status'      : emp['status'],
            'joined'      : emp['joined'],
            'q1_score'    : emp['performance']['q1_2026'],
            'city'        : emp['address']['city'],
            'skills_count': len(emp['skills']),
        })

df_emp = pd.DataFrame(rows)
print(df_emp.to_string(index=False))

# Aggregation — avg salary by department
print("\n  Average Salary by Department:")
print(df_emp.groupby('department')['salary_usd']
      .mean().apply(lambda x: f"${x:,.0f}").to_string())

# ── Method 4: Products list → DataFrame with filtering ───────────────────────
print("\n" + "=" * 60)
print("METHOD 4: Products → DataFrame with Filtering")
print("=" * 60)

df_prod = pd.DataFrame(data['products'])
print(df_prod.to_string(index=False))

print("\n  Active products only:")
active = df_prod[df_prod['status'] == 'Active']
print(active[['name', 'category', 'price_usd', 'q1_revenue']].to_string(index=False))

print(f"\n  Total Q1 Revenue (Active): ${active['q1_revenue'].sum():,}")

# ── Method 5: Deeply nested access — financials comparison ───────────────────
print("\n" + "=" * 60)
print("METHOD 5: Financials — Quarter-over-Quarter")
print("=" * 60)

financials = data['financials']
for quarter, stats in financials.items():
    print(f"\n  {quarter.upper()}")
    print(f"    Revenue  : ${stats['total_revenue_usd']:,}")
    print(f"    Expenses : ${stats['total_expenses_usd']:,}")
    print(f"    Profit   : ${stats['net_profit_usd']:,}")
    growth_key = [k for k in stats if 'growth' in k][0]
    print(f"    Growth   : {stats[growth_key]}%")

# ── Method 6: Search & filter across nested structure ─────────────────────────
print("\n" + "=" * 60)
print("METHOD 6: Search Across Nested Data")
print("=" * 60)

# Find all employees with a specific skill
search_skill = "Python"
print(f"\n  Employees with skill '{search_skill}':")
for dept in data['departments']:
    for emp in dept['employees']:
        if search_skill in emp['skills']:
            print(f"    → {emp['name']} ({dept['name']})")

# Find all Active employees with Q1 score > 4.5
print(f"\n  High performers (Q1 score > 4.5 & Active):")
for dept in data['departments']:
    for emp in dept['employees']:
        if emp['status'] == 'Active' and emp['performance']['q1_2026'] > 4.5:
            print(f"    → {emp['name']:20s} | Score: {emp['performance']['q1_2026']} | {dept['name']}")

# ── Method 7: Full structure summary ─────────────────────────────────────────
print("\n" + "=" * 60)
print("METHOD 7: Document Structure Summary")
print("=" * 60)

print(f"  Top-level keys : {list(data.keys())}")
print(f"  Departments    : {len(data['departments'])}")
print(f"  Total Employees: {sum(len(d['employees']) for d in data['departments'])}")
print(f"  Products       : {len(data['products'])}")
print(f"  Financial Qtrs : {len(data['financials'])}")
print(f"  Unique Skills  : {len(set(s for d in data['departments'] for e in d['employees'] for s in e['skills']))}")