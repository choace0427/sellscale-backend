#!/usr/bin/env python

import os
import subprocess
import sys
args = sys.argv

table_name = args[1]
column_name = args[2]
new_value = args[3]

os.chdir('./migrations')
result = subprocess.run(f'alembic revision -m "Autogen - Added {new_value} to enum column {column_name} in table {table_name}"', shell=True, capture_output=True)

output = result.stdout.decode()
file_name = output.split('/versions/')[1].split('.py')[0]

insert_import = f'from sqlalchemy import Table, MetaData\n'
insert_upgrade = f'''
    # Bind the engine and create a MetaData object
    bind = op.get_bind()
    metadata = MetaData(bind=bind)

    # Reflect the table that contains the Enum column
    table = Table('{table_name}', metadata, autoload=True)

    # Get the Enum column and its Enum type
    enum_column = table.columns['{column_name}']
    enum_type = enum_column.type

    # Add the new value to the existing values
    new_values = list(enum_type.enums) + ['{new_value}']

    # Perform the upgrade operation
    op.execute(f"""
        BEGIN;
            ALTER TYPE {{enum_type.name}} RENAME TO {{enum_type.name}}_temp;
            CREATE TYPE {{enum_type.name}} AS ENUM ('{{"', '".join(new_values)}}');
            ALTER TABLE {{table.name}} ALTER COLUMN {{enum_column.name}} TYPE {{enum_type.name}} USING {{enum_column.name}}::text::{{enum_type.name}};
            DROP TYPE {{enum_type.name}}_temp;
        COMMIT;
    """)
'''
insert_downgrade = f'''
    # Bind the engine and create a MetaData object
    bind = op.get_bind()
    metadata = MetaData(bind=bind)

    # Reflect the table that contains the Enum column
    table = Table('{table_name}', metadata, autoload=True)

    # Get the Enum column and its Enum type
    enum_column = table.columns['{column_name}']
    enum_type = enum_column.type

    # Get the existing values and remove the new value
    existing_values = [v for v in enum_type.enums if v != '{new_value}']

    # Perform the downgrade operation
    try:
        op.execute(f"""
            BEGIN;
                ALTER TYPE {{enum_type.name}} RENAME TO {{enum_type.name}}_temp;
                CREATE TYPE {{enum_type.name}} AS ENUM ('{{"', '".join(existing_values)}}');
                ALTER TABLE {{table.name}} ALTER COLUMN {{enum_column.name}} TYPE {{enum_type.name}} USING {{enum_column.name}}::text::{{enum_type.name}};
                DROP TYPE {{enum_type.name}}_temp;
            COMMIT;
        """)
    except Exception as e:
        print('Failed to execute downgrade, does a row currently use this enum?')
        print(e)
'''

# Read the contents of the file into a list of lines
with open(f'./versions/{file_name}.py', 'r') as f:
  file_lines = f.readlines()

# Find the line containing "def upgrade():"
for i, line in enumerate(file_lines):
  if line.strip() == 'from alembic import op':
    file_lines.insert(i + 1, insert_import)
  elif line.strip() == 'def upgrade():':
    file_lines.insert(i + 1, insert_upgrade)
  elif line.strip() == 'def downgrade():':
    file_lines.insert(i + 1, insert_downgrade)

# Write the modified list of lines back to the file
with open(f'./versions/{file_name}.py', 'w') as f:
    f.writelines(file_lines)

print(f'Complete!\nPlease confirm by checking: ./migrations/versions/{file_name}.py')