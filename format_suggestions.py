import json

def generate_md():
    with open('ruff_suggestions.json', 'r') as f:
        errors = json.load(f)

    with open('suggestions.md', 'w', encoding='utf-8') as f:

        for i, error in enumerate(errors, 1):
            desc = error.get('message', 'No description')
            filepath = error.get('filename', '').replace('/app/', '')
            row = error.get('location', {}).get('row', '?')
            col = error.get('location', {}).get('column', '?')
            code = error.get('code', 'Unknown')

            # extract code context
            try:
                with open(filepath, 'r') as source_file:
                    lines = source_file.readlines()
                    start_line = max(0, row - 3)
                    end_line = min(len(lines), row + 3)
                    context_lines = lines[start_line:end_line]
                    # Put a pointer to the exact line
                    for j in range(len(context_lines)):
                        if start_line + j + 1 == row:
                            context_lines[j] = "-> " + context_lines[j]
                        else:
                            context_lines[j] = "   " + context_lines[j]
                    context = "".join(context_lines)
            except Exception:
                context = "Code context not available."

            rationale = f"Rule {code}. Fixing this improves code quality, readability, and prevents potential runtime errors."

            f.write(f"DESCRIPTION -> {desc}\n")
            f.write(f"LOCATION -> {filepath}:{row}:{col}\n")
            f.write(f"RATIONALE -> {rationale}\n")
            f.write(f"CODE CONTEXT -> \n```python\n{context}\n```\n\n")

if __name__ == '__main__':
    generate_md()
