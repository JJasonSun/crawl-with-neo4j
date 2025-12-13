# -*- coding: utf-8 -*-
"""
成语数据库操作类（MySQL + Neo4j）
统一管理成语的数据库操作，包括 MySQL 写入和 Neo4j 查询。
"""
import json
import os
import sys
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.base_db import BaseDB


class ChengyuDB(BaseDB):
    """成语数据库操作类"""
    
    def get_main_table_name(self) -> str:
        """获取主表名"""
        return "hanyuguoxue_chengyu"
    
    def get_relation_table_name(self) -> str:
        """获取关系表名"""
        return "chengyu_relation"
    
    def get_main_key_field(self) -> str:
        """获取主键字段名"""
        return "chengyu"
    
    def get_label_key(self) -> str:
        """获取标签键名"""
        return "chengyu"
    
    def get_neo4j_label(self) -> str:
        """获取 Neo4j 标签名"""
        return "Idiom"
    
    def _build_insert_sql(self) -> str:
        """构建插入 SQL 语句"""
        return """
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
    
    def _build_insert_params(self, data: Dict[str, Any], data_content: Dict[str, Any], 
                           main_value: str, synonyms: List[str], antonyms: List[str]) -> tuple:
        """构建插入参数"""
        return (
            main_value,
            data.get('url', ''),
            data_content.get('pinyin', ''),
            data_content.get('zhuyin', ''),
            data_content.get('emotion', ''),
            data_content.get('explanation', ''),
            data_content.get('source', ''),
            data_content.get('usage', ''),
            data_content.get('example', ''),
            json.dumps(synonyms, ensure_ascii=False),
            json.dumps(antonyms, ensure_ascii=False),
            data_content.get('translation', '')
        )


# 创建全局实例
_chengyu_db = ChengyuDB()

# 兼容性函数
def get_database_connection():
    """获取 MySQL 数据库连接"""
    return _chengyu_db.get_mysql_connection()

def save_chengyu_to_db(chengyu_data) -> bool:
    """将成语数据保存到数据库"""
    return _chengyu_db.save_to_mysql(chengyu_data)

def get_idiom_list(limit: Optional[int] = None) -> List[str]:
    """从 Neo4j 获取成语列表"""
    return _chengyu_db.get_from_neo4j(limit)