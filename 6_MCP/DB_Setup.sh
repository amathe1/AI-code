#!/bin/bash
# ============================================================
#  DOCKER SETUP SCRIPT — PostgreSQL for MCP Use Case 3
#  Run this BEFORE starting the database MCP server
# ============================================================
#
#  PREREQUISITES:
#    - Docker installed and running
#
#  USAGE:
#    chmod +x setup_db.sh
#    ./setup_db.sh
#
# ============================================================

set -e   # exit on any error

DB_CONTAINER="mcp-postgres"
DB_NAME="agentdb"
DB_USER="agentuser"
DB_PASS="agentpass"
DB_PORT="5432"

echo "🐳 Step 1: Pull PostgreSQL Docker image..."
docker pull postgres:15-alpine

echo ""
echo "🐳 Step 2: Start PostgreSQL container..."
docker run -d \
  --name $DB_CONTAINER \
  -e POSTGRES_DB=$DB_NAME \
  -e POSTGRES_USER=$DB_USER \
  -e POSTGRES_PASSWORD=$DB_PASS \
  -p $DB_PORT:5432 \
  postgres:15-alpine

echo ""
echo "⏳ Step 3: Waiting for PostgreSQL to be ready..."
sleep 4

echo ""
echo "📊 Step 4: Create tables and insert sample data..."

docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME << 'EOF'

-- ─── EMPLOYEES TABLE ──────────────────────────────────────
CREATE TABLE employees (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    department VARCHAR(50)  NOT NULL,
    role       VARCHAR(100) NOT NULL,
    salary     NUMERIC(10,2),
    hire_date  DATE,
    email      VARCHAR(150)
);

INSERT INTO employees (name, department, role, salary, hire_date, email) VALUES
  ('Alice Johnson',  'Engineering',  'Senior Software Engineer', 120000, '2021-03-15', 'alice@company.com'),
  ('Bob Smith',      'Engineering',  'Backend Developer',        95000,  '2022-07-01', 'bob@company.com'),
  ('Carol White',    'Product',      'Product Manager',          110000, '2020-11-20', 'carol@company.com'),
  ('David Lee',      'Design',       'UX Designer',             88000,  '2023-01-10', 'david@company.com'),
  ('Eva Martinez',   'Engineering',  'DevOps Engineer',         105000, '2021-09-05', 'eva@company.com'),
  ('Frank Brown',    'Data',         'Data Scientist',           115000, '2022-04-18', 'frank@company.com'),
  ('Grace Kim',      'Product',      'Product Analyst',          82000,  '2023-06-01', 'grace@company.com'),
  ('Henry Chen',     'Engineering',  'Frontend Developer',       92000,  '2022-10-15', 'henry@company.com');

-- ─── PROJECTS TABLE ───────────────────────────────────────
CREATE TABLE projects (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(150) NOT NULL,
    status      VARCHAR(30)  NOT NULL,  -- active, completed, on-hold
    budget      NUMERIC(12,2),
    start_date  DATE,
    end_date    DATE,
    owner_id    INT REFERENCES employees(id)
);

INSERT INTO projects (name, status, budget, start_date, end_date, owner_id) VALUES
  ('AI Customer Support Bot',    'active',    250000, '2024-01-01', '2024-09-30', 1),
  ('Data Pipeline Redesign',     'active',    180000, '2024-02-15', '2024-08-15', 6),
  ('Mobile App v2.0',            'completed', 320000, '2023-06-01', '2024-01-31', 3),
  ('Internal DevOps Automation', 'on-hold',   95000,  '2024-03-01', NULL,         5),
  ('Recommendation Engine',      'active',    400000, '2024-04-01', '2025-01-31', 6);

-- ─── TASKS TABLE ──────────────────────────────────────────
CREATE TABLE tasks (
    id          SERIAL PRIMARY KEY,
    project_id  INT REFERENCES projects(id),
    title       VARCHAR(200) NOT NULL,
    status      VARCHAR(20)  NOT NULL,  -- todo, in-progress, done
    assignee_id INT REFERENCES employees(id),
    priority    VARCHAR(10)  DEFAULT 'medium',
    due_date    DATE
);

INSERT INTO tasks (project_id, title, status, assignee_id, priority, due_date) VALUES
  (1, 'Design conversation flow',    'done',        1, 'high',   '2024-02-15'),
  (1, 'Build NLP pipeline',          'in-progress', 2, 'high',   '2024-05-30'),
  (1, 'Integrate with CRM',          'todo',        5, 'medium', '2024-07-15'),
  (2, 'Audit existing pipelines',    'done',        6, 'high',   '2024-03-01'),
  (2, 'Migrate to Apache Spark',     'in-progress', 6, 'high',   '2024-06-30'),
  (5, 'Collect training dataset',    'done',        6, 'high',   '2024-04-30'),
  (5, 'Train baseline model',        'in-progress', 6, 'medium', '2024-07-01'),
  (5, 'Deploy to staging',           'todo',        5, 'low',    '2024-09-01');

EOF

echo ""
echo "✅ Database setup complete!"
echo ""
echo "   Container : $DB_CONTAINER"
echo "   Database  : $DB_NAME"
echo "   User      : $DB_USER"
echo "   Password  : $DB_PASS"
echo "   Port      : $DB_PORT"
echo ""
echo "📝 Set env variables and start the MCP server:"
echo ""
echo "   export DB_HOST=localhost"
echo "   export DB_PORT=5432"
echo "   export DB_NAME=$DB_NAME"
echo "   export DB_USER=$DB_USER"
echo "   export DB_PASS=$DB_PASS"
echo "   python database_mcp_server.py"
echo ""
echo "🛑 To stop and remove the container later:"
echo "   docker rm -f $DB_CONTAINER"