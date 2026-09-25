from pathlib import Path
import shutil
import re


# =========================
# Настройки
# =========================

SOURCE_DIR = Path("Source")
OUTPUT_DIR = Path("Generated")

FTL_FILE = (
    OUTPUT_DIR
    / "Locale"
    / "ru-RU"
    / "1"
    / "generated.ftl"
)


# =========================
# Обычные поля локализации
# =========================

LOCALIZE_FIELDS = {
    "name",
    "description",
}


# =========================
# Дополнительные поля
# =========================

FORCE_LOCALIZE_FIELDS = {
    "unit",
    "toolName",
    "text",
    "sentence",
    "message",
    "locMessage",
    "defaultText",
    "jobTitle",
    "nameLocId",
    "title",
    "defaultKeyPhrase",
    "briefingText",
}


# =========================
# Префикс ключей
# =========================

KEY_PREFIX = "lazyftl"


# =========================
# Генерация ключей
# =========================

ftl_entries = []
counter = 1


def generate_key():

    global counter

    key = f"{KEY_PREFIX}-{counter}"

    counter += 1

    return key


# =========================
# Очистка YAML значения
# =========================

def clean_yaml_value(value):

    value = value.strip()

    if (
        len(value) >= 2
        and value[0] == value[-1]
        and value[0] in ('"', "'")
    ):
        value = value[1:-1]

    return value


# =========================
# Работа с \n
# =========================

def split_newlines(value):

    return value.replace(
        "\\n",
        "\n"
    ).split("\n")


# =========================
# FTL обычное значение
# =========================

def make_ftl_value(
    key,
    value
):

    lines = split_newlines(value)

    if len(lines) == 1:

        return (
            f"{key} = "
            f"{lines[0]}"
        )

    result = [
        f"{key} ="
    ]

    for line in lines:

        result.append(
            f"    {line}"
        )

    return "\n".join(result)


# =========================
# FTL атрибут
# =========================

def make_ftl_attribute(
    attribute,
    value
):

    lines = split_newlines(value)

    if len(lines) == 1:

        return (
            f"    .{attribute} = "
            f"{lines[0]}"
        )

    result = [
        f"    .{attribute} ="
    ]

    for line in lines:

        result.append(
            f"        {line}"
        )

    return "\n".join(result)


# =========================
# Проверка локализации
# =========================

def should_localize(value):

    if not isinstance(value, str):
        return False

    if not value.strip():
        return False

    if value.startswith(
        KEY_PREFIX + "-"
    ):
        return False

    if value.startswith("ent-"):
        return False

    return True


# =========================
# Поиск родителей
# =========================

def find_parents(
    block_lines
):

    parents = []

    # parent: SomeEntity
    scalar_pattern = re.compile(
        r'^\s*parent:\s*([^\s#]+)'
    )

    # Элементы списка:
    #
    # parent:
    # - SomeEntity
    # - OtherEntity
    #
    list_pattern = re.compile(
        r'^\s*-\s*([^\s#]+)'
    )

    parent_started = False

    for line in block_lines:

        clean_line = line.rstrip(
            "\r\n"
        )

        # -------------------------
        # parent: Something
        # -------------------------

        match = scalar_pattern.match(
            clean_line
        )

        if match:

            parents.append(
                clean_yaml_value(
                    match.group(1)
                )
            )

            parent_started = False

            continue


        # -------------------------
        # parent:
        # -------------------------

        if re.match(
            r'^\s*parent:\s*(?:#.*)?$',
            clean_line
        ):

            parent_started = True

            continue


        # -------------------------
        # Элементы списка parent
        # -------------------------

        if parent_started:

            match = list_pattern.match(
                clean_line
            )

            if match:

                parents.append(
                    clean_yaml_value(
                        match.group(1)
                    )
                )

                continue


            # Если началась другая секция
            if clean_line.strip():

                parent_started = False


    return parents


