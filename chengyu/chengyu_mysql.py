# chengyu/test_db_connect.py
"""
集中的 MySQL 连接模块，同时包含一个运行测试的入口。

功能：
 - 导出 `mysql_config` 和 `get_database_connection()` 供其他模块导入使用
 - 作为脚本运行时会尝试建立连接并打印 MySQL 版本（便于快速连通性测试）

示例：
    python test_db_connect.py
"""
import pymysql
import json

# 模式标志：是否为测试模式（不实际写入数据库）
TEST_MODE = False
# TEST_MODE = True

# MySQL 连接配置
mysql_config = {
    "host": "8.153.207.172",
    "user": "root",
    "password": "Restart1128",
    "database": "lab_education",
    "port": 3307,
}


def get_database_connection():
    """
    获取 MySQL 数据库连接（返回 pymysql.Connection 或 None）。
    """
    try:
        connection = pymysql.connect(
            host=mysql_config["host"],
            user=mysql_config["user"],
            password=mysql_config["password"],
            database=mysql_config["database"],
            port=mysql_config["port"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor
        )
        return connection
    except Exception as e:
        print(f"无法建立数据库连接: {e}")
        return None


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


def save_chengyu_to_db(chengyu_data):
    """
    将成语数据保存到数据库。
    该函数从原来的 `extract_chengyu.py` 中抽出，放在数据库模块中以便于管理。
    """
    # 测试模式：打印将要执行的 SQL 与数据并返回 True（不实际写入 DB）
    if TEST_MODE:
        chengyu = ""
        if 'data' in chengyu_data and 'chengyu' in chengyu_data['data']:
            chengyu = chengyu_data['data']['chengyu']

        if 'error' in chengyu_data:
            print("[TEST_MODE] 遇到错误，原本会跳过写入：", chengyu_data.get('error'))
            return False

        data = chengyu_data.get('data', {})
        synonyms = data.get('synonyms', []) or []
        antonyms = data.get('antonyms', []) or []

        sql = (
            "INSERT INTO hanyuguoxue_chengyu (chengyu, url, pinyin, zhuyin, emotion, explanation,"
            " source, usage, example, synonyms, antonyms, translation) VALUES (...)"
        )

        params = (
            chengyu,
            chengyu_data.get('url', ''),
            data.get('pinyin', ''),
            data.get('zhuyin', ''),
            data.get('emotion', ''),
            data.get('explanation', ''),
            data.get('source', ''),
            data.get('usage', ''),
            data.get('example', ''),
            json.dumps(synonyms, ensure_ascii=False),
            json.dumps(antonyms, ensure_ascii=False),
            data.get('translation', ''),
        )

        print("[TEST_MODE] 将执行基础表 SQL:")
        print(sql)
        print("[TEST_MODE] 参数:", params)

        # 关系表计划操作
        def normalize_term(t):
            if not t:
                return None
            return t.strip()

        related_terms = set([normalize_term(t) for t in synonyms + antonyms if t and normalize_term(t)])
        print("[TEST_MODE] 将确保下列相关词在基础表存在 (INSERT IGNORE):", related_terms)

        planned_relations = []
        for t in synonyms:
            planned_relations.append((chengyu, t, 'synonym'))
        for t in antonyms:
            planned_relations.append((chengyu, t, 'antonym'))

        print("[TEST_MODE] 将插入到 chengyu_relation 的关系数据 (主词, 相关词, 类型):")
        for r in planned_relations:
            print("  ", r)

        return True

    # 非测试模式：正常写入数据库
    connection = get_database_connection()
    if not connection:
        return False
    try:
        cursor = connection.cursor()
        # 开始事务
        connection.begin()

        chengyu = ""
        data = chengyu_data.get('data', {})
        if data and 'chengyu' in data:
            chengyu = data['chengyu']

        # 如果解析返回 error 或未解析到基础信息（chengyu 为空），则放弃写入
        if 'error' in chengyu_data:
            connection.rollback()
            return False
        if not data or not chengyu:
            connection.rollback()
            return False

        synonyms = data.get('synonyms', []) or []
        antonyms = data.get('antonyms', []) or []

        sql = """
        INSERT INTO hanyuguoxue_chengyu
        (`chengyu`, `url`, `pinyin`, `zhuyin`, `emotion`, `explanation`, 
         `source`, `usage`, `example`, `synonyms`, `antonyms`, `translation`)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
        `url` = VALUES(`url`),
        `pinyin` = VALUES(`pinyin`),
        `zhuyin` = VALUES(`zhuyin`),
        `emotion` = VALUES(`emotion`),
        `explanation` = VALUES(`explanation`),
        `source` = VALUES(`source`),
        `usage` = VALUES(`usage`),
        `example` = VALUES(`example`),
        `synonyms` = VALUES(`synonyms`),
        `antonyms` = VALUES(`antonyms`),
        `translation` = VALUES(`translation`),
        updated_at = CURRENT_TIMESTAMP
        """
        cursor.execute(sql, (
            chengyu,
            chengyu_data.get('url', ''),
            data.get('pinyin', ''),
            data.get('zhuyin', ''),
            data.get('emotion', ''),
            data.get('explanation', ''),
            data.get('source', ''),
            data.get('usage', ''),
            data.get('example', ''),
            json.dumps(synonyms, ensure_ascii=False),
            json.dumps(antonyms, ensure_ascii=False),
            data.get('translation', '')
        ))

        # 确保主成语有 id
        cursor.execute("SELECT id FROM hanyuguoxue_chengyu WHERE chengyu=%s", (chengyu,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("INSERT IGNORE INTO hanyuguoxue_chengyu (chengyu) VALUES (%s)", (chengyu,))
            cursor.execute("SELECT id FROM hanyuguoxue_chengyu WHERE chengyu=%s", (chengyu,))
            row = cursor.fetchone()
        if not row:
            raise RuntimeError('无法获取主成语 id')
        main_id = row['id']

        def normalize_term(t):
            if not t:
                return None
            return t.strip()

        def ensure_terms_have_ids(term_list):
            terms = [normalize_term(t) for t in set(term_list) if t and normalize_term(t)]
            if not terms:
                return {}
            insert_vals = [(t,) for t in terms]
            cursor.executemany("INSERT IGNORE INTO hanyuguoxue_chengyu (chengyu) VALUES (%s)", insert_vals)
            placeholders = ','.join(['%s'] * len(terms))
            cursor.execute(f"SELECT id, chengyu FROM hanyuguoxue_chengyu WHERE chengyu IN ({placeholders})", terms)
            rows = cursor.fetchall()
            return {r['chengyu']: r['id'] for r in rows}

        def insert_relations_for(main_id, related_terms, relation_type):
            if not related_terms:
                return
            term_map = ensure_terms_have_ids(related_terms + [chengyu])
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
                    "INSERT IGNORE INTO chengyu_relation (min_id, max_id, relation_type) VALUES (%s, %s, %s)",
                    values
                )

        synonyms = data.get('synonyms', []) or []
        antonyms = data.get('antonyms', []) or []
        insert_relations_for(main_id, synonyms, 'synonym')
        insert_relations_for(main_id, antonyms, 'antonym')

        connection.commit()
        return True
    except Exception as e:
        print(f"保存成语数据到数据库失败: {e}")
        try:
            connection.rollback()
        except Exception:
            pass
        return False
    finally:
        connection.close()