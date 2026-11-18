# 数据复现说明

公开 GitHub 仓库不上传包含学生姓名、联系电话等内容的网页正文快照。复现实验时运行：

```bash
python scripts/fetch_notices.py
python scripts/build_dataset.py
python scripts/fetch_sms_dataset.py
```

通知数据来自上海工程技术大学教务处公开页面，脚本只保存公开标题、日期、链接和正文
摘录，供课程研究使用。短信数据来自 UCI SMS Spam Collection v.1（DOI
10.24432/C5CC84，CC BY 4.0），下载脚本会验证 SHA-256。

仓库保留手工构造、无个人信息的 20 条边界测试案例，以及训练好的模型和聚合评估结果，
便于不重新训练直接运行原型。原始快照与报告原件不放入公开仓库。