# =========================
# Сбор информации об Entity
# =========================

def collect_entity_info(
    block_lines
):

    type_pattern = re.compile(
        r'^\s*-\s*type:\s*([^\s#]+)'
    )

    id_pattern = re.compile(
        r'^\s*id:\s*([^\s#]+)'
    )

    field_pattern = re.compile(
        r'^\s*(name|description):\s*(.+?)\s*$'
    )

    prototype_type = None
    prototype_id = None

    name = None
    description = None


    # =========================
    # type + id
    # =========================

    for line in block_lines:

        clean_line = line.rstrip(
            "\r\n"
        )


        match = type_pattern.match(
            clean_line
        )

        if match:

            prototype_type = clean_yaml_value(
                match.group(1)
            )

            continue


        match = id_pattern.match(
            clean_line
        )

        if match:

            prototype_id = clean_yaml_value(
                match.group(1)
            )

            continue


    # Не Entity
    if prototype_type != "entity":

        return None


    if prototype_id is None:

        return None


    # =========================
    # name + description
    # =========================

    for line in block_lines:

        clean_line = line.rstrip(
            "\r\n"
        )


        match = field_pattern.match(
            clean_line
        )

        if not match:

            continue


        field = match.group(1)

        value = clean_yaml_value(
            match.group(2)
        )


        if field == "name":

            if should_localize(value):

                name = value


        elif field == "description":

            if should_localize(value):

                description = value


    # =========================
    # parents
    # =========================

    parents = find_parents(
        block_lines
    )


    return {
        "id": prototype_id,
        "name": name,
        "description": description,
        "parents": parents,
    }


# =========================
# Поиск эффективной локализации
# =========================
#
# Например:
#
# Child
#   ↓
# Parent
#   ↓
# Base
#
# Если Child не имеет name,
# но Base имеет name,
# функция найдёт Base.
#
# Возвращает:
#
# (entity_id, value)
#
# Например:
#
# ("MaterialTimedSpawnerSteelOre", "экстрактор...")
#

def resolve_entity_field(
    entity_id,
    field,
    entity_database,
    visited=None
):

    if visited is None:

        visited = set()


    # Защита от циклического
    # наследования

    if entity_id in visited:

        return None


    visited.add(
        entity_id
    )


    entity = entity_database.get(
        entity_id
    )


    if entity is None:

        return None


    # =========================
    # Собственное значение
    # =========================

    own_value = entity.get(
        field
    )


    if own_value is not None:

        return (
            entity_id,
            own_value
        )


    # =========================
    # Ищем у родителей
    # =========================

    for parent_id in entity.get(
        "parents",
        []
    ):

        result = resolve_entity_field(
            parent_id,
            field,
            entity_database,
            visited.copy()
        )


        if result is not None:

            return result


    return None


# =========================
# Обработка prototype
# =========================

