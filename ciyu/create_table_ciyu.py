# -*- coding: utf-8 -*-
"""创建存储词语数据的 MySQL 数据表。"""

from hanyuguoxue_ciyu import get_database_connection


def create_word_table() -> bool:
    connection = get_database_connection()
    if not connection:
        return False

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
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
        )
        connection.commit()
        print("✅ 词语数据表创建成功或已存在")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"❌ 创建表失败: {exc}")
        connection.rollback()
        return False
    finally:
        connection.close()


if __name__ == "__main__":
    print("🔧 创建词语数据表……")
    if create_word_table():
        print("🎉 表创建完成！")
    else:
        print("❌ 表创建失败！")
