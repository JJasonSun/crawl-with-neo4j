# -*- coding: utf-8 -*-
"""
数据库操作抽象基类
提供通用的数据库连接和操作方法，减少重复代码。
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from common.config import MYSQL_CONFIG, NEO4J_CONFIG, TEST_MODE


class BaseDB(ABC):
    """数据库操作抽象基类"""
    
    def __init__(self):
        self.mysql_config = MYSQL_CONFIG
        self.neo4j_config = NEO4J_CONFIG
        self.test_mode = TEST_MODE
    
    def get_mysql_connection(self):
        """获取 MySQL 数据库连接"""
        try:
            import pymysql
            cfg = self.mysql_config.copy()
            cfg.update({"charset": "utf8mb4", "cursorclass": pymysql.cursors.DictCursor})
            return pymysql.connect(**cfg)
        except Exception as e:
            print(f"无法建立 MySQL 连接: {e}")
            return None
    
    def get_neo4j_driver(self):
        """获取 Neo4j 驱动"""
        try:
            from neo4j import GraphDatabase
            return GraphDatabase.driver(
                uri=self.neo4j_config["uri"],
                auth=(self.neo4j_config["user"], self.neo4j_config["password"])
            )
        except Exception as e:
            print(f"无法建立 Neo4j 连接: {e}")
            return None
    
    @abstractmethod
    def get_main_table_name(self) -> str:
        """获取主表名"""
        pass
    
    @abstractmethod
    def get_relation_table_name(self) -> str:
        """获取关系表名"""
        pass
    
    @abstractmethod
    def get_main_key_field(self) -> str:
        """获取主键字段名"""
        pass
    
    @abstractmethod
    def get_label_key(self) -> str:
        """获取标签键名"""
        pass
    
    def save_to_mysql(self, data: Dict[str, Any]) -> bool:
        """将数据保存到 MySQL"""
        if self.test_mode:
            return self._save_to_mysql_test_mode(data)
        
        connection = self.get_mysql_connection()
        if not connection:
            return False
        
        try:
            cursor = connection.cursor()
            connection.begin()
            
            main_value = ""
            data_content = data.get('data', {})
            if data_content and self.get_label_key() in data_content:
                main_value = data_content[self.get_label_key()]
            
            # 检查错误和基础信息
            if 'error' in data or not data_content or not main_value:
                connection.rollback()
                return False
            
            synonyms = data_content.get('synonyms', []) or []
            antonyms = data_content.get('antonyms', []) or []
            
            # 插入或更新基础表
            sql = self._build_insert_sql()
            params = self._build_insert_params(data, data_content, main_value, synonyms, antonyms)
            
            cursor.execute(sql, params)
            
            # 确保主记录有 ID
            cursor.execute(f"SELECT id FROM {self.get_main_table_name()} WHERE {self.get_main_key_field()}=%s", (main_value,))
            row = cursor.fetchone()
            if not row:
                cursor.execute(f"INSERT IGNORE INTO {self.get_main_table_name()} ({self.get_main_key_field()}) VALUES (%s)", (main_value,))
                cursor.execute(f"SELECT id FROM {self.get_main_table_name()} WHERE {self.get_main_key_field()}=%s", (main_value,))
                row = cursor.fetchone()
            if not row:
                raise RuntimeError(f'无法获取主{self.get_label_key()} id')
            main_id = row['id']
            
            # 插入关系
            self._insert_relations(cursor, main_id, main_value, synonyms, antonyms)
            
            connection.commit()
            return True
        except Exception as e:
            print(f"保存{self.get_label_key()}数据失败: {e}")
            connection.rollback()
            return False
        finally:
            connection.close()
    
    @abstractmethod
    def _build_insert_sql(self) -> str:
        """构建插入 SQL 语句"""
        pass
    
    @abstractmethod
    def _build_insert_params(self, data: Dict[str, Any], data_content: Dict[str, Any], 
                           main_value: str, synonyms: List[str], antonyms: List[str]) -> tuple:
        """构建插入参数"""
        pass
    
    def _save_to_mysql_test_mode(self, data: Dict[str, Any]) -> bool:
        """测试模式：打印将要执行的 SQL 与数据"""
        main_value = ""
        if 'data' in data and self.get_label_key() in data['data']:
            main_value = data['data'][self.get_label_key()]
        
        if 'error' in data:
            print(f"[TEST_MODE] 遇到错误，原本会跳过写入：", data.get('error'))
            return False
        
        data_content = data.get('data', {})
        synonyms = data_content.get('synonyms', []) or []
        antonyms = data_content.get('antonyms', []) or []
        
        sql = self._build_insert_sql()
        params = self._build_insert_params(data, data_content, main_value, synonyms, antonyms)
        
        print(f"[TEST_MODE] 将执行基础表 SQL:")
        print(sql)
        print(f"[TEST_MODE] 参数:", params)
        
        # 打印关系计划
        related_terms = set([t.strip() for t in synonyms + antonyms if t and t.strip()])
        print(f"[TEST_MODE] 将确保下列相关词在基础表存在 (INSERT IGNORE):", related_terms)
        
        planned_relations = []
        for t in synonyms:
            planned_relations.append((main_value, t, 'synonym'))
        for t in antonyms:
            planned_relations.append((main_value, t, 'antonym'))
        
        print(f"[TEST_MODE] 将插入到 {self.get_relation_table_name()} 的关系数据 (主词, 相关词, 类型):")
        for r in planned_relations:
            print("  ", r)
        return True
    
    def _insert_relations(self, cursor, main_id: int, main_value: str, 
                       synonyms: List[str], antonyms: List[str]):
        """插入关系"""
        def normalize_term(t):
            if not t:
                return None
            return t.strip()
        
        def ensure_terms_have_ids(term_list):
            terms = [normalize_term(t) for t in set(term_list) if t and normalize_term(t)]
            if not terms:
                return {}
            insert_vals = [(t,) for t in terms]
            cursor.executemany(f"INSERT IGNORE INTO {self.get_main_table_name()} ({self.get_main_key_field()}) VALUES (%s)", insert_vals)
            placeholders = ','.join(['%s'] * len(terms))
            cursor.execute(f"SELECT id, {self.get_main_key_field()} FROM {self.get_main_table_name()} WHERE {self.get_main_key_field()} IN ({placeholders})", terms)
            rows = cursor.fetchall()
            return {r[self.get_main_key_field()]: r['id'] for r in rows}
        
        def insert_relations_for(main_id, related_terms, relation_type):
            if not related_terms:
                return
            term_map = ensure_terms_have_ids(related_terms + [main_value])
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
                    f"INSERT IGNORE INTO {self.get_relation_table_name()} (min_id, max_id, relation_type) VALUES (%s, %s, %s)",
                    values
                )
        
        insert_relations_for(main_id, synonyms, 'synonym')
        insert_relations_for(main_id, antonyms, 'antonym')
    
    def get_from_neo4j(self, limit: Optional[int] = None) -> List[str]:
        """从 Neo4j 获取数据列表"""
        driver = self.get_neo4j_driver()
        if not driver:
            return []
        
        try:
            result_list = []
            with driver.session() as session:
                if limit:
                    query = f"MATCH (n:{self.get_neo4j_label()}) RETURN n.name AS name LIMIT $limit"
                    result = session.run(query, limit=limit)
                else:
                    query = f"MATCH (n:{self.get_neo4j_label()}) RETURN n.name AS name"
                    result = session.run(query)
                for record in result:
                    result_list.append(record["name"])
            driver.close()
            return result_list
        except Exception as e:
            print(f"[WARN] 从 Neo4j 获取{self.get_label_key()}失败: {e}")
            return []
    
    @abstractmethod
    def get_neo4j_label(self) -> str:
        """获取 Neo4j 标签名"""
        pass
