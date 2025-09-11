#!/usr/bin/env python3
"""
Script to fix Azure SQL parameterization issues in app_v2.py
Replaces hardcoded %s placeholders with get_param_placeholder() function calls
"""

import re
import os

def fix_azure_sql_parameterization():
    """Fix all hardcoded %s parameterization in app_v2.py"""
    
    file_path = r"C:\Users\ccayo\OneDrive\Desktop\Warehance Returns\web\app_v2.py"
    
    # Read the current file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Patterns to fix (excluding comments and the function definition itself)
    fixes = [
        # Simple parameter replacements in queries
        {
            'pattern': r'query\s*\+=\s*["\']([^"\']*)\s+%s([^"\']*)["\']',
            'replacement': lambda m: f'placeholder = get_param_placeholder()\n        query += f"{m.group(1)} {{placeholder}}{m.group(2)}"',
            'description': 'Fix query parameter concatenation'
        },
        # WHERE clauses with %s
        {
            'pattern': r'WHERE\s+[^"\']*\s*=\s*%s',
            'replacement': lambda m: m.group(0).replace('%s', '{placeholder}'),
            'description': 'Fix WHERE clause parameters'
        },
        # Direct cursor.execute with %s (excluding function definition comments)
        {
            'pattern': r'cursor\.execute\(\s*["\']([^"\']*%s[^"\']*)["\']',
            'replacement': lambda m: f'cursor.execute(f"{m.group(1).replace("%s", "{get_param_placeholder()}")}"',
            'description': 'Fix direct cursor.execute statements'
        }
    ]
    
    # Manual fixes for specific problematic lines
    manual_fixes = [
        # search_returns function fixes
        {
            'old': '        query += " AND r.client_id = %s"',
            'new': '        placeholder = get_param_placeholder()\n        query += f" AND r.client_id = {placeholder}"'
        },
        {
            'old': '        query += " AND (r.tracking_number LIKE %s OR r.id LIKE %s OR c.name LIKE %s)"',
            'new': '        placeholder = get_param_placeholder()\n        query += f" AND (r.tracking_number LIKE {placeholder} OR r.id LIKE {placeholder} OR c.name LIKE {placeholder})"'
        },
        {
            'old': '        query += " ORDER BY r.created_at DESC LIMIT %s OFFSET %s"',
            'new': '        placeholder = get_param_placeholder()\n        query += f" ORDER BY r.created_at DESC LIMIT {placeholder} OFFSET {placeholder}"'
        },
        # return details fixes  
        {
            'old': '                WHERE ri.return_id = %s',
            'new': f'                WHERE ri.return_id = {{get_param_placeholder()}}'
        },
        {
            'old': '        WHERE r.id = %s',
            'new': f'        WHERE r.id = {{get_param_placeholder()}}'
        },
        # sync function fixes - the big one
        {
            'old': '                        cursor.execute("SELECT COUNT(*) as count FROM returns WHERE id = %s", (return_id,))',
            'new': '                        placeholder = get_param_placeholder()\n                        cursor.execute(f"SELECT COUNT(*) as count FROM returns WHERE id = {placeholder}", (return_id,))'
        },
        {
            'old': '                                WHERE id = %s',
            'new': '                                WHERE id = {get_param_placeholder()}'
        },
        {
            'old': '                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
            'new': '                                VALUES ({", ".join(["{get_param_placeholder()}" for _ in range(23)])})'
        }
    ]
    
    # Apply manual fixes
    changes_made = 0
    for fix in manual_fixes:
        if fix['old'] in content:
            content = content.replace(fix['old'], fix['new'])
            changes_made += 1
            print(f"Fixed: {fix['old'][:50]}...")
    
    # Special handling for the sync function's massive INSERT statements
    # Find and fix the big INSERT statements with many %s placeholders
    insert_patterns = [
        r'VALUES\s*\([%s,\s]+\)',  # Pattern for VALUES (%s, %s, %s, ...)
    ]
    
    for pattern in insert_patterns:
        matches = re.finditer(pattern, content)
        for match in matches:
            original_values = match.group(0)
            # Count the number of %s placeholders
            param_count = original_values.count('%s')
            if param_count > 0:
                # Replace with parameterized version
                new_values = f'VALUES ({", ".join(["{get_param_placeholder()}" for _ in range(param_count)])})'
                content = content.replace(original_values, new_values)
                changes_made += 1
                print(f"Fixed INSERT with {param_count} parameters")
    
    # Write the fixed content if changes were made
    if changes_made > 0:
        # Create backup
        backup_path = file_path + '.backup'
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(original_content)
        print(f"Created backup: {backup_path}")
        
        # Write fixed version
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Applied {changes_made} fixes to {file_path}")
        return True
    else:
        print("No changes needed")
        return False

if __name__ == '__main__':
    fix_azure_sql_parameterization()