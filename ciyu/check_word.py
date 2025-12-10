#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'ciyu'))
from ciyu_mysql import get_database_connection

def check_word(word):
    conn = get_database_connection()
    if not conn:
        print("无法连接数据库")
        return
    
    try:
        cur = conn.cursor()
        cur.execute('SELECT * FROM hanyuguoxue_ciyu WHERE word=%s', (word,))
        rows = cur.fetchall()
        
        if rows:
            print(f"词语 '{word}' 的数据库记录:")
            for row in rows:
                print(row)
        else:
            print(f"词语 '{word}' 不存在于数据库中")
            
    finally:
        conn.close()

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        check_word(sys.argv[1])
    else:
        check_word('爱亲') 