def process_block(
    block_lines,
    entity_database
):

    global ftl_entries

    if not block_lines:

        return []


    # =========================
    # Регулярки
    # =========================

    type_pattern = re.compile(
        r'^\s*-\s*type:\s*([^\s#]+)'
    )

    id_pattern = re.compile(
        r'^\s*id:\s*([^\s#]+)'
    )

    field_pattern = re.compile(
        r'^(\s*)([\w-]+):\s*(.+?)\s*$'
    )


    prototype_type = None
    prototype_id = None


    # =========================
    # type + id
    # =========================

    for line in block_lines:

        clean_line = line.rstrip(
            "\r\n"
        )


        match = type_pattern.match(
            clean_line
        )

        if match:

            prototype_type = clean_yaml_value(
                match.group(1)
            )

            continue


        match = id_pattern.match(
            clean_line
        )

        if match:

            prototype_id = clean_yaml_value(
                match.group(1)
            )

            continue


    is_entity = (
        prototype_type == "entity"
        and prototype_id is not None
    )


    # =========================
    # Entity data
    # =========================

    entity_data = None

    if is_entity:

        entity_data = entity_database.get(
            prototype_id
        )


    entity_name = None
    entity_description = None


    # =========================
    # Второй проход
    # =========================

    processed_lines = []


    for line in block_lines:

        clean_line = line.rstrip(
            "\r\n"
        )


        newline = (
            "\r\n"
            if line.endswith("\r\n")
            else "\n"
        )


        match = field_pattern.match(
            clean_line
        )


        if not match:

            processed_lines.append(
                line
            )

            continue


        prefix = match.group(1)
        field = match.group(2)
        value = match.group(3)


        # =========================
        # Нужно ли локализировать
        # =========================

        if (
            field not in LOCALIZE_FIELDS
            and
            field not in FORCE_LOCALIZE_FIELDS
        ):

            processed_lines.append(
                line
            )

            continue


        value = clean_yaml_value(
            value
        )


        # Уже локализировано
        if not should_localize(value):

            processed_lines.append(
                line
            )

            continue


        # =========================
        # ENTITY
        # =========================

        if is_entity:

            entity_key = (
                f"ent-{prototype_id}"
            )


            # -------------------------
            # NAME
            # -------------------------

            if field == "name":

                entity_name = value


                processed_lines.append(
                    f"{prefix}"
                    f"name: "
                    f"{entity_key}"
                    f"{newline}"
                )

                continue


            # -------------------------
            # DESCRIPTION
            # -------------------------

            if field == "description":

                entity_description = value


                processed_lines.append(
                    f"{prefix}"
                    f"description: "
                    f"{entity_key}.desc"
                    f"{newline}"
                )

                continue


        # =========================
        # Обычное поле
        # =========================

        key = generate_key()


        ftl_entries.append(
            make_ftl_value(
                key,
                value
            )
        )


        processed_lines.append(
            f"{prefix}"
            f"{field}: "
            f"{key}"
            f"{newline}"
        )


    # =========================
    # Entity localization
    # =========================

    if is_entity:

        entity_key = (
            f"ent-{prototype_id}"
        )


        # =========================
        # Определяем эффективные
        # name + description
        # =========================

        name_result = (
            resolve_entity_field(
                prototype_id,
                "name",
                entity_database
            )
        )


        description_result = (
            resolve_entity_field(
                prototype_id,
                "description",
                entity_database
            )
        )


        # =========================
        # Вообще нечего
        # локализировать
        # =========================

        if (
            name_result is None
            and
            description_result is None
        ):

            return processed_lines


        # =========================
        # NAME
        # =========================

        if entity_name is not None:

            name_part = make_ftl_value(
                entity_key,
                entity_name
            )

        elif name_result is not None:

            source_id = name_result[0]

            name_part = (
                f"{entity_key} = "
                f"{{ ent-{source_id} }}"
            )

        else:

            # Если есть только description,
            # сообщение всё равно должно иметь
            # основное значение.
            #
            # Пустой message нельзя оставлять.

            name_part = (
                f"{entity_key} = "
                f"{{ ent-{entity_database[prototype_id]['parents'][0]} }}"
                if entity_database[prototype_id].get("parents")
                else
                f"{entity_key} ="
            )


        # =========================
        # DESCRIPTION
        # =========================

        if entity_description is not None:

            desc_part = make_ftl_attribute(
                "desc",
                entity_description
            )

        elif description_result is not None:

            source_id = description_result[0]

            desc_part = (
                f"    .desc = "
                f"{{ ent-{source_id}.desc }}"
            )

        else:

            desc_part = None


        # =========================
        # Сборка
        # =========================

        entity_ftl = name_part


        if desc_part is not None:

            entity_ftl += (
                "\n"
                + desc_part
            )


        ftl_entries.append(
            entity_ftl
        )


    return processed_lines


# =========================
# Чтение YAML-блоков
# =========================

