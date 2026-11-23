import React, { useEffect, useState } from "react";
import { 取 } from "../api.js";

export default function 关窗发射页() {
  const [列, 设列] = useState([]);
  const [滤, 设滤] = useState("");
  const 刷 = () => 取("/关窗发射" + (滤 ? `?状态=${encodeURIComponent(滤)}` : "")).then(设列);
  useEffect(() => { 刷(); }, [滤]);
  return (
    <div>
      <h1 className="题">关窗发射（只读）</h1>
      <p className="述">
        全局口径 <strong>关闭即冻结</strong>：水位越过窗止即在同一关窗事务内物化发射快照。
        关窗后同窗<strong>准时</strong>事件（处理时 ≤ 关闭处理时）一律拒收、不挂窗键、合计与快照不变；
        仅显式迟到修正可改现行合计（发射快照仍冻结）。本页只读，核对每扇窗的关闭态、发射快照、
        现行合计、拒收/续写证据与 valid。
      </p>
      <div className="行">
        {["", "开启", "已关闭"].map((s) => (
          <button key={s || "全"} className={`次 ${滤 === s ? "亮片" : ""}`} onClick={() => 设滤(s)}>
            {s || "全部"}
          </button>
        ))}
        <button className="次" onClick={刷}>刷新发射</button>
      </div>
      {!列.length ? (
        <div className="空态">暂无热度窗。先去事件流推准时样例。</div>
      ) : (
        <div className="段">
          {列.map((v) => (
            <div key={v.窗键} className="卡" style={{ marginBottom: "0.7rem" }}>
              <div className="行" style={{ marginBottom: "0.4rem" }}>
                <span className="码" style={{ fontWeight: 700 }}>{v.窗键}</span>
                <span className={`徽章 ${v.关闭态 === "已关闭" ? "通" : "败"}`}>{v.关闭态}</span>
                <span className={`徽章 ${v.valid ? "通" : "败"}`}>{v.valid ? "valid" : "invalid"}</span>
                {v.已发射 && <span className="讯" style={{ margin: 0 }}>发射号 #{v.发射号} · {v.发射处理时}</span>}
              </div>
              {v.已发射 ? (
                <table>
                  <thead>
                    <tr><th>维度</th><th>发射快照（冻结）</th><th>现行合计</th></tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>点赞</td><td>{v.发射快照.点赞}</td><td>{v.现行合计.点赞合计}</td>
                    </tr>
                    <tr>
                      <td>送礼</td><td>{v.发射快照.送礼}</td><td>{v.现行合计.送礼合计}</td>
                    </tr>
                    <tr>
                      <td>笔数</td><td>{v.发射快照.笔数}</td><td>{v.现行合计.事件笔数}</td>
                    </tr>
                    <tr>
                      <td>版本</td><td>{v.发射快照.版本}</td><td>{v.现行合计.版本}</td>
                    </tr>
                  </tbody>
                </table>
              ) : (
                <div className="讯">尚未发射（{v.valid问题.join("；") || "窗仍开启"}）</div>
              )}
              <div className="行" style={{ marginTop: "0.5rem", marginBottom: 0 }}>
                <span className="讯" style={{ margin: 0 }}>
                  关闭拒收 {v.拒收证据.length} 笔 · 续写 {v.续写证据.length} 笔 · 迟到修正 {v.迟到修正证据.length} 笔
                </span>
              </div>
              {v.拒收证据.length > 0 && (
                <div className="报箱 码" style={{ marginTop: "0.4rem" }}>
                  {v.拒收证据.map((r) =>
                    `拒收 ${r.事件编号}（处理时 ${r.处理时} ≤ 关闭 ${r.关闭处理时}）：${r.原因}`
                  ).join("\n")}
                </div>
              )}
              {!v.valid && <div className="徽章 败" style={{ marginTop: "0.4rem" }}>{v.valid问题.join("；")}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
