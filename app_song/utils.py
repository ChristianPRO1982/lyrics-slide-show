def check_max_lines(text, max_lines):
    try:
        lines = text.splitlines()
        if len(lines) > max_lines:
            return True
        return False
    except Exception as e:
        return False

def check_max_characters_for_a_line(text, max_characters_for_a_line):
    try:
        lines = text.splitlines()
        if any(len(line) > max_characters_for_a_line for line in lines):
            return True
        return False
    except Exception as e:
        return False