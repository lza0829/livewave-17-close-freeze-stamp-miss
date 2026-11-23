from datetime import datetime, timezone

from app.db import 连接

建表 = """
CREATE TABLE IF NOT EXISTS 发射冻结戳 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  窗键 TEXT NOT NULL,
  关闭时刻 TEXT NOT NULL DEFAULT '',
  发射快照哈希 TEXT NOT NULL DEFAULT '',
  戳号 TEXT NOT NULL DEFAULT '',
  可否准时续写 INTEGER NOT NULL DEFAULT 0,
  时刻 TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS 站规 (
  键 TEXT PRIMARY KEY,
  值 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 直播间 (
  房间键 TEXT PRIMARY KEY,
  标题 TEXT NOT NULL,
  主播 TEXT NOT NULL,
  开播事件时 TEXT NOT NULL,
  状态 TEXT NOT NULL DEFAULT '直播中'
);
CREATE TABLE IF NOT EXISTS 互动事件 (
  事件编号 TEXT PRIMARY KEY,
  房间键 TEXT NOT NULL REFERENCES 直播间(房间键),
  事件类型 TEXT NOT NULL,
  事件时 TEXT NOT NULL,
  处理时 TEXT NOT NULL,
  观众键 TEXT NOT NULL DEFAULT '',
  点赞增量 INTEGER NOT NULL DEFAULT 0,
  送礼额 INTEGER NOT NULL DEFAULT 0,
  命运 TEXT NOT NULL DEFAULT '已入流',
  窗键 TEXT NOT NULL DEFAULT '',
  批次编号 TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS 装载批次 (
  编号 TEXT PRIMARY KEY,
  时刻 TEXT NOT NULL,
  报告 TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS 水位线 (
  房间键 TEXT PRIMARY KEY REFERENCES 直播间(房间键),
  事件时水位 TEXT NOT NULL,
  允许迟到秒 INTEGER NOT NULL DEFAULT 30,
  更新处理时 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 热度窗 (
  窗键 TEXT PRIMARY KEY,
  房间键 TEXT NOT NULL REFERENCES 直播间(房间键),
  窗起事件时 TEXT NOT NULL,
  窗止事件时 TEXT NOT NULL,
  状态 TEXT NOT NULL DEFAULT '开启',
  点赞合计 INTEGER NOT NULL DEFAULT 0,
  送礼合计 INTEGER NOT NULL DEFAULT 0,
  事件笔数 INTEGER NOT NULL DEFAULT 0,
  关闭处理时 TEXT NOT NULL DEFAULT '',
  版本 INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS 撤回单 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  窗键 TEXT NOT NULL,
  房间键 TEXT NOT NULL,
  原因 TEXT NOT NULL,
  旧点赞 INTEGER NOT NULL,
  新点赞 INTEGER NOT NULL,
  旧送礼 INTEGER NOT NULL,
  新送礼 INTEGER NOT NULL,
  处理时 TEXT NOT NULL,
  事件编号 TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS 旁路匣 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  原因 TEXT NOT NULL,
  载荷 TEXT NOT NULL,
  时刻 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 窗贯验 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  时刻 TEXT NOT NULL,
  事件数 INTEGER NOT NULL,
  已关闭窗数 INTEGER NOT NULL,
  撤回数 INTEGER NOT NULL,
  旁路数 INTEGER NOT NULL,
  是否通过 INTEGER NOT NULL,
  说明 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 关窗发射 (
  窗键 TEXT PRIMARY KEY REFERENCES 热度窗(窗键),
  房间键 TEXT NOT NULL,
  发射号 INTEGER NOT NULL,
  发射处理时 TEXT NOT NULL,
  关闭时水位 TEXT NOT NULL,
  快照点赞 INTEGER NOT NULL,
  快照送礼 INTEGER NOT NULL,
  快照笔数 INTEGER NOT NULL,
  快照版本 INTEGER NOT NULL,
  口径 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 关窗拒收 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  窗键 TEXT NOT NULL,
  房间键 TEXT NOT NULL,
  事件编号 TEXT NOT NULL,
  事件时 TEXT NOT NULL,
  处理时 TEXT NOT NULL,
  关闭处理时 TEXT NOT NULL,
  原因 TEXT NOT NULL,
  时刻 TEXT NOT NULL
);
"""


def 此刻() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def 初始化库() -> None:
    conn = 连接()
    conn.executescript(建表)
    conn.execute(
        "INSERT INTO 站规(键, 值) VALUES (?, ?) "
        "ON CONFLICT(键) DO UPDATE SET 值=excluded.值",
        ("关窗口径", "关闭即冻结"),
    )
    if conn.execute("SELECT COUNT(*) AS c FROM 站规").fetchone()["c"] == 0:
        for k, v in {
            "站名": "播浪",
            "窗长秒": "60",
            "允许迟到秒": "30",
            "水位推进策略": "事件时最大值",
            "关窗条件": "水位>=窗止即关闭发射",
            "旁路条件": "水位>=窗止+允许迟到",
            "关窗后准时事件": "拒收（关闭即冻结；仅显式迟到修正可改现行合计）",
            "骨架": "互动事件入流→事件时间水位线推进→热度窗关闭发射→迟到修正撤回→窗输出与撤回互证",
        }.items():
            conn.execute("INSERT INTO 站规(键, 值) VALUES (?, ?)", (k, v))
    else:
        for k, v in {
            "关窗条件": "水位>=窗止即关闭发射",
            "关窗后准时事件": "拒收（关闭即冻结；仅显式迟到修正可改现行合计）",
        }.items():
            conn.execute(
                "INSERT INTO 站规(键, 值) VALUES (?, ?) "
                "ON CONFLICT(键) DO NOTHING",
                (k, v),
            )
    if conn.execute("SELECT COUNT(*) AS c FROM 直播间").fetchone()["c"] == 0:
        conn.execute(
            "INSERT INTO 直播间(房间键, 标题, 主播, 开播事件时, 状态) VALUES (?,?,?,?,?)",
            ("房A", "晚间热聊", "主播小浪", "2026-11-22T12:00:00Z", "直播中"),
        )
        conn.execute(
            "INSERT INTO 水位线(房间键, 事件时水位, 允许迟到秒, 更新处理时) VALUES (?,?,?,?)",
            ("房A", "2026-11-22T12:00:00Z", 30, 此刻()),
        )
    conn.commit()
    conn.close()
