"""发射冻结戳（全局唯一口径甲·关闭即冻结：以戳号前置拒绝为准）。

关闭成功必须同票落下冻结戳（窗键、关闭时刻、发射快照哈希、戳号），半截失败整票回滚；
之后同窗准时写必须在写闸消化戳：

- 戳核证有效 → 拒收留证（关窗拒收携带戳号），冻结合计不动；
- 缺戳或戳失配 → 缺戳异常，整票拒绝、装载事务整体回滚，事件只能改入新窗。

硬约束：禁止关闭成功而戳空；禁止无戳号准时写改冻结合计；禁止邻窗戳串用
（戳号由 窗键|关闭时刻|快照哈希 确定性派生，挪到邻窗重算必失配）。
"""

import hashlib

状态 = "已实现"

口径 = "关闭即冻结"


class 缺戳异常(RuntimeError):
    """同窗准时写缺有效冻结戳：整票拒绝，装载事务整体回滚（冻结合计不得动）。"""


def 快照哈希(窗键: str, 关闭时刻: str, 发射号: int, 关闭时水位: str,
             点赞: int, 送礼: int, 笔数: int, 版本: int, 口径值: str = 口径) -> str:
    """发射快照哈希：把发射快照本体折成可核对的摘要。"""
    料 = "|".join(
        str(x) for x in (窗键, 关闭时刻, 发射号, 关闭时水位, 点赞, 送礼, 笔数, 版本, 口径值)
    )
    return hashlib.sha256(料.encode("utf-8")).hexdigest()


def 生成戳号(窗键: str, 关闭时刻: str, 快照哈希值: str) -> str:
    """戳号由窗键+关闭时刻+快照哈希确定性派生：邻窗戳串用重算必失配。"""
    料 = f"{窗键}|{关闭时刻}|{快照哈希值}"
    return "冻" + hashlib.sha256(料.encode("utf-8")).hexdigest()[:20].upper()


def 落戳(conn, 窗键: str, 关闭时刻: str, 快照哈希值: str) -> str:
    """关窗事务内同票落戳（甲）。任何失败抛异常 → 整票回滚，禁止关闭成功而戳空。

    - 要素缺一即失败（戳号不得为空）；
    - 同窗重戳、同号异窗（邻窗串用）即失败；
    - 可否准时续写 恒为 0：甲口径下关闭即冻结，不存在准时续写。
    """
    from app.seed import 此刻

    if not 窗键 or not 关闭时刻 or not 快照哈希值:
        raise RuntimeError(
            f"冻结戳要素缺失，拒绝落戳: 窗键={窗键!r} 关闭时刻={关闭时刻!r} 哈希={快照哈希值!r}"
        )
    戳号 = 生成戳号(窗键, 关闭时刻, 快照哈希值)
    撞 = conn.execute(
        "SELECT 窗键, 戳号 FROM 发射冻结戳 WHERE 窗键=? OR 戳号=?",
        (窗键, 戳号),
    ).fetchone()
    if 撞:
        raise RuntimeError(
            f"冻结戳冲突（重复落戳或邻窗串用）: 已有 窗键={撞['窗键']} 戳号={撞['戳号']}，"
            f"拒绝为 {窗键} 再落戳"
        )
    conn.execute(
        "INSERT INTO 发射冻结戳(窗键, 关闭时刻, 发射快照哈希, 戳号, 可否准时续写, 时刻)"
        " VALUES (?,?,?,?,0,?)",
        (窗键, 关闭时刻, 快照哈希值, 戳号, 此刻()),
    )
    return 戳号


def 取窗戳(conn, 窗键: str):
    return conn.execute("SELECT * FROM 发射冻结戳 WHERE 窗键=?", (窗键,)).fetchone()


