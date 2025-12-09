# -*- coding: utf-8 -*-
"""ciyu 的 Neo4j 工具模块。

提供：
 - neo4j_config
 - get_words_from_neo4j(limit=None)

将词语（Word 节点）的读取逻辑放在这里，便于 batch 脚本或其他模块调用。
"""
from neo4j import GraphDatabase
from typing import List, Optional

# Neo4j 配置（按需修改）
neo4j_config = {
    "uri": "bolt://8.153.207.172:7687",
    "user": "neo4j",
    "password": "xtxzhu2u",
}


def get_words_from_neo4j(limit: Optional[int] = None) -> List[str]:
    """从 Neo4j 获取词语列表（Word 节点的 name 属性）。

    返回字符串列表。出错时返回空列表并打印警告。
    """
    try:
        driver = GraphDatabase.driver(neo4j_config["uri"], auth=(neo4j_config["user"], neo4j_config["password"]))
        word_list: List[str] = []
        with driver.session() as session:
            if limit:
                query = "MATCH (n:Word) RETURN n.name AS name LIMIT $limit"
                result = session.run(query, limit=limit)
            else:
                query = "MATCH (n:Word) RETURN n.name AS name"
                result = session.run(query)
            for record in result:
                name = record.get("name")
                if name:
                    word_list.append(name)
        driver.close()
        return word_list
    except Exception as e:
        print(f"[WARN] 从 Neo4j 获取词语失败: {e}")
        return []
