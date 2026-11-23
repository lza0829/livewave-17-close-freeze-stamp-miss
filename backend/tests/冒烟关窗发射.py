import os
import sys
import tempfile

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND)
os.environ["数据目录"] = tempfile.mkdtemp(prefix="livewave-http-")
os.environ["夹具目录"] = os.path.join(os.path.dirname(_BACKEND), "fixtures")

from fastapi.testclient import TestClient
from app.main import app

ok = 0
bad = 0


def 检查(cond, msg):
    global ok, bad
    if cond:
        ok += 1
        print(f"  ✓ {msg}")
    else:
        bad += 1
        print(f"  ✗ {msg}")


with TestClient(app) as c:
    print("健康/站规")
    检查(c.get("/api/健康").json()["正常"] is True, "健康检查")
    规 = c.get("/api/站规").json()
    检查(规.get("关窗口径") == "关闭即冻结", "站规全局口径=关闭即冻结")

    print("夹具① 准时 → 关窗发射")
    r = c.post("/api/装载/夹具", params={"名": "准时热度样例"}).json()
    检查(r["新关窗"] >= 1, "准时样例触发关窗")
    wk = "房A|2026-11-22T12:00:00Z"

    print("只读接口 GET /api/关窗发射（列表）")
    lst = c.get("/api/关窗发射").json()
    w1v = next(x for x in lst if x["窗键"] == wk)
    检查(w1v["关闭态"] == "已关闭" and w1v["已发射"] is True, "列表含已关闭且已发射窗")
    检查(w1v["发射快照"]["点赞"] == 3 and w1v["发射快照"]["送礼"] == 50, "发射快照 赞3/送50")
    检查(w1v["valid"] is True and w1v["续写证据"] == [], "valid=True 且无续写证据")
    检查({"窗键", "关闭态", "发射快照", "现行合计", "拒收证据", "续写证据", "valid"} <= set(w1v),
          "只读字段齐全（窗键/关闭态/快照或现行/证据/valid）")

    print("只读接口 GET /api/关窗发射?窗键=（单窗）")
    one = c.get("/api/关窗发射", params={"窗键": wk}).json()
    检查(one["窗键"] == wk and one["valid"] is True, "单窗接口返回且 valid")
    检查(c.get("/api/关窗发射", params={"窗键": "房A|不存在"}).status_code == 404, "未知窗键 404")

    print("夹具② 关窗后只推同窗准时 → 拒收、合计不变")
    c.post("/api/装载/夹具", params={"名": "关窗准时拒收样例"})
    one2 = c.get("/api/关窗发射", params={"窗键": wk}).json()
    检查(one2["现行合计"]["点赞合计"] == 3 and one2["现行合计"]["送礼合计"] == 50,
          "拒收后现行合计不变（甲口径）")
    检查(len(one2["拒收证据"]) == 2 and one2["发射快照"]["点赞"] == 3,
          "拒收证据 2 笔且发射快照不动")
    检查(one2["valid"] is True, "拒收后单窗接口仍 valid")
    检查(all(r["戳号"] for r in one2["拒收证据"]), "拒收证据携带冻结戳号")

    print("冻结戳核证只读接口 GET /api/核证/冻结戳")
    z = c.get("/api/核证/冻结戳").json()
    检查(z["写闸校验戳"] is True and z["可准时续写"] is False, "核证接口宣告甲口径写闸核戳")
    检查(z["valid"] is True and any(r["窗键"] == wk and r["有效"] for r in z["冻结戳"]),
          "全库冻结戳核证通过且含 W1 有效戳")
    z1 = c.get("/api/核证/冻结戳", params={"窗键": wk}).json()
    检查(z1["valid"] is True and z1["冻结戳"][0]["戳号"], "单窗冻结戳核证通过且戳号非空")
    检查(one2["冻结戳"] and one2["冻结戳"]["有效"] is True, "发射视图携带有效冻结戳")

    print("夹具③ 迟到修正 → 现行升、快照冻结")
    c.post("/api/装载/夹具", params={"名": "迟到修正样例"})
    one3 = c.get("/api/关窗发射", params={"窗键": wk}).json()
    检查(one3["现行合计"]["点赞合计"] == 7 and one3["发射快照"]["点赞"] == 3,
          "现行合计升到7，发射快照冻结在3")
    检查(len(one3["迟到修正证据"]) == 1 and one3["valid"] is True, "迟到修正证据1笔且 valid")

    print("删戳再投同窗准时包 → HTTP 409 整票拒绝、累计不变")
    from app.db import 连接 as 库连接
    conn = 库连接()
    存戳 = dict(conn.execute("SELECT * FROM 发射冻结戳 WHERE 窗键=?", (wk,)).fetchone())
    conn.execute("DELETE FROM 发射冻结戳 WHERE 窗键=?", (wk,))
    conn.commit()
    conn.close()
    r409 = c.post("/api/装载/夹具", params={"名": "删戳再投准时样例"})
    检查(r409.status_code == 409 and r409.json()["命运"] == "整票拒绝",
          "缺戳准时写 → 409 整票拒绝")
    one4 = c.get("/api/关窗发射", params={"窗键": wk}).json()
    检查(one4["现行合计"]["点赞合计"] == 7 and one4["现行合计"]["送礼合计"] == 50,
          "整票回滚：现行合计不变（乙口径此处会累加）")
    检查(one4["valid"] is False and one4["冻结戳"] is None, "发射视图抓获缺戳（valid=False）")
    conn = 库连接()
    conn.execute(
        "INSERT INTO 发射冻结戳(窗键,关闭时刻,发射快照哈希,戳号,可否准时续写,时刻) VALUES (?,?,?,?,?,?)",
        (存戳["窗键"], 存戳["关闭时刻"], 存戳["发射快照哈希"], 存戳["戳号"], 存戳["可否准时续写"], 存戳["时刻"]),
    )
    conn.commit()
    conn.close()
    z2 = c.get("/api/核证/冻结戳", params={"窗键": wk}).json()
    检查(z2["valid"] is True, "还原冻结戳后核证恢复通过")

    print("热度窗列表内嵌发射视图 + 窗互证")
    hw = c.get("/api/热度窗").json()
    嵌入 = next(x for x in hw if x["窗键"] == wk)
    检查("发射视图" in 嵌入 and 嵌入["发射视图"]["valid"] is True, "/热度窗 内嵌发射视图")
    g = c.post("/api/贯验").json()
    检查(g["是否通过"] is True and g["关闭拒收数"] >= 2, f"窗互证通过（{g['说明']}）")

print(f"\nHTTP 冒烟结果：通过 {ok} / 失败 {bad}")
sys.exit(1 if bad else 0)
