# -*- coding: utf-8 -*-
"""创建词语基础表和关系表（近义/反义词）。

遵循 `chengyu` 目录下的命名与关系模型：
- 基础表：`hanyuguoxue_ciyu`
- 关系表：`ciyu_relation`（存储 min_id, max_id, relation_type）

如果在创建关系表时发生错误，脚本会尝试清理半成品。
"""

import traceback
from ciyu_mysql import get_database_connection


CREATE_BASE_SQL = """
CREATE TABLE IF NOT EXISTS hanyuguoxue_ciyu (
    id INT AUTO_INCREMENT PRIMARY KEY,
    word VARCHAR(100) NOT NULL COMMENT '词语',
    url TEXT COMMENT '详情页面 URL',
    pinyin VARCHAR(200) COMMENT '拼音',
    zhuyin VARCHAR(200) COMMENT '注音',
    part_of_speech VARCHAR(50) COMMENT '词性',
    is_common TINYINT(1) DEFAULT 0 COMMENT '是否常用词',
    definition TEXT COMMENT '网络解释',
    synonyms JSON COMMENT '近义词列表',
    antonyms JSON COMMENT '反义词列表',
    error TEXT COMMENT '错误信息',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY unique_word (word),
    INDEX idx_pos (part_of_speech)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='汉语国学词语数据'
"""


CREATE_RELATION_SQL = """
CREATE TABLE IF NOT EXISTS ciyu_relation (
    id INT AUTO_INCREMENT PRIMARY KEY,
    min_id INT NOT NULL,
    max_id INT NOT NULL,
    relation_type ENUM('synonym','antonym') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_relation (min_id, max_id, relation_type),
    INDEX idx_min (min_id),
    INDEX idx_max (max_id),
    CONSTRAINT fk_min_ciyu FOREIGN KEY (min_id) REFERENCES hanyuguoxue_ciyu(id) ON DELETE CASCADE,
    CONSTRAINT fk_max_ciyu FOREIGN KEY (max_id) REFERENCES hanyuguoxue_ciyu(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='词语关系（无向，有序对）映射表';
"""


def create_tables() -> bool:
    conn = get_database_connection()
    if not conn:
        print("无法获得数据库连接，跳过建表")
        return False

    created_relation = False
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(CREATE_BASE_SQL)
        print("基础表 hanyuguoxue_ciyu 已创建或已存在")

        cur.execute(CREATE_RELATION_SQL)
        created_relation = True
        print("关系表 ciyu_relation 已创建或已存在")

        conn.commit()
        return True
    except Exception as e:
        print("建表过程中发生错误:")
        traceback.print_exc()
        try:
            if created_relation and cur:
                print("尝试删除已创建的关系表 ciyu_relation ...")
                cur.execute("DROP TABLE IF EXISTS ciyu_relation")
                conn.commit()
                print("已删除 ciyu_relation")
        except Exception:
            print("清理 ciyu_relation 失败：")
            traceback.print_exc()
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    print("🔧 尝试创建基础表与关系表（外键方案）...")
    ok = create_tables()
    if ok:
        print("🎉 表创建成功（或已存在）。")
    else:
        print("❌ 建表失败，已尝试清理。检查日志并修正后重试。")
