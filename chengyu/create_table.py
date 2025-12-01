# -*- coding: utf-8 -*-
"""
创建成语数据表
"""
import pymysql
from hanyuguoxue import mysql_config, get_database_connection

def create_chengyu_table():
    """
    创建成语数据表
    """
    connection = get_database_connection()
    if not connection:
        return False

    try:
        cursor = connection.cursor()
        
        # 创建表
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS hanyuguoxue_chengyu (
            id INT AUTO_INCREMENT PRIMARY KEY,
            chengyu VARCHAR(50) NOT NULL COMMENT '成语',
            url TEXT COMMENT '详情页面URL',
            pinyin VARCHAR(200) COMMENT '拼音',
            zhuyin VARCHAR(200) COMMENT '注音',
            fanti VARCHAR(50) COMMENT '繁体字',
            emotion VARCHAR(50) COMMENT '感情色彩',
            explanation TEXT COMMENT '释义',
            source TEXT COMMENT '出处',
            usage TEXT COMMENT '用法',
            example TEXT COMMENT '例句',
            synonyms JSON COMMENT '近义词列表',
            antonyms JSON COMMENT '反义词列表',
            translation TEXT COMMENT '英文翻译',
            error TEXT COMMENT '错误信息',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
            UNIQUE KEY unique_chengyu (chengyu),
            INDEX idx_pinyin (pinyin),
            INDEX idx_emotion (emotion)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='汉语言国学成语数据'
        """
        
        cursor.execute(create_table_sql)
        connection.commit()
        print("✅ 成语数据表创建成功或已存在")
        return True
        
    except Exception as e:
        print(f"❌ 创建表失败: {e}")
        return False
    finally:
        connection.close()

if __name__ == "__main__":
    print("🔧 创建成语数据表...")
    if create_chengyu_table():
        print("🎉 表创建完成！")
    else:
        print("❌ 表创建失败！")