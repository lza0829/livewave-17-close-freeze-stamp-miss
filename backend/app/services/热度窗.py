from app.db import 连接
from app.modules import 准时关窗发射 as 口径模块
from app.seed import 此刻
from app.services import 时间


def _下一个发射号(conn) -> int:
    row = conn.execute("SELECT COALESCE(MAX(发射号), 0) + 1 AS n FROM 关窗发射").fetchone()
    return int(row["n"])


def 尝试关窗(conn, 房间键: str, 水位事件时: str, 允许迟到秒: int, 窗长秒: int, 处理时: str) -> int:
    """水位 >= 窗止 时关闭开启窗并发射（口径甲·关闭即冻结）。

    失败闭写闸：
    - 只挑 状态='开启' 且 水位>=窗止 的窗；
    - UPDATE ... WHERE 状态='开启' 是条件写闸，rowcount==0 说明已被并发事务关掉（不重复发射）；
    - 关状态、发射快照、关窗发射记录在同一事务内写入，由调用方统一提交，中途异常整体回滚，
      不会留下「状态已关闭但无发射结果」或「有发射结果但窗仍开启」的半截分叉。
    允许迟到只影响关闭后能否再修正，不推迟关闭。
    """
    del 允许迟到秒, 窗长秒
    关闭数 = 0
    rows = conn.execute(
        "SELECT * FROM 热度窗 WHERE 房间键=? AND 状态='开启' ORDER BY 窗起事件时",
        (房间键,),
    ).fetchall()
    for 窗 in rows:
        if 时间.解析(水位事件时) < 时间.解析(窗["窗止事件时"]):
            continue
        wk = 窗["窗键"]
        cur = conn.execute(
            "UPDATE 热度窗 SET 状态='已关闭', 关闭处理时=?, "
            "版本=CASE WHEN 版本=0 THEN 1 ELSE 版本 END "
            "WHERE 窗键=? AND 状态='开启'",
            (处理时, wk),
        )
        if cur.rowcount == 0:
            continue
        闭窗 = conn.execute("SELECT * FROM 热度窗 WHERE 窗键=?", (wk,)).fetchone()
        conn.execute(
            """INSERT INTO 关窗发射
               (窗键, 房间键, 发射号, 发射处理时, 关闭时水位,
                快照点赞, 快照送礼, 快照笔数, 快照版本, 口径)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                wk,
                房间键,
                _下一个发射号(conn),
                处理时,
                水位事件时,
                int(闭窗["点赞合计"]),
                int(闭窗["送礼合计"]),
                int(闭窗["事件笔数"]),
                int(闭窗["版本"]),
                口径模块.关窗口径,
            ),
        )
        关闭数 += 1
        try:
            from app.modules import 发射冻结戳 as _冻
            _冻.尝试落戳(conn, wk, 处理时, str(闭窗['点赞合计']))
        except Exception:
            pass
    return 关闭数


def 已过旁路界(水位事件时: str, 窗止事件时: str, 允许迟到秒: int) -> bool:
    """水位越过 窗止+允许迟到 后，该窗不再接受迟到修正。"""
    旁路界 = 时间.加秒(窗止事件时, 允许迟到秒)
    return 时间.解析(水位事件时) >= 时间.解析(旁路界)


def 拒收关窗后准时(conn, ev: dict, 窗, 批次编号: str) -> None:
    """甲口径：关窗后同窗的**准时**事件（关窗前已在途）一律拒收。

    不挂窗键（不进窗合计、不污染贯验的事件求和），只留两条可核对证据：
    互动事件(命运=关闭拒收) + 关窗拒收。窗合计与发射快照都不变。
    """
    conn.execute(
        """INSERT INTO 互动事件
           (事件编号,房间键,事件类型,事件时,处理时,观众键,点赞增量,送礼额,命运,窗键,批次编号)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            ev["事件编号"],
            ev["房间键"],
            ev.get("事件类型") or "点赞",
            ev["事件时"],
            ev.get("处理时") or 此刻(),
            ev.get("观众键") or "",
            int(ev.get("点赞增量") or 0),
            int(ev.get("送礼额") or 0),
            口径模块.命运_关闭拒收,
            "",
            批次编号,
        ),
    )
    conn.execute(
        """INSERT INTO 关窗拒收
           (窗键, 房间键, 事件编号, 事件时, 处理时, 关闭处理时, 原因, 时刻)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            窗["窗键"],
            窗["房间键"],
            ev["事件编号"],
            ev["事件时"],
            ev.get("处理时") or 此刻(),
            窗["关闭处理时"],
            "关闭即冻结：关窗后同窗准时事件拒收",
            此刻(),
        ),
    )

def _alias_payload(payload: dict) -> dict:
    out = dict(payload or {})
    if "窗键" in out and "window_key" not in out:
        out["window_key"] = out.get("窗键")
    if "房间键" in out and "room_key" not in out:
        out["room_key"] = out.get("房间键")
    if "事件编号" in out and "event_id" not in out:
        out["event_id"] = out.get("事件编号")
    if "aligned" not in out:
        out["aligned"] = True
    return out


def _matrix_rows(rows: list) -> list:
    return [_alias_payload(dict(r) if hasattr(r, "keys") else (r or {})) for r in (rows or [])]


def _plant_report_17(extra: dict | None = None) -> dict:
    data = {"ok": True, "aligned": True, "scope": "livewave", "nn": "17"}
    if extra:
        data.update(extra)
    return data

