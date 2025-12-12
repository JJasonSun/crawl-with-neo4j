# -*- coding: utf-8 -*-
"""ciyu 的数据库访问模块。

包含数据库配置、连接函数，以及 `save_ciyu_to_db`（带 TEST_MODE dry-run 支持）。
"""
import json
import pymysql

# 模式标志：是否为测试模式（不实际写入数据库）
# TEST_MODE = False
TEST_MODE = True

# MySQL 连接配置
mysql_config = {
    "host": "8.153.207.172",
    "user": "root",
    "password": "Restart1128",
    "database": "lab_education",
    "port": 3307,
}


def get_database_connection():
    try:
        return pymysql.connect(
            host=mysql_config["host"],
            user=mysql_config["user"],
            password=mysql_config["password"],
            database=mysql_config["database"],
            port=mysql_config["port"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
    except Exception as exc:
        print(f"数据库连接失败: {exc}")
        return None


def save_ciyu_to_db(ciyu_data: dict) -> bool:
    """将词语数据保存到 MySQL。

    若 `TEST_MODE` 为 True，则只打印将要执行的 SQL/参数与关系计划，不实际写入。
    """
    # 测试模式：打印将要执行的 SQL 与数据，不连接数据库
    if TEST_MODE:
        data = ciyu_data.get("data", {})
        word = data.get("word", "")

        # 与 chengyu 的 TEST_MODE 输出严格对齐：遇到 error 时给出提示并返回 False（表示不会写入）
        if "error" in ciyu_data:
            print("[TEST_MODE] 遇到错误，原本会跳过写入：", ciyu_data.get("error"))
            return False

        sql = (
            "INSERT INTO hanyuguoxue_ciyu (word, url, pinyin, zhuyin, part_of_speech, is_common, definition, synonyms, antonyms)"
            " VALUES (...) ON DUPLICATE KEY UPDATE ..."
        )

        params = (
            word,
            ciyu_data.get("url", ""),
            data.get("pinyin", ""),
            data.get("zhuyin", ""),
            data.get("part_of_speech", ""),
            int(bool(data.get("is_common"))),
            data.get("definition", ""),
            json.dumps(data.get("synonyms", []), ensure_ascii=False),
            json.dumps(data.get("antonyms", []), ensure_ascii=False),
        )

        print("[TEST_MODE] 将执行基础表 SQL:")
        print(sql)
        print("[TEST_MODE] 参数:", params)

        # 打印将要确保存在的相关词集合（INSERT IGNORE）与计划的关系插入
        synonyms = data.get("synonyms", []) or []
        antonyms = data.get("antonyms", []) or []

        # 规范化并去重相关词（简洁版本，不定义额外函数以避免命名冲突）
        related_terms = set([t.strip() for t in synonyms + antonyms if t and t.strip()])
        print("[TEST_MODE] 将确保下列相关词在基础表存在 (INSERT IGNORE):", related_terms)

        planned_relations = []
        for t in synonyms:
            planned_relations.append((word, t, 'synonym'))
        for t in antonyms:
            planned_relations.append((word, t, 'antonym'))

        print("[TEST_MODE] 将插入到 ciyu_relation 的关系 (主词, 相关词, 类型):")
        for r in planned_relations:
            print("  ", r)
        return True

    connection = get_database_connection()
    if not connection:
        return False

    try:
        cursor = connection.cursor()
        data = ciyu_data.get("data", {})
        # 要求必须有基础信息（至少要有 word），否则丢弃不写入
        if not data or not data.get("word"):
            # 与 chengyu 的逻辑保持一致：遇到无效/缺失基础信息则不写入
            return False

        word = data.get("word", "")

        # 如果解析时返回 error，则丢弃（不写入），与 chengyu 保持一致
        if "error" in ciyu_data:
            return False

        else:
            sql = (
                "INSERT INTO hanyuguoxue_ciyu "
                "(word, url, pinyin, zhuyin, part_of_speech, is_common, "
                "definition, synonyms, antonyms) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE "
                "url = VALUES(url), "
                "pinyin = VALUES(pinyin), "
                "zhuyin = VALUES(zhuyin), "
                "part_of_speech = VALUES(part_of_speech), "
                "is_common = VALUES(is_common), "
                "definition = VALUES(definition), "
                "synonyms = VALUES(synonyms), "
                "antonyms = VALUES(antonyms), "
                "updated_at = CURRENT_TIMESTAMP"
            )
            cursor.execute(
                sql,
                (
                    word,
                    ciyu_data.get("url", ""),
                    data.get("pinyin", ""),
                    data.get("zhuyin", ""),
                    data.get("part_of_speech", ""),
                    int(bool(data.get("is_common"))),
                    data.get("definition", ""),
                    json.dumps(data.get("synonyms", []), ensure_ascii=False),
                    json.dumps(data.get("antonyms", []), ensure_ascii=False),
                ),
            )

        # 确保主词语有 id（如果基础表刚插入，则能获取到）
        cursor.execute("SELECT id FROM hanyuguoxue_ciyu WHERE word=%s", (word,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("INSERT IGNORE INTO hanyuguoxue_ciyu (word) VALUES (%s)", (word,))
            cursor.execute("SELECT id FROM hanyuguoxue_ciyu WHERE word=%s", (word,))
            row = cursor.fetchone()
        if not row:
            raise RuntimeError('无法获取主词语 id')
        main_id = row['id']

        # 辅助：规范化词
        def normalize_term(t: str) -> str:
            return t.strip() if t else ''

        # 批量确保词存在并返回 name->id 映射
        def ensure_terms_have_ids(term_list):
            terms = [normalize_term(t) for t in set(term_list) if t and normalize_term(t)]
            if not terms:
                return {}
            insert_vals = [(t,) for t in terms]
            cursor.executemany("INSERT IGNORE INTO hanyuguoxue_ciyu (word) VALUES (%s)", insert_vals)
            placeholders = ','.join(['%s'] * len(terms))
            cursor.execute(f"SELECT id, word FROM hanyuguoxue_ciyu WHERE word IN ({placeholders})", terms)
            rows = cursor.fetchall()
            return {r['word']: r['id'] for r in rows}

        # 插入关系（min_id,max_id）
        def insert_relations_for(main_id: int, related_terms, relation_type: str):
            if not related_terms:
                return
            term_map = ensure_terms_have_ids(related_terms + [word])
            values = []
            for t in related_terms:
                tn = normalize_term(t)
                if not tn:
                    continue
                rid = term_map.get(tn)
                if not rid or rid == main_id:
                    continue
                a = min(main_id, rid)
                b = max(main_id, rid)
                values.append((a, b, relation_type))
            if values:
                cursor.executemany(
                    "INSERT IGNORE INTO ciyu_relation (min_id, max_id, relation_type) VALUES (%s, %s, %s)",
                    values,
                )

        synonyms = data.get("synonyms", []) or []
        antonyms = data.get("antonyms", []) or []
        insert_relations_for(main_id, synonyms, 'synonym')
        insert_relations_for(main_id, antonyms, 'antonym')

        connection.commit()
        return True
    except Exception as exc:
        print(f"保存词语数据失败: {exc}")
        connection.rollback()
        return False
    finally:
        connection.close()


def main():
    conn = get_database_connection()
    if not conn:
        print("无法建立连接")
        return 2
    try:
        cur = conn.cursor()
        cur.execute("SELECT VERSION() AS v;")
        print("数据库可达，版本：", cur.fetchone())
    except Exception as e:
        print("执行测试查询失败：", e)
        return 3
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return 0


if __name__ == '__main__':
    exit(main())
