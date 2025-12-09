# -*- coding: utf-8 -*-
"""
Neo4j 相关的配置与工具函数。

提供：
 - neo4j_config
 - get_idioms_from_neo4j(limit=None)

这个模块把 Neo4j 访问逻辑集中，方便被 batch 脚本或测试模块调用。
"""
from neo4j import GraphDatabase

# Neo4j配置（请按需修改）
neo4j_config = {
    "uri": "bolt://8.153.207.172:7687",
    "user": "neo4j",
    "password": "xtxzhu2u"
}


def get_idioms_from_neo4j(limit=None):
    """
    从 Neo4j 数据库获取成语名称列表。
    返回值为字符串列表，若获取失败返回空列表。
    """
    try:
        driver = GraphDatabase.driver(neo4j_config["uri"], auth=(neo4j_config["user"], neo4j_config["password"]))
        idiom_list = []
        with driver.session() as session:
            if limit:
                query = "MATCH (n:Idiom) RETURN n.name AS name LIMIT $limit"
                result = session.run(query, limit=limit)
            else:
                query = "MATCH (n:Idiom) RETURN n.name AS name"
                result = session.run(query)
            for record in result:
                idiom_list.append(record["name"])
        driver.close()
        return idiom_list
    except Exception as e:
        print(f"[WARN] 从 Neo4j 获取成语失败: {e}")
        return []
