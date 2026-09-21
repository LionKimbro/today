"""The small text machine for TkMarkup panels."""

import re
from uuid import UUID, uuid4


ITEM_PATTERN = re.compile(r"^(\[ |\[>|\[x|\[-)\](?: ?)(.*)$")
PROMPT_PATTERN = re.compile(r"^>>>(?: ?)(.*)$")
GUID_PATTERN = re.compile(r"\s*(\{[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\})$")


def is_valid_guid(text):
    if not isinstance(text, str) or not re.fullmatch(r"\{[0-9a-f-]{36}\}", text):
        return False
    try:
        return str(UUID(text[1:-1], version=4)) == text[1:-1]
    except ValueError:
        return False


def make_guid():
    return "{" + str(uuid4()) + "}"


def split_final_guid(text):
    match = GUID_PATTERN.search(text)
    if match is None or not is_valid_guid(match.group(1)):
        return text, None
    return text[:match.start()].rstrip(), match.group(1)


def parse_text(text):
    lines = text.splitlines()
    elements = []
    paragraph_lines = []
    paragraph_start = None

    def finish_paragraph():
        nonlocal paragraph_lines, paragraph_start
        if paragraph_lines:
            elements.append({
                "type": "PARAGRAPH", "line-start": paragraph_start,
                "line-end": paragraph_start + len(paragraph_lines),
                "text": " ".join(line.strip() for line in paragraph_lines),
            })
        paragraph_lines = []
        paragraph_start = None

    for line_index, line in enumerate(lines):
        item = ITEM_PATTERN.match(line)
        prompt = PROMPT_PATTERN.match(line)
        if line == "":
            finish_paragraph()
            elements.append({"type": "BLANK", "line-index": line_index})
        elif line.startswith("# "):
            finish_paragraph()
            elements.append({"type": "HEADING", "line-index": line_index, "text": line[2:]})
        elif item is not None:
            finish_paragraph()
            title, guid = split_final_guid(item.group(2))
            elements.append({
                "type": "ITEM", "line-index": line_index,
                "marker": item.group(1), "title": title, "guid": guid,
            })
        elif prompt is not None:
            finish_paragraph()
            trailing, guid = split_final_guid(prompt.group(1))
            elements.append({
                "type": "PROMPT", "line-index": line_index,
                "trailing": trailing, "guid": guid,
            })
        else:
            if not paragraph_lines:
                paragraph_start = line_index
            paragraph_lines.append(line)
    finish_paragraph()
    return elements


def normalize_text(text):
    lines = text.splitlines(keepends=True)
    seen = set()
    for element in parse_text(text):
        if element["type"] not in {"ITEM", "PROMPT"}:
            continue
        line_index = element["line-index"]
        guid = element["guid"]
        if guid is not None and guid not in seen:
            seen.add(guid)
            continue
        new_guid = make_guid()
        seen.add(new_guid)
        ending = "\n" if lines[line_index].endswith("\n") else ""
        line = lines[line_index][:-1] if ending else lines[line_index]
        lines[line_index] = f"{line} {new_guid}{ending}"
    return "".join(lines)


def find_element(text, guid, element_type):
    for element in parse_text(text):
        if element["type"] == element_type and element.get("guid") == guid:
            return element
    return None


def replace_line(lines, line_index, new_line):
    ending = "\n" if lines[line_index].endswith("\n") else ""
    lines[line_index] = new_line + ending
    return "".join(lines)


def add_item(text, prompt_guid, item_text):
    item_text = item_text.strip()
    prompt = find_element(text, prompt_guid, "PROMPT")
    if prompt is None or not item_text:
        return text
    lines = text.splitlines(keepends=True)
    line_index = prompt["line-index"]
    lines.insert(line_index, f"[ ] {item_text} {make_guid()}\n")
    return "".join(lines)


def delete_item(text, item_guid):
    item = find_element(text, item_guid, "ITEM")
    if item is None:
        return text
    lines = text.splitlines(keepends=True)
    lines.pop(item["line-index"])
    return "".join(lines)


def cycle_item(text, item_guid):
    item = find_element(text, item_guid, "ITEM")
    if item is None or item["marker"] == "[-":
        return text
    marker = {"[ ": "[>", "[>": "[x", "[x": "[ "}[item["marker"]]
    lines = text.splitlines(keepends=True)
    return replace_line(lines, item["line-index"], marker + "]" + lines[item["line-index"]][3:].rstrip("\n"))


def move_item(text, item_guid, direction):
    if direction not in {-1, 1}:
        return text
    item = find_element(text, item_guid, "ITEM")
    if item is None:
        return text
    elements_by_line = {element.get("line-index"): element for element in parse_text(text)}
    destination = item["line-index"] + direction
    if elements_by_line.get(destination, {}).get("type") != "ITEM":
        return text
    lines = text.splitlines(keepends=True)
    lines[item["line-index"]], lines[destination] = lines[destination], lines[item["line-index"]]
    return "".join(lines)
