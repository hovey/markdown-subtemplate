import os
import datetime
from typing import Dict, Optional, Any, List

from markdown_subtemplate import caching as __caching
from markdown_subtemplate.infrastructure import markdown_transformer
from markdown_subtemplate.exceptions import ArgumentExpectedException, TemplateNotFoundException
from markdown_subtemplate import logging as __logging

template_folder: Optional[str] = None


# noinspection DuplicatedCode
def get_page(template_path: str, data: Dict[str, Any]) -> str:
    cache = __caching.get_cache()
    log = __logging.get_log()

    key = f'name: {template_path}, data: {data}'
    entry = cache.get_html(key)
    if entry:
        log.trace(f"CACHE HIT: Reusing {template_path} from HTML cache.")
        return entry.contents

    t0 = datetime.datetime.now()

    # Get the markdown with imports and substitutions
    markdown = get_markdown(template_path, data)
    # Convert markdown to HTML
    html = get_html(markdown)

    cache.add_html(key, key, str(data), html)

    dt = datetime.datetime.now() - t0

    msg = f"Created contents for {template_path}:{data} in {int(dt.total_seconds() * 1000):,} ms."
    log.info(f"GENERATING HTML: {msg}")

    return html


def get_html(markdown_text: str, unsafe_data=False) -> str:
    return markdown_transformer.transform(markdown_text, unsafe_data)


# noinspection DuplicatedCode
def get_markdown(template_path: str, data: Dict[str, Any]) -> str:
    cache = __caching.get_cache()
    log = __logging.get_log()

    key = f'name: {template_path}, data: {data}'
    entry = cache.get_markdown(key)
    if entry:
        log.trace(f"CACHE HIT: Reusing {template_path} from MARKDOWN cache.")
        return entry.contents

    t0 = datetime.datetime.now()

    text = load_markdown_contents(template_path, data)
    cache.add_markdown(key, key, str(data), text)

    dt = datetime.datetime.now() - t0

    msg = f"Created contents for {template_path}:{data} in {int(dt.total_seconds() * 1000):,} ms."
    log.trace(f"GENERATING MARKDOWN: {msg}")

    return text


def load_markdown_contents(template_path: str, data: Dict[str, Any]) -> str:
    log = __logging.get_log()
    log.verbose(f"Loading markdown template: {template_path}")

    landing_md = get_page_markdown(template_path)

    lines = landing_md.split('\n')
    lines = process_imports(lines)
    lines = process_variables(lines, data)

    final_markdown = "\n".join(lines).strip()

    return final_markdown


def get_page_markdown(template_path: str) -> Optional[str]:
    if not template_path or not template_path.strip():
        raise TemplateNotFoundException("No template file specified: template_path=''.")

    file_name = os.path.basename(template_path)
    file_parts = os.path.dirname(template_path).split(os.path.sep)
    folder = get_folder(file_parts)
    full_file = os.path.join(folder, file_name).lower()

    if not os.path.exists(full_file):
        raise TemplateNotFoundException(full_file)

    with open(full_file, 'r', encoding='utf-8') as fin:
        return fin.read()


def get_folder(path_parts: List[str]) -> str:
    if not path_parts:
        raise ArgumentExpectedException('path_parts')

    path_parts = [
        p.strip().strip('/').strip('\\').lower()
        for p in path_parts
    ]
    parent_folder = os.path.abspath(template_folder)
    folder = os.path.join(parent_folder, *path_parts)
    return folder


def get_shared_markdown(import_name: str) -> Optional[str]:
    if not import_name or not import_name.strip():
        raise ArgumentExpectedException('import_name')

    folder = get_folder(['_shared'])
    file = os.path.join(folder, import_name.strip().lower() + '.md')

    if not os.path.exists(file):
        raise TemplateNotFoundException(file)

    with open(file, 'r', encoding='utf-8') as fin:
        return fin.read()


def process_imports(lines: List[str]) -> List[str]:
    log = __logging.get_log()
    line_data = list(lines)

    for idx, line in enumerate(line_data):
        if not line.strip().startswith('[IMPORT '):
            continue

        import_statement = line.strip()
        import_name = import_statement \
            .replace('[IMPORT ', '') \
            .replace(']', '') \
            .strip()

        imported_file = os.path.join('_shared', import_name + '.md')
        log.verbose(f"Loading import: {imported_file}...")

        markdown = get_page_markdown(imported_file)
        markdown_lines = markdown.split('\n')
        line_data = line_data[:idx] + markdown_lines + line_data[idx + 1:]

        return process_imports(line_data)

    return line_data


def process_variables(lines: List[str], data: Dict[str, Any]) -> List[str]:
    log = __logging.get_log()

    line_data = list(lines)
    keys = list(data.keys())
    key_placeholders = {
        key: f"${key.strip().upper()}$"
        for key in keys
        if key and isinstance(key, str)
    }

    for idx, line in enumerate(line_data):
        for key in keys:
            if key_placeholders[key] not in line:
                continue

            log.verbose(f"Replacing {key_placeholders[key]} in:\n{line}")
            line_data[idx] = line.replace(key_placeholders[key], str(data[key]))

    return line_data
