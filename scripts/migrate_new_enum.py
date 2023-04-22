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
file_name = output.replace('\n', '').replace(' ', '').split('/versions/')[1].split('.py')[0]

insert_import = f'from sqlalchemy import Table, MetaData\n'
insert_upgrade = f'''
    # Get the name of the enum type associated with the column
    result = op.get_bind().execute("SELECT udt_name FROM information_schema.columns WHERE table_name = '{table_name}' AND column_name = '{column_name}'").fetchone()
    enum_type_name = result[0]
    
    # Get the current values of the enum type
    current_values = op.get_bind().execute("SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = '%s')" % enum_type_name).fetchall()
    values = [value[0] for value in current_values]
    
    # Add the new value to the enum type
    values.append('{new_value}')
    op.execute("ALTER TYPE %s ADD VALUE '%s'" % (enum_type_name, '{new_value}'))
'''
insert_downgrade = f'''
    # Get the name of the enum type associated with the column
    result = op.get_bind().execute("SELECT udt_name FROM information_schema.columns WHERE table_name = '{table_name}' AND column_name = '{column_name}'").fetchone()
    enum_type_name = result[0]
    
    # Remove the new value from the enum type
    op.execute("ALTER TYPE %s DROP VALUE '{new_value}'" % enum_type_name)
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