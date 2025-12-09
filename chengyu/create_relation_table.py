# -*- coding: utf-8 -*-
"""
创建成语关系表（外键方案），并在创建失败时进行清理（删除已创建的表）。

说明：此脚本用于创建两张表：基础表 `hanyuguoxue_chengyu`（如果尚不存在）和
关系表 `chengyu_relation`（使用 id 外键，存储有序对 min_id/max_id 来表示无向关系）。

注意：DDL 在 MySQL 中通常是自动提交的（非事务性的），因此如果某条 CREATE TABLE
失败，我们不能回滚之前的 DDL；脚本会在捕获异常后尝试删除关系表以清理半成品。
运行示例：
  python create_relation_table.py
"""
import traceback
import pymysql
from hanyuguoxue_chengyu import get_database_connection


CREATE_BASE_SQL = """
CREATE TABLE IF NOT EXISTS hanyuguoxue_chengyu (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `chengyu` VARCHAR(50) NOT NULL COMMENT '成语',
    `url` TEXT COMMENT '详情页面URL',
    `pinyin` VARCHAR(200) COMMENT '拼音',
    `zhuyin` VARCHAR(200) COMMENT '注音',
    `emotion` VARCHAR(50) COMMENT '感情色彩',
    `explanation` TEXT COMMENT '释义',
    `source` TEXT COMMENT '出处',
    `usage` TEXT COMMENT '用法',
    `example` TEXT COMMENT '例句',
    `synonyms` JSON COMMENT '近义词列表',
    `antonyms` JSON COMMENT '反义词列表',
    `translation` TEXT COMMENT '英文翻译',
    `error` TEXT COMMENT '错误信息',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY unique_chengyu (chengyu),
    INDEX idx_pinyin (pinyin),
    INDEX idx_emotion (emotion)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='汉语言国学成语数据';
"""


CREATE_RELATION_SQL = """
CREATE TABLE IF NOT EXISTS chengyu_relation (
    id INT AUTO_INCREMENT PRIMARY KEY,
    min_id INT NOT NULL,
    max_id INT NOT NULL,
    relation_type ENUM('synonym','antonym') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_relation (min_id, max_id, relation_type),
    INDEX idx_min (min_id),
    INDEX idx_max (max_id),
    CONSTRAINT fk_min_chengyu FOREIGN KEY (min_id) REFERENCES hanyuguoxue_chengyu(id) ON DELETE CASCADE,
    CONSTRAINT fk_max_chengyu FOREIGN KEY (max_id) REFERENCES hanyuguoxue_chengyu(id) ON DELETE CASCADE
    -- 注意：在某些 MySQL 版本中 CHECK 约束会被忽略，建议在应用层保证 min_id < max_id
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='成语关系（无向，有序对）映射表';
"""


def create_tables():
    conn = get_database_connection()
    if not conn:
        print("无法获得数据库连接，跳过建表")
        return False

    created_relation = False
    cur = None
    try:
        cur = conn.cursor()
        # 创建基础表（若已有则 noop）
        cur.execute(CREATE_BASE_SQL)
        print("基础表 hanyuguoxue_chengyu 已创建或已存在")

        # 创建关系表
        cur.execute(CREATE_RELATION_SQL)
        created_relation = True
        print("关系表 chengyu_relation 已创建或已存在")

        conn.commit()
        return True

    except Exception as e:
        print("建表过程中发生错误:")
        traceback.print_exc()
        # 尝试清理已创建的关系表（如果存在）
        try:
            if created_relation and cur:
                print("尝试删除已创建的关系表 chengyu_relation ...")
                cur.execute("DROP TABLE IF EXISTS chengyu_relation")
                conn.commit()
                print("已删除 chengyu_relation")
        except Exception:
            print("清理 chengyu_relation 失败：")
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