def read_yaml_blocks(
    source_file
):

    lines = source_file.read_text(
        encoding="utf-8"
    ).splitlines(
        keepends=True
    )


    blocks = []

    current_block = []


    prototype_start = re.compile(
        r'^\s*-\s*type:\s*'
    )


    for line in lines:

        if prototype_start.match(line):

            if current_block:

                blocks.append(
                    current_block
                )


            current_block = [
                line
            ]

        else:

            current_block.append(
                line
            )


    if current_block:

        blocks.append(
            current_block
        )


    return blocks


# =========================
# Обработка YAML-файла
# =========================

def process_yaml_file(
    source_file,
    output_file,
    entity_database
):

    lines = source_file.read_text(
        encoding="utf-8"
    ).splitlines(
        keepends=True
    )


    processed_lines = []

    current_block = []


    prototype_start = re.compile(
        r'^\s*-\s*type:\s*'
    )


    for line in lines:

        if prototype_start.match(line):

            if current_block:

                processed_lines.extend(
                    process_block(
                        current_block,
                        entity_database
                    )
                )


            current_block = [
                line
            ]

        else:

            current_block.append(
                line
            )


    if current_block:

        processed_lines.extend(
            process_block(
                current_block,
                entity_database
            )
        )


    output_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    output_file.write_text(
        "".join(processed_lines),
        encoding="utf-8"
    )


# =========================
# MAIN
# =========================

def main():

    global ftl_entries
    global counter


    print(
        "=== FTL Generator ==="
    )


    # =========================
    # Source
    # =========================

    if not SOURCE_DIR.exists():

        print(
            f"ОШИБКА: папка "
            f"'{SOURCE_DIR}' не найдена."
        )

        return


    # =========================
    # Generated
    # =========================

    if OUTPUT_DIR.exists():

        print(
            f"Удаление старой папки "
            f"'{OUTPUT_DIR}'..."
        )

        shutil.rmtree(
            OUTPUT_DIR
        )


    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    # =========================
    # Сброс
    # =========================

    ftl_entries = []
    counter = 1


    # =========================
    # YAML-файлы
    # =========================

    yaml_files = list(
        SOURCE_DIR.rglob("*.yml")
    )

    yaml_files += list(
        SOURCE_DIR.rglob("*.yaml")
    )


    print(
        f"Найдено YAML файлов: "
        f"{len(yaml_files)}"
    )


    # =========================
    # Первый проход
    #
    # Собираем ВСЕ Entity
    # =========================

    entity_database = {}


    for source_file in yaml_files:

        blocks = read_yaml_blocks(
            source_file
        )


        for block in blocks:

            entity_data = (
                collect_entity_info(
                    block
                )
            )


            if entity_data:

                entity_database[
                    entity_data["id"]
                ] = entity_data


    print(
        f"Найдено Entity: "
        f"{len(entity_database)}"
    )


    # =========================
    # Второй проход
    #
    # Генерируем YAML + FTL
    # =========================

    for source_file in yaml_files:

        relative_path = (
            source_file.relative_to(
                SOURCE_DIR
            )
        )


        output_file = (
            OUTPUT_DIR
            / relative_path
        )


        print(
            f"Обработка: "
            f"{relative_path}"
        )


        process_yaml_file(
            source_file,
            output_file,
            entity_database
        )


    # =========================
    # FTL
    # =========================

    FTL_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    FTL_FILE.write_text(
        "\n\n".join(
            ftl_entries
        )
        + "\n",
        encoding="utf-8"
    )


    # =========================
    # Готово
    # =========================

    print()
    print(
        "=== Готово ==="
    )

    print(
        f"Создано FTL записей: "
        f"{len(ftl_entries)}"
    )

    print(
        f"YAML файлы: "
        f"{OUTPUT_DIR}"
    )

    print(
        f"FTL файл: "
        f"{FTL_FILE}"
    )


if __name__ == "__main__":

    main()
