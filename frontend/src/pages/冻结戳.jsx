import React, { useEffect, useState } from "react";
import { 取 } from "../api.js";

export default function 冻结戳() {
  const [核, 设核] = useState(null);
  const [err, setErr] = useState("");
  const [窗键, 设窗键] = useState("");
  const reload = () => {
    取("/核证/冻结戳" + (窗键 ? `?窗键=${encodeURIComponent(窗键)}` : ""))
      .then((d) => { 设核(d); setErr(""); })
      .catch((e) => setErr(String(e.message || e)));
  };
  useEffect(() => { reload(); }, [窗键]);
  return (
    <div>
      <h1 className="题">冻结戳核证（只读）</h1>
      <p className="述">
        全局口径 <strong>关闭即冻结 · 以戳号前置拒绝为准</strong>：关窗事务同票落冻结戳
        （窗键/关闭时刻/发射快照哈希/戳号，戳号由三者确定性派生，邻窗挪用重算必失配）。
        同窗准时写先核戳：戳有效 → 拒收留证、冻结合计不动；缺戳/失配 → 整票拒绝回滚。
      </p>
      <div className="行">
        <input
          className="码"
          placeholder="窗键过滤（可空=全库扫描）"
          value={窗键}
          onChange={(e) => 设窗键(e.target.value)}
          style={{ minWidth: "22rem" }}
        />
        <button className="次" onClick={reload}>刷新核证</button>
      </div>
      {err && <pre className="码">{err}</pre>}
      {核 && (
        <div className="段">
          <div className="行">
            <span className={`徽章 ${核.valid ? "通" : "败"}`}>{核.valid ? "核证通过" : "核证撕裂"}</span>
            <span className={`徽章 ${核.写闸校验戳 ? "通" : "败"}`}>写闸校验戳 {String(核.写闸校验戳)}</span>
            <span className={`徽章 ${核.可准时续写 ? "败" : "通"}`}>可准时续写 {String(核.可准时续写)}</span>
            <span className="讯" style={{ margin: 0 }}>口径 {核.口径}</span>
          </div>
          {核.问题.length > 0 && (
            <div className="报箱 码" style={{ marginTop: "0.5rem" }}>{核.问题.join("\n")}</div>
          )}
          {!核.冻结戳.length ? (
            <div className="空态" style={{ marginTop: "0.6rem" }}>暂无冻结戳。关窗发射时同票落下。</div>
          ) : (
            <table style={{ marginTop: "0.6rem" }}>
              <thead>
                <tr>
                  <th>窗键</th><th>戳号</th><th>关闭时刻</th><th>快照哈希</th><th>可续写</th><th>核证</th>
                </tr>
              </thead>
              <tbody>
                {核.冻结戳.map((r) => (
                  <tr key={r.编号}>
                    <td className="码">{r.窗键}</td>
                    <td className="码">{r.戳号}</td>
                    <td className="码">{r.关闭时刻}</td>
                    <td className="码">{String(r.发射快照哈希).slice(0, 12)}…</td>
                    <td>{r.可否准时续写 ? "是（违规）" : "否"}</td>
                    <td>
                      <span className={`徽章 ${r.有效 ? "通" : "败"}`}>{r.有效 ? "有效" : "失配"}</span>
                      {r.核证问题.length > 0 && <div className="码">{r.核证问题.join("；")}</div>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
