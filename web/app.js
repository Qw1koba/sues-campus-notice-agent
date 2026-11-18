const notice = document.getElementById("notice");
const dateInput = document.getElementById("reference-date");
const analyzeButton = document.getElementById("analyze-button");
const sampleButton = document.getElementById("sample-button");
const emptyState = document.getElementById("empty-state");
const resultContent = document.getElementById("result-content");
const charCount = document.getElementById("char-count");
let currentResult = null;

const escapeHtml = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char]));

notice.addEventListener("input", () => {
  charCount.textContent = `${notice.value.trim().length} 字`;
});

sampleButton.addEventListener("click", async () => {
  const response = await fetch("/api/sample");
  const data = await response.json();
  notice.value = data.text;
  notice.dispatchEvent(new Event("input"));
  notice.focus();
  if (new URLSearchParams(window.location.search).has("demo")) {
    analyzeButton.click();
  }
});

analyzeButton.addEventListener("click", async () => {
  const text = notice.value.trim();
  if (text.length < 8) {
    showError("请输入至少 8 个字符的通知内容。");
    return;
  }
  analyzeButton.disabled = true;
  analyzeButton.querySelector("span").textContent = "正在分析…";
  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, date: dateInput.value }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "分析失败");
    currentResult = data;
    renderResult(data);
  } catch (error) {
    showError(error.message);
  } finally {
    analyzeButton.disabled = false;
    analyzeButton.querySelector("span").textContent = "分析并生成行动清单";
  }
});

function showError(message) {
  emptyState.hidden = true;
  resultContent.hidden = false;
  resultContent.innerHTML = `<div class="error-box">${escapeHtml(message)}</div>`;
}

function statusText(status) {
  if (status === "completed") return ["已完成", ""];
  if (status === "blocked_spam") return ["已拦截", "blocked"];
  if (status === "rejected") return ["无法处理", "blocked"];
  return ["需要确认", "review"];
}

function renderResult(data) {
  emptyState.hidden = true;
  resultContent.hidden = false;
  if (data.error && !data.classification) {
    showError(data.error);
    return;
  }
  const [statusLabel, statusClass] = statusText(data.status);
  const classification = data.classification;
  const extraction = data.extraction;
  const deadline = extraction?.deadline;
  const spam = data.spam_check;
  const confidence = classification?.confidence;
  const category = classification?.category || (data.status === "blocked_spam" ? "风险消息" : "待判断");
  const priorityMap = { high: "紧急", medium: "近期", low: "普通", expired: "已过期", unknown: "待确认" };

  const metrics = classification ? `
    <div class="class-grid">
      <div class="metric">
        <span>业务类别</span>
        <strong>${escapeHtml(category)}</strong>
        <small> · ${escapeHtml(classification.confidence_source || "model")}</small>
        <div class="confidence-track"><i style="width:${Math.round(confidence * 100)}%"></i></div>
      </div>
      <div class="metric">
        <span>截止时间</span>
        <strong>${escapeHtml(deadline ? `${deadline.date} ${deadline.time || ""}` : "未明确")}</strong>
        <small>优先级：${escapeHtml(priorityMap[extraction?.priority] || "待确认")}</small>
      </div>
    </div>` : `
    <div class="class-grid">
      <div class="metric"><span>安全判断</span><strong>高置信垃圾短信</strong><small>垃圾概率 ${(spam.spam_probability * 100).toFixed(1)}%</small></div>
      <div class="metric"><span>自动行动</span><strong>已停止</strong><small>不会生成报名或缴费提醒</small></div>
    </div>`;

  const reasons = data.review_reasons?.length
    ? `<div class="section-label">需要人工确认</div><ul class="reason-list">${data.review_reasons.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
    : "";
  const steps = data.steps?.length
    ? `<div class="section-label">执行轨迹</div><div class="trace">${data.steps.map((step) => `<div class="trace-row"><b>${escapeHtml(step.name)}</b><span>${escapeHtml(step.result)}</span></div>`).join("")}</div>`
    : "";
  const actionButtons = deadline
    ? `<div class="result-actions"><button class="blue" id="download-ics">导出日历提醒</button><button id="copy-list">复制行动清单</button></div>`
    : `<div class="result-actions"><button id="copy-list">复制行动清单</button></div>`;

  resultContent.innerHTML = `
    <div class="status-head">
      <div><h2>${escapeHtml(category)}</h2><p>轨迹 ${escapeHtml(data.trace_id)} · 输入 ${data.input_length} 字</p></div>
      <span class="status-badge ${statusClass}">${statusLabel}</span>
    </div>
    ${metrics}
    <div class="section-label">行动清单</div>
    <ul class="checklist">${(data.checklist || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    ${reasons}
    ${steps}
    ${actionButtons}`;

  document.getElementById("copy-list")?.addEventListener("click", () => {
    navigator.clipboard.writeText((data.checklist || []).join("\n"));
  });
  document.getElementById("download-ics")?.addEventListener("click", () => downloadIcs(data, category));
}

function downloadIcs(data, title) {
  const deadline = data.extraction.deadline;
  const time = (deadline.time || "09:00").replace(":", "");
  const start = `${deadline.date.replaceAll("-", "")}T${time}00`;
  const endDate = new Date(`${deadline.date}T${deadline.time || "09:00"}:00`);
  endDate.setMinutes(endDate.getMinutes() + 30);
  const pad = (value) => String(value).padStart(2, "0");
  const end = `${endDate.getFullYear()}${pad(endDate.getMonth() + 1)}${pad(endDate.getDate())}T${pad(endDate.getHours())}${pad(endDate.getMinutes())}00`;
  const description = (data.checklist || []).join("；").replace(/,/g, "\\,").replace(/;/g, "\\;");
  const lines = [
    "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Campus Notice Agent//CN", "BEGIN:VEVENT",
    `UID:${data.trace_id}@notice-agent.local`, `DTSTART:${start}`, `DTEND:${end}`,
    `SUMMARY:${title.replace(/,/g, "\\,")}`, `DESCRIPTION:${description}`,
    "BEGIN:VALARM", "TRIGGER:-P1D", "ACTION:DISPLAY", "DESCRIPTION:截止提醒", "END:VALARM",
    "END:VEVENT", "END:VCALENDAR",
  ];
  const blob = new Blob([lines.join("\r\n")], { type: "text/calendar;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "campus-notice-deadline.ics";
  link.click();
  URL.revokeObjectURL(link.href);
}

if (new URLSearchParams(window.location.search).has("demo")) {
  window.addEventListener("load", () => sampleButton.click());
}
