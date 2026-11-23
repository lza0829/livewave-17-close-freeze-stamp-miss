from app.modules import 发射冻结戳 as 冻
from app.modules import 准时关窗发射 as 口径模块
from app.services import 时间


def _拒收证据(conn, 窗键: str) -> list:
    return [
        dict(r)
        for r in conn.execute(
            "SELECT 编号, 窗键, 事件编号, 事件时, 处理时, 关闭处理时, 原因, 戳号 "
            "FROM 关窗拒收 WHERE 窗键=? ORDER BY 编号",
            (窗键,),
        ).fetchall()
    ]


def _冻结戳视图(戳, 戳问题: list) -> dict | None:
    if not 戳:
        return None
    return {
        "戳号": 戳["戳号"],
        "关闭时刻": 戳["关闭时刻"],
        "发射快照哈希": 戳["发射快照哈希"],
        "可否准时续写": bool(戳["可否准时续写"]),
        "有效": not 戳问题,
        "核证问题": 戳问题,
    }


def 组装发射视图(conn, 窗) -> dict:
    """单扇窗的关窗发射只读视图（含冻结戳核证）。"""
    wk = 窗["窗键"]
    发射 = conn.execute("SELECT * FROM 关窗发射 WHERE 窗键=?", (wk,)).fetchone()
    拒收 = _拒收证据(conn, wk)
    戳, 戳问题 = 冻.核证窗戳(conn, wk)

    撤回 = [
        dict(r)
        for r in conn.execute(
            "SELECT 编号, 原因, 旧点赞, 新点赞, 旧送礼, 新送礼, 处理时, 事件编号 "
            "FROM 撤回单 WHERE 窗键=? ORDER BY 编号",
            (wk,),
        ).fetchall()
    ]

    事件和 = conn.execute(
        "SELECT COALESCE(SUM(点赞增量),0) AS 赞, COALESCE(SUM(送礼额),0) AS 送, COUNT(*) AS n "
        "FROM 互动事件 WHERE 窗键=? AND 命运='已入窗'",
        (wk,),
    ).fetchone()

    视图 = {
        "窗键": wk,
        "房间键": 窗["房间键"],
        "窗起事件时": 窗["窗起事件时"],
        "窗止事件时": 窗["窗止事件时"],
        "关闭态": 窗["状态"],
        "关闭处理时": 窗["关闭处理时"],
        "口径": 口径模块.关窗口径,
        "冻结戳": _冻结戳视图(戳, 戳问题),
        "valid": False,
        "valid问题": [],
    }

    if 窗["状态"] != "已关闭":
        视图.update(
            {
                "已发射": False,
                "发射号": None,
                "发射快照": None,
                "现行合计": None,
                "拒收证据": [],
                "续写证据": [],
                "迟到修正证据": [],
            }
        )
        视图["valid问题"] = (["窗仍开启，尚无发射结果"] if 发射 else []) + 戳问题
        视图["valid"] = not 发射 and not 戳问题
        return 视图

    if not 发射:
        视图.update(
            {
                "已发射": False,
                "发射号": None,
                "发射快照": None,
                "现行合计": {
                    "点赞合计": 窗["点赞合计"],
                    "送礼合计": 窗["送礼合计"],
                    "事件笔数": 窗["事件笔数"],
                    "版本": 窗["版本"],
                },
                "拒收证据": 拒收,
                "续写证据": [],
                "迟到修正证据": 撤回,
            }
        )
        视图["valid问题"] = ["状态已关闭但缺少关窗发射记录（半截关窗）"] + 戳问题
        视图["valid"] = False
        return 视图

    快照 = {
        "点赞": 发射["快照点赞"],
        "送礼": 发射["快照送礼"],
        "笔数": 发射["快照笔数"],
        "版本": 发射["快照版本"],
    }
    现行 = {
        "点赞合计": 窗["点赞合计"],
        "送礼合计": 窗["送礼合计"],
        "事件笔数": 窗["事件笔数"],
        "版本": 窗["版本"],
    }
    视图.update(
        {
            "已发射": True,
            "发射号": 发射["发射号"],
            "发射处理时": 发射["发射处理时"],
            "关闭时水位": 发射["关闭时水位"],
            "发射快照": 快照,
            "现行合计": 现行,
            "续写证据": [],
            "拒收证据": 拒收,
            "迟到修正证据": 撤回,
        }
    )

    问题 = []
    问题.extend(戳问题)
    if 发射["口径"] != 口径模块.关窗口径:
        问题.append(f"发射口径污染:{发射['口径']}")
    if (事件和["赞"], 事件和["送"], 事件和["n"]) != (
        窗["点赞合计"],
        窗["送礼合计"],
        窗["事件笔数"],
    ):
        问题.append(
            f"现行合计与窗内事件分叉: 窗{窗['点赞合计']}/{窗['送礼合计']}/{窗['事件笔数']}"
            f" vs 事件{事件和['赞']}/{事件和['送']}/{事件和['n']}"
        )
    修正赞 = sum(int(r["新点赞"]) - int(r["旧点赞"]) for r in 撤回)
    修正送 = sum(int(r["新送礼"]) - int(r["旧送礼"]) for r in 撤回)
    if (
        快照["点赞"] + 修正赞 != 窗["点赞合计"]
        or 快照["送礼"] + 修正送 != 窗["送礼合计"]
    ):
        问题.append("发射快照+迟到修正净增量 != 现行合计（快照被改写或修正链断裂）")
    for r in 拒收:
        ev = conn.execute(
            "SELECT 命运, 窗键 FROM 互动事件 WHERE 事件编号=?", (r["事件编号"],)
        ).fetchone()
        if not ev or ev["命运"] != 口径模块.命运_关闭拒收 or ev["窗键"] != "":
            问题.append(f"拒收证据缺事件落账或误挂窗键:{r['事件编号']}")
            break
        if 时间.解析(r["处理时"]) > 时间.解析(r["关闭处理时"]):
            问题.append(f"拒收事件处理时晚于关窗，不应按准时拒收:{r['事件编号']}")
            break

    视图["valid问题"] = 问题
    视图["valid"] = not 问题
    return 视图


def 列发射视图(conn, 状态过滤: str = "") -> list:
    if 状态过滤:
        rows = conn.execute(
            "SELECT * FROM 热度窗 WHERE 状态=? ORDER BY 窗起事件时 DESC", (状态过滤,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM 热度窗 ORDER BY 窗起事件时 DESC").fetchall()
    return [组装发射视图(conn, r) for r in rows]


def 取单窗(conn, 窗键: str) -> dict | None:
    窗 = conn.execute("SELECT * FROM 热度窗 WHERE 窗键=?", (窗键,)).fetchone()
    if not 窗:
        return None
    return 组装发射视图(conn, 窗)