def 核证窗戳(conn, 窗键: str):
    """核证单窗冻结戳（只读）。返回 (戳行|None, 问题列表)。

    核对链：窗关闭态 ↔ 戳在/戳空 ↔ 关闭时刻 ↔ 发射快照哈希 ↔ 戳号 ↔ 可否准时续写。
    """
    问题 = []
    窗 = conn.execute("SELECT * FROM 热度窗 WHERE 窗键=?", (窗键,)).fetchone()
    戳 = 取窗戳(conn, 窗键)
    if 窗 is None:
        return 戳, [f"冻结戳指向不存在的窗:{窗键}"] if 戳 else [f"窗不存在:{窗键}"]
    if 窗["状态"] != "已关闭":
        if 戳:
            问题.append(f"窗仍开启却已有冻结戳（半截落戳）:{戳['戳号']}")
        return 戳, 问题
    if not 戳:
        问题.append(f"窗已关闭但缺冻结戳（禁止关闭成功而戳空）:{窗键}")
        return None, 问题
    if not 戳["戳号"]:
        问题.append("冻结戳戳号为空（禁止无戳号）")
    if 戳["关闭时刻"] != 窗["关闭处理时"]:
        问题.append(f"戳关闭时刻{戳['关闭时刻']} != 窗关闭处理时{窗['关闭处理时']}")
    if int(戳["可否准时续写"]) != 0:
        问题.append("戳标记可准时续写，违反关闭即冻结（乙口径污染）")
    发射 = conn.execute("SELECT * FROM 关窗发射 WHERE 窗键=?", (窗键,)).fetchone()
    if not 发射:
        问题.append("已关闭有戳但缺关窗发射记录（半截关窗）")
        return 戳, 问题
    期望哈希 = 快照哈希(
        窗键, 发射["发射处理时"], 发射["发射号"], 发射["关闭时水位"],
        发射["快照点赞"], 发射["快照送礼"], 发射["快照笔数"], 发射["快照版本"], 发射["口径"],
    )
    if 戳["发射快照哈希"] != 期望哈希:
        问题.append("发射快照哈希失配（戳非本窗本票发射所出）")
    if 戳["戳号"] and 戳["戳号"] != 生成戳号(窗键, 发射["发射处理时"], 期望哈希):
        问题.append("戳号失配（非本窗本票所出，疑似邻窗戳串用）")
    return 戳, 问题


def 消化准时写(conn, 窗) -> object:
    """准时写闸（甲·以戳号前置拒绝为准）：同窗准时写必须先消化冻结戳。

    核证有效 → 返回戳行，调用方据此写拒收证据（冻结合计不动）；
    缺戳/失配 → 缺戳异常，整票拒绝、装载事务整体回滚，事件只能改入新窗。
    """
    戳, 问题 = 核证窗戳(conn, 窗["窗键"])
    if 戳 is None or 问题:
        raise 缺戳异常(
            f"同窗准时写缺有效冻结戳，整票拒绝（事件只能改入新窗）: "
            f"窗={窗['窗键']} 问题={'；'.join(问题)}"
        )
    return 戳


def 查冻结戳(conn, 窗键: str | None = None) -> dict:
    """冻结戳核证只读接口（甲口径）：逐戳核证 + 缺戳/早戳/串用全局扫描。"""
    问题 = []
    出 = []
    if 窗键:
        窗键列 = [窗键]
    else:
        窗键列 = [r["窗键"] for r in conn.execute("SELECT DISTINCT 窗键 FROM 发射冻结戳")]
    for wk in 窗键列:
        戳, 戳问题 = 核证窗戳(conn, wk)
        if 戳:
            出.append({**dict(戳), "有效": not 戳问题, "核证问题": 戳问题})
        问题.extend(戳问题)
    if not 窗键:
        for r in conn.execute(
            "SELECT w.窗键 FROM 热度窗 w LEFT JOIN 发射冻结戳 d ON d.窗键=w.窗键 "
            "WHERE w.状态='已关闭' AND d.窗键 IS NULL"
        ):
            问题.append(f"已关闭窗缺冻结戳:{r['窗键']}")
        for r in conn.execute(
            "SELECT d.窗键 FROM 发射冻结戳 d LEFT JOIN 热度窗 w ON w.窗键=d.窗键 "
            "WHERE w.窗键 IS NULL"
        ):
            问题.append(f"冻结戳指向不存在的窗:{r['窗键']}")
        for r in conn.execute(
            "SELECT 戳号, COUNT(*) AS c FROM 发射冻结戳 GROUP BY 戳号 HAVING c>1"
        ):
            问题.append(f"戳号串用:{r['戳号']} 出现{r['c']}次")
    return {
        "口径": 口径,
        "写闸校验戳": True,
        "可准时续写": False,
        "冻结戳": 出,
        "问题": 问题,
        "valid": not 问题,
    }
