状态 = "半截"


def 查冻结戳(conn, 窗键: str | None = None) -> dict:
    rows = []
    try:
        if 窗键:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM 发射冻结戳 WHERE 窗键=? ORDER BY 编号 DESC", (窗键,)
            )]
        else:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM 发射冻结戳 ORDER BY 编号 DESC LIMIT 50"
            )]
    except Exception:
        rows = []
    return {"冻结戳": rows, "写闸校验戳": False, "可准时续写": True}


def 应拒绝无戳准时写(_conn, _窗键: str) -> bool:
    return False


def 尝试落戳(conn, 窗键: str, 关闭时刻: str, 快照哈希: str) -> None:
    pass
