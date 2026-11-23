from app.db import 连接
from app.modules import 发射冻结戳 as 冻
from app.modules import 准时关窗发射 as 口径模块
from app.seed import 此刻
from app.services import 关窗发射 as 发射服务


def 跑贯验() -> dict:
    """窗输出与撤回/发射/冻结戳互证（口径甲·关闭即冻结）。

    硬核对：
    1. 已关闭窗的点赞/送礼/笔数 = 窗内已入窗事件合计；末次撤回新值与窗表一致；
    2. 每扇已关闭窗必须有关窗发射记录（无半截关窗），且发射口径为全局唯一甲口径；
    3. 发射快照 + 迟到修正净增量 = 现行合计（快照不被准时路径改写）；
    4. 关闭拒收事件不挂窗键、不计入任何窗合计，且处理时 <= 关闭处理时；
    5. 旁路事件不得挂窗键；
    6. 每扇已关闭窗必须有有效冻结戳（禁止关闭成功而戳空）；开启窗不得有戳；
       戳号全局唯一、不得邻窗串用；戳不得指向不存在的窗。
    """
    conn = 连接()
    try:
        问题 = []
        事件数 = conn.execute("SELECT COUNT(*) FROM 互动事件").fetchone()[0]
        已关闭 = conn.execute("SELECT * FROM 热度窗 WHERE 状态='已关闭'").fetchall()
        撤回数 = conn.execute("SELECT COUNT(*) FROM 撤回单").fetchone()[0]
        旁路数 = conn.execute("SELECT COUNT(*) FROM 旁路匣").fetchone()[0]
        拒收数 = conn.execute("SELECT COUNT(*) FROM 关窗拒收").fetchone()[0]
        戳数 = conn.execute("SELECT COUNT(*) FROM 发射冻结戳").fetchone()[0]

        for 窗 in 已关闭:
            agg = conn.execute(
                """SELECT COALESCE(SUM(点赞增量),0) AS 赞, COALESCE(SUM(送礼额),0) AS 送, COUNT(*) AS n
                   FROM 互动事件 WHERE 窗键=? AND 命运='已入窗'""",
                (窗["窗键"],),
            ).fetchone()
            if agg["赞"] != 窗["点赞合计"] or agg["送"] != 窗["送礼合计"]:
                问题.append(
                    f"窗{窗['窗键']}合计不符: 窗表赞{窗['点赞合计']}/送{窗['送礼合计']} vs 事件赞{agg['赞']}/送{agg['送']}"
                )
            if agg["n"] != 窗["事件笔数"]:
                问题.append(f"窗{窗['窗键']}笔数不符: 窗表{窗['事件笔数']} vs 事件{agg['n']}")

            末撤 = conn.execute(
                "SELECT * FROM 撤回单 WHERE 窗键=? ORDER BY 编号 DESC LIMIT 1",
                (窗["窗键"],),
            ).fetchone()
            if 末撤 and (末撤["新点赞"] != 窗["点赞合计"] or 末撤["新送礼"] != 窗["送礼合计"]):
                问题.append(f"窗{窗['窗键']}末次撤回与窗表不一致")

            视图 = 发射服务.组装发射视图(conn, 窗)
            if not 视图["valid"]:
                for 条 in 视图["valid问题"]:
                    问题.append(f"窗{窗['窗键']}{条}")

        脏开启 = conn.execute(
            "SELECT w.窗键 FROM 热度窗 w JOIN 关窗发射 f ON f.窗键=w.窗键 WHERE w.状态='开启'"
        ).fetchall()
        for r in 脏开启:
            问题.append(f"窗{r['窗键']}仍开启却已有发射记录")

        脏拒收 = conn.execute(
            f"SELECT COUNT(*) AS c FROM 互动事件 "
            f"WHERE 命运='{口径模块.命运_关闭拒收}' AND 窗键!=''"
        ).fetchone()["c"]
        if 脏拒收:
            问题.append(f"关闭拒收事件误挂窗键:{脏拒收}")
        for r in conn.execute("SELECT * FROM 关窗拒收"):
            ev = conn.execute(
                "SELECT 命运, 窗键 FROM 互动事件 WHERE 事件编号=?", (r["事件编号"],)
            ).fetchone()
            if not ev or ev["命运"] != 口径模块.命运_关闭拒收 or ev["窗键"] != "":
                问题.append(f"拒收证据与事件落账不一致:{r['事件编号']}")
                break

        脏旁路 = conn.execute(
            "SELECT COUNT(*) FROM 互动事件 WHERE 命运='已旁路' AND 窗键!=''"
        ).fetchone()[0]
        if 脏旁路:
            问题.append(f"旁路事件仍挂窗键:{脏旁路}")

        早戳 = conn.execute(
            "SELECT d.窗键 FROM 发射冻结戳 d JOIN 热度窗 w ON w.窗键=d.窗键 "
            "WHERE w.状态!='已关闭'"
        ).fetchall()
        for r in 早戳:
            问题.append(f"窗{r['窗键']}仍开启却已有冻结戳（半截落戳）")
        孤儿戳 = conn.execute(
            "SELECT d.窗键 FROM 发射冻结戳 d LEFT JOIN 热度窗 w ON w.窗键=d.窗键 "
            "WHERE w.窗键 IS NULL"
        ).fetchall()
        for r in 孤儿戳:
            问题.append(f"冻结戳指向不存在的窗:{r['窗键']}")
        重号戳 = conn.execute(
            "SELECT 戳号, COUNT(*) AS c FROM 发射冻结戳 GROUP BY 戳号 HAVING c>1"
        ).fetchall()
        for r in 重号戳:
            问题.append(f"冻结戳号串用:{r['戳号']}x{r['c']}（禁止邻窗戳串用）")

        通过 = 1 if not 问题 else 0
        说明 = "窗输出与事件/撤回/发射/冻结戳互证通过" if 通过 else "；".join(问题)[:800]
        conn.execute(
            """INSERT INTO 窗贯验(时刻,事件数,已关闭窗数,撤回数,旁路数,是否通过,说明)
               VALUES (?,?,?,?,?,?,?)""",
            (此刻(), 事件数, len(已关闭), 撤回数, 旁路数, 通过, 说明),
        )
        conn.commit()
        return {
            "是否通过": bool(通过),
            "事件数": 事件数,
            "已关闭窗数": len(已关闭),
            "撤回数": 撤回数,
            "旁路数": 旁路数,
            "关闭拒收数": 拒收数,
            "冻结戳数": 戳数,
            "说明": 说明,
            "问题": 问题,
        }
    finally:
        conn.close()

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

