import React, { useEffect, useState } from "react";
import { 取 } from "../api.js";

export default function 热度窗页() {
  const [窗, 设] = useState([]);
  const [滤, 设滤] = useState("");
  const 刷 = () => 取("/热度窗" + (滤 ? `?状态=${encodeURIComponent(滤)}` : "")).then(设);
  useEffect(() => { 刷(); }, [滤]);
  return (
    <div>
      <h1 className="题">③ 热度窗</h1>
      <p className="述">
        按事件时翻滚对齐的热度窗。口径 <strong>关闭即冻结</strong>：开启时累计点赞/送礼；水位越过窗止即在
        关窗事务内物化「发射快照」并置已关闭。关窗后同窗准时事件拒收（合计与快照不变），仅显式迟到修正
        可升现行合计，发射快照始终冻结在关窗瞬间。
      </p>
      <div className="行">
        {["", "开启", "已关闭"].map((s) => (
          <button key={s || "全"} className={`次 ${滤 === s ? "亮片" : ""}`} onClick={() => 设滤(s)}>
            {s || "全部"}
          </button>
        ))}
        <button className="次" onClick={刷}>刷新窗</button>
      </div>
      {!窗.length ? (
        <div className="空态">暂无热度窗。先去事件流推准时样例。</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>窗键</th><th>房间</th><th>窗起</th><th>窗止</th><th>状态</th>
              <th>点赞合计</th><th>送礼合计</th><th>笔数</th><th>版本</th>
              <th>发射快照(赞/送)</th><th>关闭处理时</th><th>valid</th>
            </tr>
          </thead>
          <tbody>
            {窗.map((r) => {
              const v = r.发射视图 || {};
              return (
                <tr key={r.窗键}>
                  <td className="码">{r.窗键}</td><td>{r.房间键}</td>
                  <td className="码">{r.窗起事件时}</td><td className="码">{r.窗止事件时}</td>
                  <td>{r.状态}</td><td>{r.点赞合计}</td><td>{r.送礼合计}</td>
                  <td>{r.事件笔数}</td><td>{r.版本}</td>
                  <td className="码">
                    {v.已发射 ? `${v.发射快照.点赞}/${v.发射快照.送礼}` : "—"}
                  </td>
                  <td className="码">{r.关闭处理时 || "—"}</td>
                  <td><span className={`徽章 ${v.valid ? "通" : "败"}`}>{v.valid ? "valid" : "invalid"}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
