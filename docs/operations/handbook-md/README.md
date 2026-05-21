# 蓝鲸 DBM · MongoDB 运维手册（Markdown 版）

> 本目录是 `docs/operations/handbook` HTML 版手册的 Markdown 镜像，便于在 GitLab / iWiki / VSCode 等环境中直接阅读、检索和二次编辑。

## 📚 目录

| 章节 | 标题 | 文件 |
|------|------|------|
| 第 01 章 | 核心概念与术语 | [01-concepts.md](./01-concepts.md) |
| 第 02 章 | 集群拓扑与节点规范 | [02-cluster-topology.md](./02-cluster-topology.md) |
| 第 03 章 | 数据目录和配置文件 | [03-first-deploy.md](./03-first-deploy.md) |
| 第 04 章 | 单据系统（Tickets） | [04-tickets.md](./04-tickets.md) |
| 第 05 章 | mongosh 使用指南 | [05-mongosh.md](./05-mongosh.md) |
| 第 06 章 | bk-dbmon 监控与备份 | [06-bk-dbmon.md](./06-bk-dbmon.md) |
| 第 07 章 | MongoDB 版本支持 | [07-versions.md](./07-versions.md) |
| 第 08 章 | MongoDB 工具集 | [08-mongo-tools.md](./08-mongo-tools.md) |
| 第 09 章 | MongoDB 日志（各版本差异） | [09-mongodb-logs.md](./09-mongodb-logs.md) |
| 第 10 章 | MongoDB 索引设计与优化 | [10-indexes.md](./10-indexes.md) |
| 第 11 章 | URI 与 Read Preference | [11-uri-readpref.md](./11-uri-readpref.md) |
| 第 12 章 | 真实业务案例 | [12-cases.md](./12-cases.md) |
| 第 13 章 | DBM 性能视图（Grafana） | [13-performance-views.md](./13-performance-views.md) |
| 第 14 章 | DBHA 与故障自愈 | [14-dbha-autofix.md](./14-dbha-autofix.md) |
| 第 15 章 | 附录：常用命令与配置 | [15-appendix.md](./15-appendix.md) |

## 🧭 阅读建议

- **新手入门**：按 01（概念）→ 02（拓扑）→ 03（目录与配置）→ 05（mongosh）顺序通读，理解基础概念与节点本地形态；真正发起部署走 04（工单）+ 06（bk-dbmon）。
- **日常运维**：重点关注 04（单据）、06（监控备份）、13（性能视图）、14（DBHA/自愈）、15（附录速查）。
- **性能优化**：聚焦 11（连接串）和 10（索引）。
- **疑难排查**：先查 12（真实案例）→ 13（性能视图）/ 09（日志）→ 08（工具集）。

## 🔄 与 HTML 版的对应关系

每个 `.md` 文件对应 `../handbook/chapters/` 下的同名 `.html`。
HTML 版包含交互式动效、流程图与可视化卡片，Markdown 版保留全部文字、代码、表格内容，便于离线阅读和版本对比。

---

> 维护提示：当 HTML 章节有结构性更新时，请同步刷新对应 `.md` 文件，保持两套文档一致。
